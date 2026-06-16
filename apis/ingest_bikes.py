import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import requests
import psycopg2
from datetime import datetime
import math

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

# GBFS Nextbike Berlin
GBFS_URL = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bn/en/free_bike_status.json"

# Known stop locations (for matching bikes)
STOPS = [
    {"vbb_id": "900100003", "lat": 52.521508, "lon": 13.411267},
    {"vbb_id": "900096101", "lat": 52.596451, "lon": 13.335524},
    {"vbb_id": "900056105", "lat": 52.520008, "lon": 13.386389},
]

SEARCH_RADIUS_KM = 0.5  # Match bikes within 500m of stop

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS points (in km)"""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def find_nearest_stop(bike_lat, bike_lon):
    """Find the nearest stop to a bike (within search radius)"""
    nearest_stop = None
    min_distance = float('inf')
    
    for stop in STOPS:
        distance = haversine_distance(bike_lat, bike_lon, stop["lat"], stop["lon"])
        if distance < min_distance and distance <= SEARCH_RADIUS_KM:
            min_distance = distance
            nearest_stop = stop
    
    return nearest_stop

def fetch_bikes():
    """Fetch available bikes from GBFS feed"""
    response = requests.get(GBFS_URL)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("bikes", [])
    else:
        print(f"❌ Error fetching bikes: {response.status_code}")
        return []

def insert_bike(conn, bike, stop_vbb_id):
    """Insert one bike into the database"""
    cursor = conn.cursor()
    
    try:
        bike_id_nextbike = bike.get("bike_id")
        lat = bike.get("lat")
        lon = bike.get("lon")
        is_reserved = bike.get("is_reserved", False)
        
        cursor.execute("""
            INSERT INTO bikes_available 
            (stop_id, nextbike_id, lat, lon, is_reserved, geom, last_seen)
            SELECT 
                stop_id, %s, %s, %s, %s, 
                ST_GeomFromText('POINT(' || %s || ' ' || %s || ')', 4326),
                %s
            FROM stops
            WHERE vbb_id = %s
            ON CONFLICT (nextbike_id) DO UPDATE
            SET lat = %s, lon = %s, is_reserved = %s, last_seen = %s
        """, (
            bike_id_nextbike, lat, lon, is_reserved, lon, lat, datetime.now(), stop_vbb_id,
            lat, lon, is_reserved, datetime.now()
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error inserting bike: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def main():
    print("=" * 60)
    print("GBFS Nextbike Ingestion")
    print("=" * 60)
    
    # Fetch bikes
    print("Fetching available bikes from Berlin...")
    bikes = fetch_bikes()
    print(f"✅ Got {len(bikes)} total bikes\n")
    
    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Match bikes to stops and insert
    matched_count = 0
    
    for bike in bikes:
        bike_lat = bike.get("lat")
        bike_lon = bike.get("lon")
        
        # Find nearest stop
        nearest_stop = find_nearest_stop(bike_lat, bike_lon)
        
        if nearest_stop:
            if insert_bike(conn, bike, nearest_stop["vbb_id"]):
                matched_count += 1
                status = "reserved" if bike.get("is_reserved") else "available"
                print(f"   ✓ Bike near {nearest_stop['vbb_id']}: {status}")
    
    print(f"\n✅ Matched and ingested {matched_count} bikes near target stops")
    conn.close()

if __name__ == "__main__":
    main()