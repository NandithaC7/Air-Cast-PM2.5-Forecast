import csv
import os
import time
import requests
from datetime import datetime, timedelta, timezone

BASE = "https://api.openaq.org/v3"
API_KEY = os.environ["OPENAQ_API_KEY"]
HEADERS = {"X-API-Key": API_KEY}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def get_json(path, params=None):
    """Request JSON from OpenAQ, retrying temporary failures."""
    url = f"{BASE}{path}"
    for attempt in range(4):
        try:
            response = SESSION.get(url, params=params, timeout=30)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OpenAQ request failed: {path}")

def utc_text(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# Retrieve locations with PM2.5 in India. Limit 1000 is the API page maximum.
payload = get_json(
    "/locations",
    {"iso": "IN", "parameters_id": 2, "limit": 1000, "page": 1},
)
locations = payload.get("results", [])
print("Location records returned:", len(locations))
print("API result count:", payload.get("meta", {}).get("found"))

# Extract PM2.5 sensor candidates from sensor metadata embedded in locations.
candidates = []
for loc in locations:
    sensors = loc.get("sensors") or []
    for sensor in sensors:
        parameter = sensor.get("parameter") or {}
        name = str(parameter.get("name") or sensor.get("name") or "").lower()
        parameter_id = parameter.get("id")
        is_pm25 = parameter_id == 2 or name in {
            "pm25", "pm2.5", "pm2_5", "pm₂.₅"
        }
        if not is_pm25:
            continue

        candidates.append({
            "location_id": loc.get("id"),
            "location": loc.get("name"),
            "city": loc.get("locality") or "",
            "sensor_id": sensor.get("id"),
            "sensor_name": sensor.get("name") or name,
            "sensor_first": (
                (sensor.get("datetimeFirst") or {}).get("utc", "")
            ),
            "sensor_last": (
                (sensor.get("datetimeLast") or {}).get("utc", "")
            ),
            "location_last": (
                (loc.get("datetimeLast") or {}).get("utc", "")
            ),
            "timezone": loc.get("timezone") or "",
        })

# If the location response omits embedded sensors, use the dedicated endpoint.
if not candidates:
    print("Embedded sensor metadata unavailable; checking location sensor endpoints.")
    for index, loc in enumerate(locations, start=1):
        detail = get_json(f"/locations/{loc['id']}/sensors", {"limit": 1000})
        for sensor in detail.get("results", []):
            parameter = sensor.get("parameter") or {}
            name = str(parameter.get("name") or sensor.get("name") or "").lower()
            if parameter.get("id") != 2 and name not in {
                "pm25", "pm2.5", "pm2_5", "pm₂.₅"
            }:
                continue
            candidates.append({
                "location_id": loc.get("id"),
                "location": loc.get("name"),
                "city": loc.get("locality") or "",
                "sensor_id": sensor.get("id"),
                "sensor_name": sensor.get("name") or name,
                "sensor_first": (
                    (sensor.get("datetimeFirst") or {}).get("utc", "")
                ),
                "sensor_last": (
                    (sensor.get("datetimeLast") or {}).get("utc", "")
                ),
                "location_last": (
                    (loc.get("datetimeLast") or {}).get("utc", "")
                ),
                "timezone": loc.get("timezone") or "",
            })
        if index % 50 == 0:
            print(f"Inspected sensor metadata for {index} locations")

# Prefer sensors whose own metadata reports recent activity.
def last_time(candidate):
    value = candidate["sensor_last"] or candidate["location_last"]
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)

candidates.sort(key=last_time, reverse=True)
print("PM2.5 sensor candidates:", len(candidates))

# Probe up to 30 candidates over the last seven days.
# A real returned hourly record is stronger evidence than metadata alone.
now = datetime.now(timezone.utc)
start = now - timedelta(days=7)
audited = []
tested = set()

for candidate in candidates:
    sensor_id = candidate.get("sensor_id")
    if not sensor_id or sensor_id in tested:
        continue
    tested.add(sensor_id)

    try:
        data = get_json(
            f"/sensors/{sensor_id}/hours",
            {
                "datetime_from": utc_text(start),
                "datetime_to": utc_text(now),
                "limit": 100,
                "page": 1,
            },
        )
        readings = data.get("results", [])
        candidate["recent_hours_returned"] = len(readings)
        candidate["latest_reading_utc"] = ""
        candidate["latest_value"] = ""

        if readings:
            latest = max(
                readings,
                key=lambda r: (
                    ((r.get("period") or {}).get("datetimeFrom") or {}).get("utc", "")
                ),
            )
            period = latest.get("period") or {}
            dt = period.get("datetimeFrom") or {}
            candidate["latest_reading_utc"] = dt.get("utc", "")
            candidate["latest_value"] = latest.get("value", "")

        candidate["audit_status"] = (
            "RECENT_READINGS_FOUND" if readings else "NO_READINGS_IN_WINDOW"
        )
    except Exception as exc:
        candidate["recent_hours_returned"] = ""
        candidate["latest_reading_utc"] = ""
        candidate["latest_value"] = ""
        candidate["audit_status"] = f"API_ERROR: {type(exc).__name__}"

    audited.append(candidate)
    print(
        f"[{len(audited):02d}] {candidate.get('location')} | "
        f"sensor={sensor_id} | "
        f"recent hours={candidate.get('recent_hours_returned')} | "
        f"{candidate['audit_status']}"
    )

    if len(audited) >= 30:
        break

# Save the audit results for review before any full download.
output = os.path.expanduser("~/openaq_station_shortlist.csv")
fields = [
    "location_id", "location", "city", "sensor_id", "sensor_name",
    "sensor_first", "sensor_last", "location_last", "timezone",
    "recent_hours_returned", "latest_reading_utc", "latest_value",
    "audit_status",
]
with open(output, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(audited)

print("\nAudit complete.")
print("Audited sensors:", len(audited))
print("CSV saved to:", output)
print("A sensor with no readings in the window is not automatically invalid;")
print("we will inspect metadata and API errors before excluding any candidate.")
