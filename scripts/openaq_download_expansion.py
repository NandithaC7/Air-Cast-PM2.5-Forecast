import csv
import os
import time
import requests
from datetime import date

# Keep the existing six-station dataset unchanged.
ORIGINAL = os.path.expanduser("~/aircast_pm25_hourly.csv")
OUTPUT = os.path.expanduser("~/aircast_pm25_hourly_expanded.csv")
ERRORS = os.path.expanduser("~/aircast_expansion_errors.csv")

# Add only the eight new sensors selected from the coverage audit.
# Start months match the historical coverage audit.
STATIONS = [
    {"id": 13273790, "name": "Santushti Apartments, Vasant Kunj", "start": "2025-06-01"},
    {"id": 14453757, "name": "Sector 1, Noida extension", "start": "2025-10-01"},
    {"id": 13587481, "name": "IIMA Ventures", "start": "2025-07-01"},
    {"id": 14745878, "name": "Anand Lok", "start": "2025-11-01"},
    {"id": 14598776, "name": "Uptitude Cloud Pvt Ltd - Sector 62, GGN", "start": "2025-11-01"},
    {"id": 14755255, "name": "Araria", "start": "2025-11-01"},
    {"id": 15289075, "name": "Air Check", "start": "2026-01-01"},
    {"id": 15175974, "name": "Talab Tillo Jammu", "start": "2026-01-01"},
]

# Exclusive UTC end date, matching the original historical download window.
END = date(2026, 10, 1)
BASE = "https://api.openaq.org/v3"
PAGE_SIZE = 1000

FIELDS = [
    "timestamp_utc", "timestamp_local", "period_end_utc",
    "value", "unit", "parameter", "sensor_id", "station",
    "location_id", "month_requested"
]

api_key = os.environ.get("OPENAQ_API_KEY")
if not api_key:
    raise SystemExit("OPENAQ_API_KEY is not set.")

# Do not overwrite an earlier expansion accidentally.
if os.path.exists(OUTPUT):
    raise SystemExit(
        f"{OUTPUT} already exists. Rename it before running again."
    )

# Read the existing dataset so we can merge without changing it.
with open(ORIGINAL, newline="", encoding="utf-8") as handle:
    existing_rows = list(csv.DictReader(handle))

# Store records by sensor and UTC timestamp to avoid duplicates.
records = {}
for row in existing_rows:
    records[(str(row["sensor_id"]), row["timestamp_utc"])] = row

errors = []
session = requests.Session()
session.headers.update({"X-API-Key": api_key})


def next_month_start(current):
    # Calculate the first day of the next calendar month.
    if current.month == 12:
        return date(current.year + 1, 1, 1)
    return date(current.year, current.month + 1, 1)


def fetch_month(station, month):
    """Fetch every page of hourly observations for one sensor/month."""
    month_end = min(next_month_start(month), END)
    params = {
        "datetime_from": month.isoformat() + "T00:00:00Z",
        "datetime_to": month_end.isoformat() + "T00:00:00Z",
        "limit": PAGE_SIZE,
        "page": 1,
    }
    result_rows = []

    while True:
        response = session.get(
            f"{BASE}/sensors/{station['id']}/hours",
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])

        if not results:
            break

        for item in results:
            period = item.get("period") or {}
            start = period.get("datetimeFrom") or {}
            end = period.get("datetimeTo") or {}
            parameter = item.get("parameter") or {}

            utc = start.get("utc")
            local = start.get("local")

            # Preserve both source timestamps; do not convert or shift them.
            if not utc or not local:
                continue

            result_rows.append({
                "timestamp_utc": utc,
                "timestamp_local": local,
                "period_end_utc": end.get("utc", ""),
                "value": item.get("value"),
                "unit": parameter.get("units", ""),
                "parameter": parameter.get("name", "pm25"),
                "sensor_id": str(station["id"]),
                "station": station["name"],
                "location_id": "",
                "month_requested": month.strftime("%Y-%m"),
            })

        # Move through every page, not just the first 1,000 records.
        if len(results) < PAGE_SIZE:
            break

        params["page"] += 1
        time.sleep(0.15)

    return result_rows


for station in STATIONS:
    start = date.fromisoformat(station["start"])
    month = date(start.year, start.month, 1)

    while month < END:
        label = month.strftime("%Y-%m")
        print(f"Downloading {station['name']} | {label}")

        try:
            rows = fetch_month(station, month)
            for row in rows:
                key = (row["sensor_id"], row["timestamp_utc"])
                records[key] = row
            print(f"  Received {len(rows)} records")
        except (requests.RequestException, ValueError, KeyError) as exc:
            # Log the failed month so it can be retried later.
            errors.append({
                "sensor_id": station["id"],
                "station": station["name"],
                "month_requested": label,
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"  ERROR: {type(exc).__name__}")

        month = next_month_start(month)
        time.sleep(0.15)

# Sort and write the expanded raw dataset deterministically.
final_rows = sorted(
    records.values(),
    key=lambda row: (str(row["sensor_id"]), row["timestamp_utc"])
)

with open(OUTPUT, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(final_rows)

# Save request failures separately; a failed month means the download needs review.
if errors:
    with open(ERRORS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sensor_id", "station", "month_requested", "error"]
        )
        writer.writeheader()
        writer.writerows(errors)

print("\n========== EXPANSION SUMMARY ==========")
print("Original rows:", len(existing_rows))
print("Expanded unique rows:", len(final_rows))
print("Additional unique rows:", len(final_rows) - len(existing_rows))
print("Request failures:", len(errors))
print("Expanded CSV:", OUTPUT)
if errors:
    print("Review failed months in:", ERRORS)

session.close()
