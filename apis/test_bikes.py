import requests
import json

# --- GBFS Nextbike Berlin (no API key needed) ---
BASE_URL = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bn/en"

print("=" * 50)
print("TEST: Fetch available bikes near Berlin")
print("=" * 50)

# Step 1: get list of free bikes
url = f"{BASE_URL}/free_bike_status.json"

response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    bikes = data["data"]["bikes"]

    print(f"\n✅ Got {len(bikes)} available bikes in Berlin!\n")

    # Step 2: show the first 5 bikes
    print("Sample of available bikes:\n")
    for bike in bikes[:5]:
        bike_id  = bike.get("bike_id", "?")
        lat      = bike.get("lat", "?")
        lon      = bike.get("lon", "?")
        is_reserved = bike.get("is_reserved", False)
        is_disabled = bike.get("is_disabled", False)

        status = "available" if not is_reserved and not is_disabled else "unavailable"

        print(f"  Bike ID : {bike_id}")
        print(f"  Location: lat={lat}, lon={lon}")
        print(f"  Status  : {status}")
        print()

    # Step 3: show raw JSON of first bike
    print("--- Raw JSON of first bike ---")
    print(json.dumps(bikes[0], indent=2))

else:
    print(f"❌ Error {response.status_code}")
    print(response.text)