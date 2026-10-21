import csv
import os
import time
import requests
from datetime import datetime, timezone

BASE = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": os.environ["OPENAQ_API_KEY"]}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Sensor IDs selected from the verified metadata audit.
SENSORS = {
    23320: "Mumbai",
    23534: "New Delhi",
    9320367: "GK1 Delhi",
    13478101: "CURAJ",
    13587481: "IIMA Ventures",
    14499369: "VNIT Nagpur",
    15203555: "Koramangala Bengaluru",
}

def get_json(path, params):
    # Request one month's hourly records, retrying transient API failures.
    for attempt in range(4):
        response = SESSION.get(
            f"{BASE}{path}", params=params, timeout=30
        )
        if response.status_code == 429 or response.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"API retries exhausted for {path}")

def month_range(start_year, start_month, end_year, end_month):
    # Generate month boundaries without assuming every month has 30 days.
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        next_year = year + (month == 12)
        next_month = 1 if month == 12 else month + 1
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
        yield start, end
        year, month = next_year, next_month

# Audit every month from January 2025 through September 2026.
months = list(month_range(2025, 1, 2026, 9))
rows = []

for sensor_id, name in SENSORS.items():
    print(f"\nChecking {name} (sensor {sensor_id})")

    for start, end in months:
        try:
            payload = get_json(
                f"/sensors/{sensor_id}/hours",
                {
                    "datetime_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "datetime_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "limit": 1000,
                    "page": 1,
                },
            )
            readings = payload.get("results", [])

            # Count returned hourly aggregates; 1000 is the per-request cap.
            row = {
                "sensor_id": sensor_id,
                "station": name,
                "month": start.strftime("%Y-%m"),
                "hourly_records_returned": len(readings),
                "at_api_limit": len(readings) == 1000,
                "status": "OK",
            }
        except Exception as exc:
            row = {
                "sensor_id": sensor_id,
                "station": name,
                "month": start.strftime("%Y-%m"),
                "hourly_records_returned": "",
                "at_api_limit": "",
                "status": f"ERROR: {type(exc).__name__}",
            }

        rows.append(row)
        print(
            f"  {row['month']}: {row['hourly_records_returned']} "
            f"records | {row['status']}"
        )
        time.sleep(0.1)

# Save the monthly counts so we can compare coverage objectively.
output = os.path.expanduser("~/openaq_monthly_coverage.csv")
with open(output, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\nMonthly coverage audit saved to:", output)
print("Note: zero records indicate no returned data for that month.")
print("A count of 1000 reaches the API limit and needs pagination.")
