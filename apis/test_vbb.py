import requests
import json

# --- VBB REST API (no API key needed) ---
BASE_URL = "https://v6.vbb.transport.rest"

print("=" * 50)
print("TEST 1: Fetch live departures from Alexanderplatz")
print("=" * 50)

# Alexanderplatz U-Bahn station ID in VBB system
ALEXANDERPLATZ_ID = "900100003"

url = f"{BASE_URL}/stops/{ALEXANDERPLATZ_ID}/departures"

params = {
    "duration": 10,        # next 10 minutes
    "results": 5,          # only 5 departures
    "subway": "true",      # include U-Bahn
    "tram": "true",        # include trams (M10 etc)
    "bus": "false",
    "suburban": "false"
}

response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    departures = data.get("departures", [])

    print(f"\n✅ Got {len(departures)} departures!\n")

    for dep in departures:
        line    = dep.get("line", {}).get("name", "?")
        dest    = dep.get("direction", "?")
        planned = dep.get("plannedWhen", "?")
        delay   = dep.get("delay", 0)   # delay in SECONDS

        delay_min = round(delay / 60, 1) if delay else 0

        print(f"  Line: {line:<6} → {dest:<35} | Planned: {planned[11:16]} | Delay: {delay_min} min")

    print("\n--- Raw JSON of first departure ---")
    if departures:
        print(json.dumps(departures[0], indent=2))

else:
    print(f"❌ Error {response.status_code}")
    print(response.text)