"""Repository path helpers. Discover Spark part files instead of hardcoding names."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("AIRCAST_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def raw_hourly_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "data" / "raw" / "aircast_pm25_hourly_expanded.csv"


def expanded_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "preprocessed" / "expanded"


def features_dir(root: Path | None = None) -> Path:
    return expanded_dir(root) / "model_features"


def daily_valid_dir(root: Path | None = None) -> Path:
    return expanded_dir(root) / "daily_valid"


def cleaned_hourly_dir(root: Path | None = None) -> Path:
    return expanded_dir(root) / "cleaned_hourly"


def next_day_dir(root: Path | None = None) -> Path:
    return expanded_dir(root) / "next_day_dataset"


def station_metadata_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "outputs" / "openaq_station_enriched.csv"


def evaluation_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "outputs" / "model_evaluation"


def models_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "models"


def discover_spark_csv(directory: Path) -> Path:
    """Return the first Spark CSV part file in a directory.

    Spark writes `part-*.csv` plus `_SUCCESS` and optional checksum files.
    The part filename is generated per run and must not be hardcoded.
    """
    if not directory.exists():
        raise FileNotFoundError(f"Spark output directory does not exist: {directory}")
    parts = sorted(
        path
        for path in directory.glob("part-*.csv")
        if path.is_file() and not path.name.endswith(".crc")
    )
    if not parts:
        raise FileNotFoundError(
            f"No Spark CSV part file found in {directory}. "
            "Run the preprocessing / feature-engineering scripts first."
        )
    return parts[0]


def latest_evaluation_payload(root: Path | None = None) -> Path:
    return evaluation_dir(root) / "model_metrics.json"
