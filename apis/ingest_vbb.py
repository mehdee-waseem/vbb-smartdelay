import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import requests
import psycopg2
from datetime import datetime
import json

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

# VBB API
BASE_URL = "https://v6.vbb.transport.rest"

# Target lines: U2, M10, S5, S7, Bus 22
TARGET_LINES = ["U2", "M10", "S5", "S7", "22"]

# Target stops (we'll fetch from multiple stops)
STOPS = [
    {"vbb_id": "900100003", "name": "S+U Alexanderplatz Bhf"},
    {"vbb_id": "900096101", "name": "S+U Wittenau"},
    {"vbb_id": "900056105", "name": "U Friedrichstraße"},
]

def fetch_departures(stop_vbb_id):
    """Fetch live departures from a single stop"""
    url = f"{BASE_URL}/stops/{stop_vbb_id}/departures"
    params = {
        "duration": 30,  # next 30 minutes
        "results": 50,   # up to 50 departures
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json().get("departures", [])
    else:
        print(f"❌ Error fetching departures for {stop_vbb_id}: {response.status_code}")
        return []

def filter_target_lines(departures):
    """Filter to only our target lines"""
    filtered = []
    for dep in departures:
        line_name = dep.get("line", {}).get("name", "")
        if line_name in TARGET_LINES:
            filtered.append(dep)
    return filtered

def insert_vehicle_position(conn, departure, stop_vbb_id):
    """Insert one vehicle position into the database"""
    cursor = conn.cursor()
    
    try:
        trip_id = departure.get("tripId", "")
        line_name = departure.get("line", {}).get("name", "")
        delay_seconds = departure.get("delay", 0)
        
        # GPS position
        current_pos = departure.get("currentTripPosition", {})
        lat = current_pos.get("latitude")
        lon = current_pos.get("longitude")
        
        if not lat or not lon:
            return False
        
        # Insert into vehicle_positions table
        cursor.execute("""
            INSERT INTO vehicle_positions 
            (stop_id, trip_id, line_name, lat, lon, delay_seconds, recorded_at)
            SELECT 
                stop_id, %s, %s, %s, %s, %s, %s
            FROM stops
            WHERE vbb_id = %s
            ON CONFLICT DO NOTHING
        """, (trip_id, line_name, lat, lon, delay_seconds, datetime.now(), stop_vbb_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error inserting vehicle position: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def main():
    print("=" * 60)
    print("VBB Live Delay Ingestion")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    total_vehicles = 0
    
    # Fetch from each stop
    for stop in STOPS:
        print(f"Fetching departures from: {stop['name']}")
        
        departures = fetch_departures(stop["vbb_id"])
        print(f"  → Got {len(departures)} departures")
        
        # Filter to target lines
        filtered = filter_target_lines(departures)
        print(f"  → Filtered to {len(filtered)} target lines")
        
        # Insert each vehicle
        for dep in filtered:
            if insert_vehicle_position(conn, dep, stop["vbb_id"]):
                total_vehicles += 1
                line = dep.get("line", {}).get("name", "?")
                delay = dep.get("delay", 0) / 60  # convert to minutes
                print(f"      ✓ {line}: {delay:.1f} min delay")
    
    print(f"\n✅ Ingested {total_vehicles} vehicle positions")
    conn.close()

if __name__ == "__main__":
    main()