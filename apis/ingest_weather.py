import os
from dotenv import load_dotenv, find_dotenv

# Load secrets from the .env file in the project root (never committed to git)
load_dotenv(find_dotenv(usecwd=True))

import requests
import psycopg2
from datetime import datetime

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set. Create a .env file in the project root (see .env.example).")

# OpenWeatherMap API
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
if not WEATHER_API_KEY:
    raise SystemExit("WEATHER_API_KEY not set. Add it to your .env file (see .env.example).")
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

def fetch_weather():
    """Fetch current weather for Berlin"""
    params = {
        "q": "Berlin",
        "appid": WEATHER_API_KEY,
        "units": "metric"
    }
    
    response = requests.get(WEATHER_URL, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error fetching weather: {response.status_code}")
        return None

def insert_weather_snapshot(conn, weather_data):
    """Insert weather snapshot into database"""
    cursor = conn.cursor()
    
    try:
        temp_c = weather_data.get("main", {}).get("temp")
        rain_1h = weather_data.get("rain", {}).get("1h", 0)
        wind_speed_ms = weather_data.get("wind", {}).get("speed")
        humidity_pct = weather_data.get("main", {}).get("humidity")
        
        cursor.execute("""
            INSERT INTO weather_snapshots 
            (temp_c, rain_1h, wind_speed_ms, humidity_pct, snapshot_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING weather_id
        """, (temp_c, rain_1h, wind_speed_ms, humidity_pct, datetime.now()))
        
        weather_id = cursor.fetchone()[0]
        conn.commit()
        
        return weather_id
        
    except Exception as e:
        print(f"❌ Error inserting weather: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()

def main():
    print("=" * 60)
    print("OpenWeatherMap Ingestion")
    print("=" * 60)
    
    # Fetch weather
    print("Fetching weather for Berlin...")
    weather_data = fetch_weather()
    
    if not weather_data:
        print("❌ Failed to fetch weather data")
        return
    
    # Extract fields
    temp = weather_data.get("main", {}).get("temp")
    rain = weather_data.get("rain", {}).get("1h", 0)
    wind = weather_data.get("wind", {}).get("speed")
    humidity = weather_data.get("main", {}).get("humidity")
    description = weather_data.get("weather", [{}])[0].get("description")
    
    print(f"✅ Got weather data:")
    print(f"   Temperature: {temp} °C")
    print(f"   Rain (1h):   {rain} mm")
    print(f"   Wind:        {wind} m/s")
    print(f"   Humidity:    {humidity} %")
    print(f"   Condition:   {description}\n")
    
    # Insert into database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        weather_id = insert_weather_snapshot(conn, weather_data)
        
        if weather_id:
            print(f"✅ Weather snapshot inserted (ID: {weather_id})")
        else:
            print("❌ Failed to insert weather snapshot")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    main()