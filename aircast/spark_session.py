"""Local Spark session helpers for a single-machine run."""

from __future__ import annotations

import os
from pathlib import Path


def detect_java_home() -> str | None:
    existing = os.environ.get("JAVA_HOME")
    if existing and Path(existing).exists():
        return existing
    candidates = [
        Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"),
        Path("/opt/homebrew/opt/openjdk@17"),
        Path("/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"),
        Path("/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home"),
        Path("/usr/lib/jvm/java-17-openjdk-arm64"),
        Path("/usr/lib/jvm/java-17-openjdk-amd64"),
    ]
    for candidate in candidates:
        if (candidate / "bin" / "java").exists():
            return str(candidate)
    return None


def configure_runtime() -> dict[str, str]:
    java_home = detect_java_home()
    if java_home:
        os.environ["JAVA_HOME"] = java_home
        os.environ["PATH"] = str(Path(java_home) / "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    import sys

    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    return {
        "java_home": os.environ.get("JAVA_HOME", ""),
        "spark_local_ip": os.environ.get("SPARK_LOCAL_IP", ""),
        "python": sys.executable,
    }


def build_spark(app_name: str = "AirCast-India"):
    configure_runtime()
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[2]")
        .config("spark.sql.session.timeZone", "Asia/Kolkata")
        .config("spark.hadoop.fs.defaultFS", "file:///")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark
