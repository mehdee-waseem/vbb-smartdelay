import subprocess
import time

print("\n" + "=" * 80)
print("VBB-SmartDelay: Complete Data Pipeline")
print("=" * 80 + "\n")

scripts = [
    ("ingest_weather.py", "Fetching weather data..."),
    ("ingest_vbb.py", "Fetching VBB transit data..."),
    ("ingest_bikes.py", "Fetching bike data..."),
    ("predict_delays.py", "Generating predictions..."),
    ("api_output.py", "Displaying results..."),
]

for script, description in scripts:
    print(f"\n{'=' * 80}")
    print(f"▶️  {description}")
    print(f"{'=' * 80}")
    
    try:
        result = subprocess.run(["python", script], capture_output=False, text=True)
        if result.returncode != 0:
            print(f"⚠️  Script {script} had issues")
    except Exception as e:
        print(f"❌ Error running {script}: {e}")
    
    time.sleep(1)

print("\n" + "=" * 80)
print("✅ Pipeline complete!")
print("=" * 80 + "\n")