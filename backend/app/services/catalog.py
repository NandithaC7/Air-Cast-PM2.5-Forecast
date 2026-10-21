from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any

import pandas as pd

from aircast.constants import HAZARD_THRESHOLD_UG_M3, MIN_VALID_HOURS, TIMEZONE
from aircast.io import load_cleaned_hourly, load_daily_valid, load_model_features, load_station_metadata
from aircast.paths import cleaned_hourly_dir, daily_valid_dir, discover_spark_csv, features_dir, raw_hourly_path


def _iso(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    return text if text and text != "NaT" else None


def _file_stamp(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


class DataCatalog:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.features = load_model_features()
        self.daily = load_daily_valid()
        self.hourly = load_cleaned_hourly()
        self.metadata = load_station_metadata()
        self.hourly["timestamp_local"] = pd.to_datetime(self.hourly["timestamp_local"], utc=False, errors="coerce")
        self.hourly["timestamp_utc"] = pd.to_datetime(self.hourly["timestamp_utc"], utc=True, errors="coerce")

    @cached_property
    def stations(self) -> list[dict[str, Any]]:
        meta = self.metadata
        by_sensor: dict[int, dict[str, Any]] = {}
        if not meta.empty and "sensor_id" in meta.columns:
            for row in meta.to_dict(orient="records"):
                try:
                    sensor_id = int(row["sensor_id"])
                except (TypeError, ValueError):
                    continue
                city = row.get("city")
                if isinstance(city, str) and city.strip() in {"", "India"}:
                    city = None
                by_sensor[sensor_id] = {
                    "city": city,
                    "provider": row.get("provider_name"),
                    "latitude": _finite(row.get("latitude")),
                    "longitude": _finite(row.get("longitude")),
                    "timezone": row.get("timezone") or TIMEZONE,
                }
        rows = (
            self.features.groupby(["sensor_id", "station"], as_index=False)
            .agg(first_date=("local_date", "min"), last_date=("local_date", "max"), rows=("label", "size"))
            .sort_values("station")
        )
        stations = []
        for row in rows.itertuples():
            extra = by_sensor.get(int(row.sensor_id), {})
            stations.append(
                {
                    "location_id": int(row.sensor_id),
                    "sensor_id": int(row.sensor_id),
                    "name": row.station,
                    "city": extra.get("city"),
                    "provider": extra.get("provider"),
                    "latitude": extra.get("latitude"),
                    "longitude": extra.get("longitude"),
                    "timezone": extra.get("timezone") or TIMEZONE,
                    "first_feature_date": row.first_date.isoformat(),
                    "last_feature_date": row.last_date.isoformat(),
                    "feature_rows": int(row.rows),
                }
            )
        return stations

    def station_or_none(self, sensor_id: int) -> dict[str, Any] | None:
        return next((row for row in self.stations if row["location_id"] == sensor_id), None)

    def observations(self, sensor_id: int, start: str | None, end: str | None, page: int, page_size: int) -> dict[str, Any]:
        frame = self.hourly[self.hourly["sensor_id"] == sensor_id].copy()
        if start:
            frame = frame[frame["local_date"] >= date.fromisoformat(start)]
        if end:
            frame = frame[frame["local_date"] <= date.fromisoformat(end)]
        frame = frame.sort_values("timestamp_local")
        total = int(len(frame))
        start_idx = max(0, (page - 1) * page_size)
        page_rows = frame.iloc[start_idx : start_idx + page_size]
        items = []
        for row in page_rows.itertuples():
            items.append(
                {
                    "timestamp": _iso(row.timestamp_local) or _iso(row.timestamp_utc),
                    "location_id": int(row.sensor_id),
                    "station_name": row.station,
                    "pm25": _finite(row.pm25_value),
                    "unit": getattr(row, "unit", "µg/m³"),
                    "valid": True,
                }
            )
        unit = None
        if not page_rows.empty:
            unit = str(page_rows.iloc[0]["unit"])
        return {
            "station_id": sensor_id,
            "unit": unit,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": items,
        }

    def summary(self, sensor_id: int, start: str | None, end: str | None) -> dict[str, Any]:
        hourly = self.hourly[self.hourly["sensor_id"] == sensor_id].copy()
        daily = self.daily[self.daily["sensor_id"] == sensor_id].copy()
        if start:
            start_d = date.fromisoformat(start)
            hourly = hourly[hourly["local_date"] >= start_d]
            daily = daily[daily["local_date"] >= start_d]
        if end:
            end_d = date.fromisoformat(end)
            hourly = hourly[hourly["local_date"] <= end_d]
            daily = daily[daily["local_date"] <= end_d]
        daily = daily.sort_values("local_date")
        hourly = hourly.sort_values("timestamp_local")
        latest_obs = None
        if not hourly.empty:
            last = hourly.iloc[-1]
            latest_obs = {
                "timestamp": _iso(last["timestamp_local"]) or _iso(last["timestamp_utc"]),
                "pm25": _finite(last["pm25_value"]),
                "unit": last.get("unit") or "µg/m³",
            }
        features = self.features[self.features["sensor_id"] == sensor_id]
        first_feature_date = features["local_date"].min() if not features.empty else None
        latest_feature_date = features["local_date"].max() if not features.empty else None
        latest_daily = None
        if not daily.empty:
            last_d = daily.iloc[-1]
            latest_daily = {
                "date": last_d["local_date"].isoformat(),
                "pm25_daily_mean": _finite(last_d["daily_mean_pm25"]),
                "valid_hours": int(last_d["valid_reading_count"]),
                "exceeds": int(last_d["daily_mean_pm25"] > HAZARD_THRESHOLD_UG_M3),
            }
        coverage_start = daily["local_date"].min().isoformat() if not daily.empty else None
        coverage_end = daily["local_date"].max().isoformat() if not daily.empty else None
        missing_ts: list[str] = []
        expected_hours = None
        missing_hours = None
        if start and end:
            expected_hours, missing_hours, missing_ts = _missing_hours(hourly, date.fromisoformat(start), date.fromisoformat(end))
        return {
            "station_id": sensor_id,
            "unit": "µg/m³",
            "threshold_ug_m3": HAZARD_THRESHOLD_UG_M3,
            "min_hours_per_day": MIN_VALID_HOURS,
            "latest_observation": latest_obs,
            "latest_daily_mean": latest_daily,
            "first_feature_date": first_feature_date.isoformat() if first_feature_date else None,
            "latest_feature_date": latest_feature_date.isoformat() if latest_feature_date else None,
            "freshness": {
                "latest_observation_at": latest_obs["timestamp"] if latest_obs else None,
                "coverage_start": coverage_start,
                "coverage_end": coverage_end,
            },
            "quality": {
                "valid_readings": int(len(hourly)),
                "invalid_readings": 0,
                "missing_hours": missing_hours,
                "expected_hours": expected_hours,
                "latest_timestamp": latest_obs["timestamp"] if latest_obs else None,
                "missing_hour_timestamps": missing_ts[:50] if missing_ts else [],
            },
            "daily_series": [
                {
                    "date": row.local_date.isoformat(),
                    "pm25_daily_mean": _finite(row.daily_mean_pm25),
                    "valid_hours": int(row.valid_reading_count),
                    "exceeds": int(row.daily_mean_pm25 > HAZARD_THRESHOLD_UG_M3),
                }
                for row in daily.itertuples()
            ],
        }

    def overview(self) -> dict[str, Any]:
        raw = raw_hourly_path(self.root)
        return {
            "stations": int(self.features["station"].nunique()),
            "labelled_station_days": int(len(self.features)),
            "hazard_positive": int((self.features["label"] == 1).sum()),
            "hazard_negative": int((self.features["label"] == 0).sum()),
            "valid_hourly_observations": int(len(self.hourly)),
            "eligible_station_days": int(len(self.daily)),
            "raw_hourly_path_exists": raw.exists(),
            "raw_hourly_bytes": raw.stat().st_size if raw.exists() else None,
            "first_feature_date": self.features["local_date"].min().isoformat(),
            "last_feature_date": self.features["local_date"].max().isoformat(),
            "latest_observation_date": self.hourly["local_date"].max().isoformat() if not self.hourly.empty else None,
            "hazard_threshold_ug_m3": HAZARD_THRESHOLD_UG_M3,
            "min_hours_per_day": MIN_VALID_HOURS,
            "timezone": TIMEZONE,
        }

    def latest_feature_row(self, sensor_id: int) -> pd.Series | None:
        frame = self.features[self.features["sensor_id"] == sensor_id]
        if frame.empty:
            return None
        return frame.sort_values("local_date").iloc[-1]

    def feature_row(self, sensor_id: int, local_day: date) -> pd.Series | None:
        frame = self.features[
            (self.features["sensor_id"] == sensor_id) & (self.features["local_date"] == local_day)
        ]
        if frame.empty:
            return None
        return frame.iloc[0]

    def pipeline_status(self, models_ready: bool, preferred: str | None) -> dict[str, Any]:
        raw = raw_hourly_path(self.root)
        hourly = discover_spark_csv(cleaned_hourly_dir(self.root))
        daily = discover_spark_csv(daily_valid_dir(self.root))
        features = discover_spark_csv(features_dir(self.root))
        stages = [
            _stage("openaq_api", raw.exists(), _file_stamp(raw), int(raw.stat().st_size) if raw.exists() else None, "Expanded OpenAQ PM2.5 archive on disk."),
            _stage("ingestion", raw.exists(), _file_stamp(raw), int(self.overview()["valid_hourly_observations"]), "Raw hourly file present."),
            _stage("validation", hourly.exists(), _file_stamp(hourly), int(len(self.hourly)), "Cleaned hourly Spark output."),
            _stage("pyspark", features.exists(), _file_stamp(features), int(len(self.features)), "Daily aggregation, labels, and leakage-safe features."),
            _stage(
                "forecast_api",
                models_ready,
                _file_stamp(self.root / "models" / "inference_bundle.json"),
                4 if models_ready else 0,
                f"Preferred model {preferred}." if models_ready and preferred else "Trained artifacts not loaded.",
            ),
        ]
        return {"generated_at": datetime.now().astimezone().isoformat(), "stages": stages}


def _stage(stage_id: str, ok: bool, stamp: str | None, records: int | None, detail: str) -> dict[str, Any]:
    return {
        "id": stage_id,
        "status": "completed" if ok else "delayed",
        "detail": detail,
        "last_success_at": stamp if ok else None,
        "latest_observation_at": stamp if ok else None,
        "records": records,
        "last_error": None if ok else f"{stage_id} output is not available.",
        "last_processing_run_at": stamp,
    }


def _finite(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _missing_hours(hourly: pd.DataFrame, start: date, end: date) -> tuple[int, int, list[str]]:
    if end < start:
        return 0, 0, []
    expected = []
    cursor = datetime.combine(start, time.min)
    last = datetime.combine(end, time(23, 0))
    while cursor <= last:
        expected.append(cursor)
        cursor += timedelta(hours=1)
    have = set()
    if "timestamp_local" in hourly and not hourly.empty:
        stamps = pd.to_datetime(hourly["timestamp_local"], errors="coerce")
        for value in stamps.dropna():
            have.add(value.replace(minute=0, second=0, microsecond=0).to_pydatetime().replace(tzinfo=None))
    missing = [stamp.isoformat() for stamp in expected if stamp not in have]
    return len(expected), len(missing), missing
