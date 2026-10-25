#!/usr/bin/env python3
"""Check the local runtime before training or serving AirCast India."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aircast.paths import discover_spark_csv, features_dir, raw_hourly_path
from aircast.spark_session import detect_java_home


def main() -> int:
    errors: list[str] = []
    print(f"Python: {sys.version}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11 or newer is required.")
    java = detect_java_home()
    print(f"JAVA_HOME candidate: {java or 'not found'}")
    if not java:
        errors.append("Java 17 is required for PySpark. Install openjdk@17 and set JAVA_HOME.")
    try:
        import pyspark

        print(f"PySpark: {pyspark.__version__}")
    except Exception as exc:
        errors.append(f"PySpark is not importable: {exc}")
    raw = raw_hourly_path()
    print(f"Raw hourly file: {raw} exists={raw.exists()}")
    if not raw.exists():
        errors.append(f"Missing raw dataset: {raw}")
    try:
        feature_csv = discover_spark_csv(features_dir())
        print(f"Feature CSV: {feature_csv}")
    except FileNotFoundError as exc:
        errors.append(str(exc))
    print(f"java executable: {shutil.which('java')}")
    if errors:
        print("\nEnvironment is not ready:")
        for item in errors:
            print(" -", item)
        return 1
    print("\nEnvironment looks ready for training and serving.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
