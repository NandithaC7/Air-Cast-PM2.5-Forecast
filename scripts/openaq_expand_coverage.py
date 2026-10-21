import csv
import os
import time
import requests
from datetime import datetime

# Read the existing enriched shortlist; do not overwrite it.
INPUT = os.path.expanduser("~/openaq_station_enriched.csv")
OUTPUT = os.path.expanduser("~/openaq_expand_coverage.csv")
SUMMARY = os.path.expanduser("~/openaq_expand_coverage_summary.csv")

# Keep the six stations already in our dataset out of the new shortlist.
EXISTING_IDS = {
    "23534", "9320367", "13478101",
    "14499369", "15203555", "12235583"
}

# Audit completed calendar months only, avoiding a partial current month.
START = datetime(2025, 1, 1)
END_EXCLUSIVE = datetime(2026, 10, 1)

# OpenAQ v3 requires the API key in the request header.
API_KEY = os.environ.get("OPENAQ_API_KEY")
if not API_KEY:
    raise SystemExit("OPENAQ_API_KEY is not set; no requests were made.")

session = requests.Session()
session.headers.update({"X-API-Key": API_KEY})
BASE = "https://api.openaq.org/v3"

def get_json(path, params):
    response = session.get(
        BASE + path,
        params=params,
        timeout=45
    )
    response.raise_for_status()
    return response.json()

def month_starts(start, end):
    current = datetime(start.year, start.month, 1)
    while current < end:
        yield current
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

# Load candidates that have verified metadata and sufficiently early histories.
with open(INPUT, newline="", encoding="utf-8") as handle:
    candidates = list(csv.DictReader(handle))

selected = []
seen = set()

for row in candidates:
    sensor_id = row.get("verified_sensor_id") or row.get("sensor_id", "")
    first = row.get("sensor_first_utc") or row.get("sensor_first", "")

    if not sensor_id or sensor_id in EXISTING_IDS or sensor_id in seen:
        continue
    if row.get("metadata_status") != "OK":
        continue

    # Exclude sensors that began after January 2026 for this first audit.
    try:
        first_dt = datetime.fromisoformat(first.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        continue

    if first_dt.replace(tzinfo=None) >= datetime(2026, 2, 1):
        continue

    seen.add(sensor_id)
    selected.append({
        "sensor_id": sensor_id,
        "station": row.get("verified_location_name") or row.get("location", ""),
        "first": first,
        "last": row.get("sensor_last_utc") or row.get("sensor_last", ""),
    })

print("Additional candidate sensors to audit:", len(selected))
print("Audit window: January 2025 through September 2026")

details = []
for index, sensor in enumerate(selected, start=1):
    print(f"\n[{index}/{len(selected)}] {sensor['station']} "
          f"(sensor {sensor['sensor_id']})")

    for month in month_starts(START, END_EXCLUSIVE):
        if month < datetime.fromisoformat(
            sensor["first"].replace("Z", "+00:00")
        ).replace(tzinfo=None).replace(day=1):
            continue

        if month.month == 12:
            month_end = datetime(month.year + 1, 1, 1)
        else:
            month_end = datetime(month.year, month.month + 1, 1)

        params = {
            "datetime_from": month.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datetime_to": month_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 1000,
            "page": 1,
        }

        try:
            payload = get_json(
                f"/sensors/{sensor['sensor_id']}/hours",
                params
            )
            readings = payload.get("results", [])
            count = len(readings)

            # A full page means the result may be capped; flag it for review.
            details.append({
                "sensor_id": sensor["sensor_id"],
                "station": sensor["station"],
                "month": month.strftime("%Y-%m"),
                "record_count_returned": count,
                "possible_api_cap": count >= 1000,
                "status": "OK",
            })
        except requests.RequestException as exc:
            details.append({
                "sensor_id": sensor["sensor_id"],
                "station": sensor["station"],
                "month": month.strftime("%Y-%m"),
                "record_count_returned": "",
                "possible_api_cap": "",
                "status": f"ERROR: {type(exc).__name__}",
            })

        # Avoid sending requests too quickly.
        time.sleep(0.15)

# Save detailed monthly counts for reproducibility.
with open(OUTPUT, "w", newline="", encoding="utf-8") as handle:
    fields = [
        "sensor_id", "station", "month",
        "record_count_returned", "possible_api_cap", "status"
    ]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(details)

# Summarize how many months returned records for each candidate.
summary = []
for sensor in selected:
    rows = [
        row for row in details
        if row["sensor_id"] == sensor["sensor_id"]
    ]
    successful = [
        row for row in rows
        if row["status"] == "OK"
    ]
    months_with_data = sum(
        1 for row in successful
        if int(row["record_count_returned"] or 0) > 0
    )
    total_records = sum(
        int(row["record_count_returned"] or 0)
        for row in successful
    )
    errors = sum(1 for row in rows if row["status"] != "OK")

    summary.append({
        "sensor_id": sensor["sensor_id"],
        "station": sensor["station"],
        "first_reading_utc": sensor["first"],
        "last_reading_utc": sensor["last"],
        "months_with_data": months_with_data,
        "months_checked": len(rows),
        "records_returned_across_months": total_records,
        "months_with_errors": errors,
    })

summary.sort(
    key=lambda row: (
        row["months_with_data"],
        row["records_returned_across_months"]
    ),
    reverse=True
)

with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0].keys())
                            if summary else [
                                "sensor_id", "station", "months_with_data"
                            ])
    writer.writeheader()
    writer.writerows(summary)

print("\n========== HISTORICAL COVERAGE RANKING ==========")
for row in summary:
    print(
        f"{row['station']} | sensor={row['sensor_id']} | "
        f"months={row['months_with_data']}/{row['months_checked']} | "
        f"records={row['records_returned_across_months']} | "
        f"errors={row['months_with_errors']}"
    )

print("\nDetailed monthly audit:", OUTPUT)
print("Coverage ranking:", SUMMARY)
print("Counts are returned API records, not guaranteed complete hourly coverage.")
