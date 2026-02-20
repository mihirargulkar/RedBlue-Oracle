import os
import sys

# Add src to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ingestion.real_time_collector import get_vehicle_positions, get_weather

def test_mbta_api():
    print("Testing MBTA /vehicles API...")
    try:
        vehicles = get_vehicle_positions()
        print(f"SUCCESS: Fetched {len(vehicles)} subway vehicles.")
        if vehicles:
            sample = vehicles[0]
            print(f"Sample Vehicle ID: {sample['id']}, Status: {sample['attributes']['current_status']}")
        return True
    except Exception as e:
        print(f"FAILED MBTA API check: {e}")
        return False

def test_weather_api():
    print("\nTesting Open-Meteo API...")
    try:
        weather = get_weather()
        print(f"SUCCESS: Current Temperature: {weather['temperature']}°C")
        return True
    except Exception as e:
        print(f"FAILED Open-Meteo check: {e}")
        return False

if __name__ == "__main__":
    print("--- Running API Health Checks ---")
    mbta_ok = test_mbta_api()
    weather_ok = test_weather_api()
    
    print("\n--- Summary ---")
    if mbta_ok and weather_ok:
        print("ALL API TESTS PASSED! Data collection logic is working.")
        print("(Note: Database insertion tests require local Postgres configuration via .env)")
    else:
        print("SOME TESTS FAILED. Please check the logs.")
