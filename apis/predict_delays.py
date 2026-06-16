import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import psycopg2
from datetime import datetime, timedelta
import math

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

# --- Bike-suggestion policy (configurable) ---
# Static gate: ignore delays shorter than this many minutes.
# Override without touching code via the BIKE_SUGGESTION_THRESHOLD_MIN env var.
DEFAULT_THRESHOLD_MIN = float(os.getenv("BIKE_SUGGESTION_THRESHOLD_MIN", "7"))
# Dynamic check parameters: only suggest a bike if riding actually beats waiting.
WALKING_SPEED_MS = 1.4        # ~5 km/h average walking pace
BIKE_UNLOCK_BUFFER_SEC = 60   # time to reach, unlock and start the bike


def should_suggest_bike(predicted_delay_sec, nearest_bike_m):
    """
    Decide whether to recommend a bike instead of waiting.

    Two-stage policy (this is what replaces the old fixed 7-minute rule):
      1. Static gate  - ignore trivial delays below DEFAULT_THRESHOLD_MIN.
      2. Dynamic check - only suggest a bike when walking to it and unlocking
                         it is genuinely faster than waiting out the delay.
    Returns (suggest: bool, reason: str).
    """
    if predicted_delay_sec < DEFAULT_THRESHOLD_MIN * 60:
        return False, f"delay under {DEFAULT_THRESHOLD_MIN:.0f}-min gate"
    if nearest_bike_m is None:
        return False, "no available bike nearby"
    walk_sec = nearest_bike_m / WALKING_SPEED_MS + BIKE_UNLOCK_BUFFER_SEC
    if predicted_delay_sec > walk_sec:
        saved = (predicted_delay_sec - walk_sec) / 60
        return True, f"saves ~{saved:.1f} min vs waiting"
    return False, "waiting is still faster than biking"

def get_latest_weather(conn):
    """Get the most recent weather snapshot"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weather_id, temp_c, rain_1h, wind_speed_ms, humidity_pct
        FROM weather_snapshots
        ORDER BY snapshot_at DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    cursor.close()
    
    if result:
        return {
            "weather_id": result[0],
            "temp_c": result[1],
            "rain_1h": result[2],
            "wind_speed_ms": result[3],
            "humidity_pct": result[4]
        }
    return None

def calculate_weather_modifier(rain_1h, wind_speed_ms):
    """
    Calculate speed penalty based on weather.
    
    Logic:
    - Rain > 1mm: +5% slower
    - Rain > 5mm: +10% slower (heavy rain)
    - Wind > 10 m/s: +3% slower
    - Combined: additive
    """
    modifier = 0.0
    
    if rain_1h > 5:
        modifier += 0.10
    elif rain_1h > 1:
        modifier += 0.05
    
    if wind_speed_ms > 10:
        modifier += 0.03
    
    return modifier

def get_vehicles_needing_prediction(conn):
    """Get recent vehicle positions that need delay prediction"""
    cursor = conn.cursor()
    
    # Get vehicles from last 15 minutes that don't have predictions yet
    cursor.execute("""
        SELECT vp.vehicle_id, vp.stop_id, vp.trip_id, vp.line_name, 
               vp.delay_seconds, vp.lat, vp.lon, vp.recorded_at
        FROM vehicle_positions vp
        WHERE vp.recorded_at > NOW() - INTERVAL '15 minutes'
        AND vp.vehicle_id NOT IN (
            SELECT vehicle_id FROM delay_events 
            WHERE event_timestamp > NOW() - INTERVAL '5 minutes'
        )
        ORDER BY vp.recorded_at DESC
        LIMIT 50
    """)
    
    vehicles = cursor.fetchall()
    cursor.close()
    
    return vehicles

def find_nearby_bikes(conn, stop_id, bike_radius_km=0.5):
    """Find available bikes near a transit stop"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT b.bike_id, b.nextbike_id, b.lat, b.lon,
               ST_Distance(b.geom, s.geom) / 1000.0 as distance_km
        FROM bikes_available b
        JOIN stops s ON b.stop_id = s.stop_id
        WHERE s.stop_id = %s
        AND b.is_reserved = FALSE
        AND ST_DWithin(b.geom, s.geom, %s * 1000)
        ORDER BY distance_km
        LIMIT 5
    """, (stop_id, bike_radius_km))
    
    bikes = cursor.fetchall()
    cursor.close()
    
    return bikes

def insert_delay_event(conn, vehicle_id, stop_id, weather_id, 
                       raw_delay_sec, weather_modifier, predicted_delay_sec):
    """Insert a delay prediction event into the database"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO delay_events 
            (vehicle_id, stop_id, weather_id, raw_delay_sec, 
             weather_modifier, predicted_delay_sec, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id
        """, (vehicle_id, stop_id, weather_id, raw_delay_sec, 
              weather_modifier, predicted_delay_sec, datetime.now()))
        
        event_id = cursor.fetchone()[0]
        conn.commit()
        
        return event_id
        
    except Exception as e:
        print(f"❌ Error inserting delay event: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()

def main():
    print("=" * 70)
    print("VBB-SmartDelay Prediction Engine")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Step 1: Get latest weather
    print("Step 1: Fetching latest weather data...")
    weather = get_latest_weather(conn)
    
    if not weather:
        print("❌ No weather data found")
        conn.close()
        return
    
    print(f"✅ Weather:")
    print(f"   Temperature: {weather['temp_c']} °C")
    print(f"   Rain (1h): {weather['rain_1h']} mm")
    print(f"   Wind: {weather['wind_speed_ms']} m/s\n")
    
    # Step 2: Calculate weather modifier
    weather_modifier = calculate_weather_modifier(weather['rain_1h'], weather['wind_speed_ms'])
    print(f"Step 2: Weather speed modifier = {weather_modifier * 100:.1f}%\n")
    
    # Step 3: Get vehicles needing prediction
    print("Step 3: Fetching recent vehicle positions...")
    vehicles = get_vehicles_needing_prediction(conn)
    print(f"✅ Found {len(vehicles)} vehicles\n")
    
    # Step 4: Process each vehicle
    print("Step 4: Generating predictions...\n")
    
    predictions_made = 0
    bike_suggestions = 0
    
    for vehicle in vehicles:
        vehicle_id, stop_id, trip_id, line_name, raw_delay_sec, lat, lon, recorded_at = vehicle
        
        # Calculate predicted delay with weather modifier
        # Simple model: predicted = raw_delay * (1 + weather_modifier)
        predicted_delay_sec = int(raw_delay_sec * (1 + weather_modifier))
        predicted_delay_min = predicted_delay_sec / 60
        
        # Insert prediction
        event_id = insert_delay_event(
            conn, vehicle_id, stop_id, weather['weather_id'],
            raw_delay_sec, weather_modifier, predicted_delay_sec
        )
        
        if event_id:
            predictions_made += 1
            
            print(f"   {line_name} at stop {stop_id}")
            print(f"      Raw delay: {raw_delay_sec/60:.1f} min")
            print(f"      Predicted: {predicted_delay_min:.1f} min")
            
            # Decide whether to suggest a bike: static gate + dynamic "does it beat waiting?" check
            bikes = find_nearby_bikes(conn, stop_id)
            nearest_bike_m = bikes[0][4] * 1000 if bikes else None  # distance_km -> metres

            suggest, reason = should_suggest_bike(predicted_delay_sec, nearest_bike_m)
            if suggest:
                print(f"      ⚠️  Suggesting bike ({reason}):")
                for bike in bikes[:3]:
                    bike_id, nextbike_id, bike_lat, bike_lon, distance_km = bike
                    print(f"         🚲 Bike {nextbike_id[:8]}... ({distance_km*1000:.0f}m away)")
                    bike_suggestions += 1
            else:
                print(f"      (no bike suggested: {reason})")
            
            print()
    
    print("=" * 70)
    print(f"✅ Predictions generated: {predictions_made}")
    print(f"🚲 Bike suggestions made: {bike_suggestions}")
    print("=" * 70)
    
    conn.close()

if __name__ == "__main__":
    main()