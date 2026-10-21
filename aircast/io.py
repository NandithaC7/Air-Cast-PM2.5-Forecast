"""Load Spark-written CSV outputs with an explicit pandas schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aircast.constants import EXPECTED_FEATURE_SCHEMA, FEATURE_COLUMNS, LABEL_COLUMN
from aircast.paths import (
    cleaned_hourly_dir,
    daily_valid_dir,
    discover_spark_csv,
    features_dir,
    station_metadata_path,
)


def load_model_features(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or discover_spark_csv(features_dir())
    frame = pd.read_csv(csv_path)
    missing = [column for column in EXPECTED_FEATURE_SCHEMA if column not in frame.columns]
    if missing:
        raise ValueError(f"Feature file {csv_path} is missing columns: {missing}")
    frame["sensor_id"] = pd.to_numeric(frame["sensor_id"], errors="raise").astype("int64")
    frame["local_date"] = pd.to_datetime(frame["local_date"], errors="raise").dt.date
    for column in FEATURE_COLUMNS + [LABEL_COLUMN]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not set(frame[LABEL_COLUMN].dropna().unique()).issubset({0, 1, 0.0, 1.0}):
        raise ValueError("label must be binary {0, 1}.")
    frame[LABEL_COLUMN] = frame[LABEL_COLUMN].astype(int)
    return frame


def load_daily_valid(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or discover_spark_csv(daily_valid_dir())
    frame = pd.read_csv(csv_path)
    frame["sensor_id"] = pd.to_numeric(frame["sensor_id"], errors="raise").astype("int64")
    frame["local_date"] = pd.to_datetime(frame["local_date"], errors="raise").dt.date
    for column in ("valid_reading_count", "daily_mean_pm25", "daily_min_pm25", "daily_max_pm25"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_cleaned_hourly(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or discover_spark_csv(cleaned_hourly_dir())
    frame = pd.read_csv(csv_path)
    frame["sensor_id"] = pd.to_numeric(frame["sensor_id"], errors="raise").astype("int64")
    frame["local_date"] = pd.to_datetime(frame["local_date"], errors="coerce").dt.date
    frame["pm25_value"] = pd.to_numeric(frame["pm25_value"], errors="coerce")
    return frame


def load_station_metadata(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or station_metadata_path()
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)
