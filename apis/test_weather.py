import requests

# --- CONFIG ---
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
API_KEY = os.getenv("WEATHER_API_KEY")
CITY = "Berlin"
URL = "https://api.openweathermap.org/data/2.5/weather"

# --- API CALL ---
params = {
    "q": CITY,
    "appid": API_KEY,
    "units": "metric"   # gives us Celsius, m/s wind speed
}

response = requests.get(URL, params=params)

# --- PARSE & DISPLAY ---
if response.status_code == 200:
    data = response.json()

    print("✅ Connection successful!\n")
    print(f"City        : {data['name']}")
    print(f"Temperature : {data['main']['temp']} °C")
    print(f"Weather     : {data['weather'][0]['description']}")
    print(f"Wind Speed  : {data['wind']['speed']} m/s")

    # This is the key field for our delay prediction
    rain_1h = data.get("rain", {}).get("1h", 0)
    print(f"Rain (1h)   : {rain_1h} mm")

    print("\n--- Raw JSON (full response) ---")
    import json
    print(json.dumps(data, indent=2))

else:
    print(f"❌ Error {response.status_code}: {response.json()}")