import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import psycopg2
from datetime import datetime, timedelta
import json

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

def get_recent_predictions(conn, minutes=30):
    """Get recent delay predictions"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            de.event_id,
            vp.line_name,
            s.name as stop_name,
            de.raw_delay_sec,
            de.predicted_delay_sec,
            de.weather_modifier,
            ws.temp_c,
            ws.rain_1h,
            de.event_timestamp
        FROM delay_events de
        JOIN vehicle_positions vp ON de.vehicle_id = vp.vehicle_id
        JOIN stops s ON de.stop_id = s.stop_id
        JOIN weather_snapshots ws ON de.weather_id = ws.weather_id
        WHERE de.event_timestamp > NOW() - INTERVAL '%s minutes'
        ORDER BY de.event_timestamp DESC
        LIMIT 20
    """ % minutes)
    
    predictions = cursor.fetchall()
    cursor.close()
    
    return predictions

def get_bike_suggestions(conn):
    """Get current bike suggestions for delayed vehicles"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT
            de.event_id,
            vp.line_name,
            s.name as stop_name,
            de.predicted_delay_sec,
            COUNT(b.bike_id) as bikes_nearby
        FROM delay_events de
        JOIN vehicle_positions vp ON de.vehicle_id = vp.vehicle_id
        JOIN stops s ON de.stop_id = s.stop_id
        LEFT JOIN bikes_available b ON s.stop_id = b.stop_id AND b.is_reserved = FALSE
        WHERE de.predicted_delay_sec > 420  -- > 7 minutes
        AND de.event_timestamp > NOW() - INTERVAL '30 minutes'
        GROUP BY de.event_id, vp.line_name, s.name, de.predicted_delay_sec
        ORDER BY de.predicted_delay_sec DESC
    """)
    
    suggestions = cursor.fetchall()
    cursor.close()
    
    return suggestions

def print_predictions(predictions):
    """Pretty print predictions"""
    print("\n" + "=" * 80)
    print("RECENT DELAY PREDICTIONS (Last 30 minutes)")
    print("=" * 80)
    
    if not predictions:
        print("No predictions found.")
        return
    
    for pred in predictions:
        event_id, line, stop, raw_delay, pred_delay, weather_mod, temp, rain, timestamp = pred
        
        raw_min = raw_delay / 60 if raw_delay else 0
        pred_min = pred_delay / 60 if pred_delay else 0
        mod_pct = weather_mod * 100 if weather_mod else 0
        
        print(f"\n📍 {stop}")
        print(f"   Line: {line}")
        print(f"   Raw Delay: {raw_min:.1f} min → Predicted: {pred_min:.1f} min")
        print(f"   Weather Modifier: +{mod_pct:.1f}% (Temp: {temp}°C, Rain: {rain}mm)")
        print(f"   Timestamp: {timestamp}")

def print_bike_suggestions(suggestions):
    """Pretty print bike suggestions"""
    print("\n" + "=" * 80)
    print("🚲 BIKE FALLBACK SUGGESTIONS (Delays > 7 min)")
    print("=" * 80)
    
    if not suggestions:
        print("No significant delays requiring bike suggestions at this time.")
        return
    
    for sug in suggestions:
        event_id, line, stop, pred_delay, bikes_count = sug
        pred_min = pred_delay / 60 if pred_delay else 0
        
        print(f"\n⚠️  {line} at {stop}")
        print(f"   Expected delay: {pred_min:.1f} minutes")
        print(f"   🚲 Available bikes nearby: {bikes_count}")
        print(f"   ✅ Suggest using Nextbike instead of waiting")

def main():
    print("=" * 80)
    print("VBB-SmartDelay API Output")
    print("=" * 80)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Get and display recent predictions
    predictions = get_recent_predictions(conn, minutes=30)
    print_predictions(predictions)
    
    # Get and display bike suggestions
    suggestions = get_bike_suggestions(conn)
    print_bike_suggestions(suggestions)
    
    print("\n" + "=" * 80)
    print("✅ API Output Complete")
    print("=" * 80 + "\n")
    
    conn.close()

if __name__ == "__main__":
    main()