import csv
import os
import time
import requests

BASE = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": os.environ["OPENAQ_API_KEY"]}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def get_result(path):
    # Fetch one sensor or location record from OpenAQ.
    response = SESSION.get(f"{BASE}{path}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", [])
    if isinstance(results, list):
        return results[0] if results else {}
    return results if isinstance(results, dict) else {}

def date_value(obj, field):
    # Extract a UTC timestamp from OpenAQ's nested date metadata.
    value = obj.get(field) or {}
    if isinstance(value, dict):
        return value.get("utc", "")
    return str(value)

source = os.path.expanduser("~/openaq_station_shortlist.csv")
output = os.path.expanduser("~/openaq_station_enriched.csv")

with open(source, newline="", encoding="utf-8") as handle:
    candidates = list(csv.DictReader(handle))

rows = []
for index, candidate in enumerate(candidates, start=1):
    sensor_id = candidate["sensor_id"]
    location_id = candidate["location_id"]

    try:
        # Get the authoritative sensor metadata and its parameter details.
        sensor = get_result(f"/sensors/{sensor_id}")
        parameter = sensor.get("parameter") or {}

        # Get the location's coordinates, country, and provider information.
        location = get_result(f"/locations/{location_id}")
        coords = location.get("coordinates") or {}
        country = location.get("country") or {}
        provider = location.get("provider") or {}

        row = {
            **candidate,
            "verified_sensor_id": sensor.get("id", ""),
            "parameter_name": parameter.get("name", ""),
            "parameter_id": parameter.get("id", ""),
            "sensor_first_utc": date_value(sensor, "datetimeFirst"),
            "sensor_last_utc": date_value(sensor, "datetimeLast"),
            "latitude": coords.get("latitude", ""),
            "longitude": coords.get("longitude", ""),
            "country_code": country.get("code", ""),
            "country_name": country.get("name", ""),
            "provider_name": provider.get("name", "") if isinstance(provider, dict) else str(provider),
            "verified_location_name": location.get("name", ""),
            "metadata_status": "OK",
        }
    except Exception as exc:
        row = {
            **candidate,
            "metadata_status": f"ERROR: {type(exc).__name__}",
        }

    rows.append(row)

    print(
        f"[{index:02d}/{len(candidates)}] "
        f"{candidate.get('location')} | "
        f"sensor={sensor_id} | "
        f"country={row.get('country_code', '')} | "
        f"first={row.get('sensor_first_utc', '')} | "
        f"last={row.get('sensor_last_utc', '')} | "
        f"{row['metadata_status']}"
    )

    # Avoid sending requests too rapidly.
    time.sleep(0.15)

# Save all candidates, including metadata errors, for review.
fields = sorted({key for row in rows for key in row})
with open(output, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("\nEnrichment complete.")
print("Records:", len(rows))
print("Saved to:", output)
