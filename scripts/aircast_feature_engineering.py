import math
from pathlib import Path

from pyspark.sql import SparkSession, Window, functions as F

# All paths refer to the expanded dataset, not the archived original data.
ROOT = Path("/mnt/bda-share/bda proj/Air Cast India")
DAILY_DIR = ROOT / "preprocessed/expanded/daily_valid"
LABEL_DIR = ROOT / "preprocessed/expanded/next_day_dataset"
OUTPUT_DIR = ROOT / "preprocessed/expanded/model_features"
REPORT_PATH = ROOT / "outputs/feature_engineering_summary.txt"

# Stop rather than silently overwrite an earlier feature-engineering run.
if OUTPUT_DIR.exists():
    raise SystemExit(
        f"Output already exists: {OUTPUT_DIR}\n"
        "Inspect it first or choose a new output directory."
    )

# Start Spark in local mode and use the Indian local calendar.
spark = (
    SparkSession.builder
    .appName("AirCast-Feature-Engineering")
    .master("local[2]")
    .config("spark.sql.session.timeZone", "Asia/Kolkata")
    .config("spark.hadoop.fs.defaultFS", "file:///")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

try:
    # Read the daily aggregates and labels created by expanded preprocessing.
    daily = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(str(DAILY_DIR))
        .withColumn("local_date", F.to_date("local_date"))
    )

    labels = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(str(LABEL_DIR))
        .withColumn("local_date", F.to_date("local_date"))
        .select(
            "sensor_id", "local_date",
            F.col("next_day_hazard").cast("double").alias("label")
        )
    )

    # Keep the current day's measurements as the base feature row.
    base = daily.select(
        "sensor_id", "station", "local_date",
        F.col("valid_reading_count").cast("double").alias("valid_reading_count"),
        F.col("daily_mean_pm25").cast("double").alias("daily_mean_pm25"),
        F.col("daily_min_pm25").cast("double").alias("daily_min_pm25"),
        F.col("daily_max_pm25").cast("double").alias("daily_max_pm25")
    )

    # Create lag features by joining on exact calendar dates.
    # For lag k, the source date must be exactly k calendar days earlier.
    for k in (1, 2, 3):
        lag = base.select(
            "sensor_id",
            F.date_add("local_date", k).alias("local_date"),
            F.col("daily_mean_pm25").alias(f"pm25_lag{k}")
        )
        base = base.join(lag, ["sensor_id", "local_date"], "left")

    # Rolling average across the current date and previous six calendar days.
    # The date-based range prevents missing days from shifting the window.
    day_number = F.datediff("local_date", F.lit("1970-01-01"))
    window_7d = (
        Window.partitionBy("sensor_id")
        .orderBy(day_number)
        .rangeBetween(-6, 0)
    )

    base = (
        base.withColumn("_n7", F.count("daily_mean_pm25").over(window_7d))
        .withColumn("_avg7", F.avg("daily_mean_pm25").over(window_7d))
        .withColumn(
            "pm25_roll7",
            F.when(F.col("_n7") >= 4, F.col("_avg7"))
        )
        .drop("_n7", "_avg7")
    )

    # Add current-day change and calendar features.
    month = F.month("local_date")
    base = (
        base
        .withColumn(
            "pm25_delta1",
            F.col("daily_mean_pm25") - F.col("pm25_lag1")
        )
        .withColumn(
            "month_sin",
            F.sin(F.lit(2 * math.pi) * month / F.lit(12.0))
        )
        .withColumn(
            "month_cos",
            F.cos(F.lit(2 * math.pi) * month / F.lit(12.0))
        )
        .withColumn(
            "is_winter",
            F.when(month.isin(11, 12, 1, 2), 1.0).otherwise(0.0)
        )
        .withColumn("dow", F.dayofweek("local_date").cast("double"))
    )

    # Join only the already validated next-day labels.
    # Do not bring future-day measurements into the predictor columns.
    featured = base.join(
        labels, ["sensor_id", "local_date"], "inner"
    )

    # Use an explicit output schema to prevent accidental target leakage.
    output_columns = [
        "sensor_id", "station", "local_date",
        "valid_reading_count",
        "daily_mean_pm25", "daily_min_pm25", "daily_max_pm25",
        "pm25_lag1", "pm25_lag2", "pm25_lag3",
        "pm25_roll7", "pm25_delta1",
        "month_sin", "month_cos", "is_winter", "dow",
        "label"
    ]
    featured = featured.select(*output_columns)

    # Compute actual counts and label balance before saving.
    row_count = featured.count()
    label_counts = {
        int(row["label"]): row["count"]
        for row in featured.groupBy("label").count().collect()
    }
    missing_lag1 = featured.filter(F.col("pm25_lag1").isNull()).count()
    missing_lag2 = featured.filter(F.col("pm25_lag2").isNull()).count()
    missing_lag3 = featured.filter(F.col("pm25_lag3").isNull()).count()
    missing_roll7 = featured.filter(F.col("pm25_roll7").isNull()).count()

    # Write the feature dataset as Spark CSV output with a header.
    featured.write.mode("errorifexists").option("header", True).csv(str(OUTPUT_DIR))

    # Record the feature definition, row count, label balance and missing lags.
    report = [
        "AirCast India feature-engineering summary",
        f"Input daily directory: {DAILY_DIR}",
        f"Input labels directory: {LABEL_DIR}",
        f"Output directory: {OUTPUT_DIR}",
        f"Labelled feature rows: {row_count}",
        f"Non-hazard labels (0): {label_counts.get(0, 0)}",
        f"Hazard labels (1): {label_counts.get(1, 0)}",
        f"Missing lag-1 values: {missing_lag1}",
        f"Missing lag-2 values: {missing_lag2}",
        f"Missing lag-3 values: {missing_lag3}",
        f"Missing rolling-7-day means: {missing_roll7}",
        "Predictors: current-day PM2.5 statistics, reading count, calendar-date lags,",
        "            rolling mean, daily change and calendar features.",
        "Target: next_day_hazard, renamed label.",
        "Future-day measurements are excluded from the predictor columns.",
        "Rolling window: current date and previous six calendar days; minimum 4 observations."
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print("\nFeature dataset saved successfully.")

finally:
    # Release Spark resources even if a validation or write step fails.
    spark.stop()
