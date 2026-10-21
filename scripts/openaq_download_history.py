import csv
import os
import time
import requests
from datetime import datetime, timezone

BASE = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": os.environ["OPENAQ_API_KEY"]}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Provisional stations selected from the coverage audit.
STATIONS = [
    {"sensor_id": 23534,    "station": "New Delhi",             "start": "2025-01"},
    {"sensor_id": 9320367,  "station": "GK1 Delhi",             "start": "2025-01"},
    {"sensor_id": 13478101, "station": "CURAJ",                 "start": "2025-07"},
    {"sensor_id": 14499369, "station": "VNIT Nagpur",           "start": "2025-10"},
    {"sensor_id": 15203555, "station": "Koramangala Bengaluru", "start": "2026-01"},
    {"sensor_id": 12235583, "station": "Zoo Park Hyderabad",    "start": "2025-02"},
]

# Keep the first dataset version to complete months through September 2026.
END_MONTH = "2026-10"  # Exclusive: stops at 2026-10-01 UTC.
OUTPUT = os.path.expanduser("~/aircast_pm25_hourly.csv")

def month_start(text):
    return datetime.strptime(text, "%Y-%m").replace(tzinfo=timezone.utc)

def next_month(dt):
    year = dt.year + (dt.month == 12)
    month = 1 if dt.month == 12 else dt.month + 1
    return dt.replace(year=year, month=month, day=1)

def api_get(path, params):
    # Retry temporary throttling and server errors.
    for attempt in range(5):
        response = SESSION.get(f"{BASE}{path}", params=params, timeout=45)
        if response.status_code == 429 or response.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"API retries exhausted: {path} {params}")

if os.path.exists(OUTPUT):
    raise SystemExit(
        f"Output already exists: {OUTPUT}\n"
        "Rename or back it up before rerunning; this script will not overwrite it."
    )

all_rows = []
seen = set()
errors = []

for station in STATIONS:
    sensor_id = station["sensor_id"]
    start = month_start(station["start"])
    end = month_start(END_MONTH)
    print(f"\nDownloading {station['station']} (sensor {sensor_id})")

    month = start
    while month < end:
        month_end = next_month(month)
        page = 1
        month_count = 0

        while True:
            params = {
                "datetime_from": month.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_to": month_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 1000,
                "page": page,
            }

            try:
                payload = api_get(f"/sensors/{sensor_id}/hours", params)
            except Exception as exc:
                errors.append({
                    "sensor_id": sensor_id,
                    "station": station["station"],
                    "month": month.strftime("%Y-%m"),
                    "error": type(exc).__name__,
                })
                print(f"  {month:%Y-%m}: ERROR {type(exc).__name__}")
                break

            records = payload.get("results", [])
            for record in records:
                period = record.get("period") or {}
                start_time = period.get("datetimeFrom") or {}
                end_time = period.get("datetimeTo") or {}
                utc_start = start_time.get("utc", "")
                if not utc_start:
                    continue

                # Deduplicate by sensor and UTC timestamp.
                key = (sensor_id, utc_start)
                if key in seen:
                    continue
                seen.add(key)

                all_rows.append({
                    "timestamp_utc": utc_start,
                    "timestamp_local": start_time.get("local", ""),
                    "period_end_utc": end_time.get("utc", ""),
                    "value": record.get("value", ""),
                    "unit": (record.get("parameter") or {}).get("units", ""),
                    "parameter": (record.get("parameter") or {}).get("name", "pm25"),
                    "sensor_id": sensor_id,
                    "station": station["station"],
                    "location_id": "",
                    "month_requested": month.strftime("%Y-%m"),
                })
                month_count += 1

            # Continue pagination whenever a full page was returned.
            if len(records) < 1000:
                break
            page += 1

        print(f"  {month:%Y-%m}: {month_count} unique records")
        month = month_end
        time.sleep(0.1)

# Sort deterministically before writing the combined dataset.
all_rows.sort(key=lambda row: (row["timestamp_utc"], row["sensor_id"]))

fields = [
    "timestamp_utc", "timestamp_local", "period_end_utc", "value",
    "unit", "parameter", "sensor_id", "station", "location_id",
    "month_requested",
]
with open(OUTPUT, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(all_rows)

# Record failed month requests separately so they are not mistaken for zero readings.
if errors:
    error_file = os.path.expanduser("~/aircast_download_errors.csv")
    with open(error_file, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=errors[0].keys())
        writer.writeheader()
        writer.writerows(errors)
    print("Download errors saved to:", error_file)

print("\nDownload finished.")
print("Total unique hourly records:", len(all_rows))
print("Stations requested:", len(STATIONS))
print("Output:", OUTPUT)
print("Failed month requests:", len(errors))
