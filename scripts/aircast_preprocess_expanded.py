import os
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

# Input and output paths. The raw input file is never overwritten.
INPUT = "/mnt/bda-share/bda proj/Air Cast India/data/raw/aircast_pm25_hourly_expanded.csv"
OUT = "/mnt/bda-share/bda proj/Air Cast India/preprocessed/expanded"

# Project settings: these are configurable project choices.
MIN_VALID_HOURS = 18
HAZARD_THRESHOLD = 60.0

# Force local filesystem access, since this stage does not require HDFS.
spark = (
    SparkSession.builder
    .appName("AirCast-Preprocessing")
    .master("local[2]")
    .config("spark.sql.session.timeZone", "Asia/Kolkata")
    .config("spark.hadoop.fs.defaultFS", "file:///")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

# Read all CSV fields as strings so we can validate them explicitly.
raw = (
    spark.read
    .option("header", True)
    .option("inferSchema", False)
    .csv("file://" + os.path.abspath(INPUT))
)

# Parse the measurement and check that the timestamp strings are usable.
# The first 10 characters of timestamp_local give its local calendar date.
# This avoids shifting a UTC timestamp across an Indian midnight.
parsed = (
    raw
    .withColumn("pm25_value", F.col("value").cast("double"))
    .withColumn(
        "local_timestamp_parsed",
        F.to_timestamp("timestamp_local")
    )
    .withColumn(
        "local_date",
        F.to_date(F.substring("timestamp_local", 1, 10), "yyyy-MM-dd")
    )
)

# A record is valid only if its value is numeric and non-negative,
# its local timestamp/date is valid, and its unit is the expected unit.
valid_condition = (
    F.col("pm25_value").isNotNull()
    & (~F.isnan("pm25_value"))
    & (F.col("pm25_value") >= 0)
    & F.col("local_timestamp_parsed").isNotNull()
    & F.col("local_date").isNotNull()
    & (F.col("unit") == "µg/m³")
    & F.col("sensor_id").isNotNull()
    & F.col("station").isNotNull()
)

# Report raw-data quality before excluding anything.
raw_count = raw.count()
invalid_count = parsed.filter(~valid_condition).count()
raw_negative_value_count = parsed.filter(
    F.col("pm25_value").isNotNull() & (F.col("pm25_value") < 0)
).count()
null_or_non_numeric_count = parsed.filter(
    F.col("pm25_value").isNull() | F.isnan("pm25_value")
).count()

# Retain only valid records and remove duplicate sensor/timestamp pairs.
valid = parsed.filter(valid_condition)

before_dedup = valid.count()
valid = valid.dropDuplicates(["sensor_id", "timestamp_utc"])
after_dedup = valid.count()
duplicates_removed = before_dedup - after_dedup

# Keep useful source fields and a numeric PM2.5 column.
cleaned_hourly = valid.select(
    "timestamp_utc",
    "timestamp_local",
    "period_end_utc",
    "local_date",
    "pm25_value",
    "unit",
    "sensor_id",
    "station",
    "month_requested"
)

# Aggregate only valid readings into daily station-level statistics.
daily_all = (
    cleaned_hourly
    .groupBy("sensor_id", "station", "local_date")
    .agg(
        F.count("pm25_value").alias("valid_reading_count"),
        F.avg("pm25_value").alias("daily_mean_pm25"),
        F.min("pm25_value").alias("daily_min_pm25"),
        F.max("pm25_value").alias("daily_max_pm25")
    )
)

# Enforce the required minimum of 18 valid hourly readings per day.
daily_valid = daily_all.filter(
    F.col("valid_reading_count") >= MIN_VALID_HOURS
)

# Match each day only to the following calendar day for the same sensor.
# This avoids incorrectly labelling a day using a later date when
# intermediate days are missing or fail the coverage rule.
tomorrow = daily_valid.select(
    "sensor_id",
    F.date_sub(F.col("local_date"), 1).alias("local_date"),
    F.col("daily_mean_pm25").alias("next_day_mean_pm25"),
    F.col("valid_reading_count").alias("next_day_valid_reading_count")
)

labelled = (
    daily_valid
    .join(tomorrow, ["sensor_id", "local_date"], "left")
    .withColumn(
        "hazard_threshold_pm25",
        F.lit(HAZARD_THRESHOLD)
    )
    .withColumn(
        "next_day_hazard",
        F.when(
            F.col("next_day_mean_pm25").isNull(),
            F.lit(None).cast("integer")
        ).otherwise(
            (F.col("next_day_mean_pm25") > HAZARD_THRESHOLD).cast("integer")
        )
    )
)

# Exclude rows whose following calendar day has no qualifying daily mean.
# Such rows cannot be assigned a reliable supervised-learning target.
next_day_dataset = labelled.filter(
    F.col("next_day_hazard").isNotNull()
)

# Collect key counts for a transparent preprocessing report.
daily_total = daily_all.count()
daily_eligible = daily_valid.count()
labelled_count = next_day_dataset.count()
positive_count = next_day_dataset.filter(
    F.col("next_day_hazard") == 1
).count()
negative_class_count = next_day_dataset.filter(
    F.col("next_day_hazard") == 0
).count()
unlabelled_count = labelled.filter(
    F.col("next_day_hazard").isNull()
).count()

print("\n========== AIRCAST PREPROCESSING REPORT ==========")
print(f"Spark version: {spark.version}")
print(f"Session timezone: {spark.conf.get('spark.sql.session.timeZone')}")
print(f"Raw hourly records: {raw_count}")
print(f"Invalid records excluded: {invalid_count}")
print(f"Negative PM2.5 measurements found: {raw_negative_value_count}")
print(f"Null/non-numeric values found: {null_or_non_numeric_count}")
print(f"Duplicate sensor/timestamp records removed: {duplicates_removed}")
print(f"Cleaned hourly records: {after_dedup}")
print(f"All station-days before coverage filter: {daily_total}")
print(f"Station-days with >= {MIN_VALID_HOURS} valid readings: {daily_eligible}")
print(f"Rows with a valid next-calendar-day label: {labelled_count}")
print(f"Positive next-day hazard cases: {positive_count}")
print(f"Negative next-day hazard cases: {negative_class_count}")
print(f"Rows excluded because next day was unavailable: {unlabelled_count}")

print("\n========== DAILY COVERAGE BY STATION ==========")
daily_all.groupBy("station").agg(
    F.count("*").alias("all_station_days"),
    F.sum(
        (F.col("valid_reading_count") >= MIN_VALID_HOURS).cast("integer")
    ).alias("eligible_station_days"),
    F.min("local_date").alias("first_local_date"),
    F.max("local_date").alias("last_local_date")
).orderBy("station").show(truncate=False)

print("\n========== TARGET CLASS BALANCE ==========")
next_day_dataset.groupBy("next_day_hazard").count().orderBy(
    "next_day_hazard"
).show()

# Write each output as a Spark CSV directory. Each directory contains
# one or more part files and a success marker; it is not a single CSV file.
os.makedirs(OUT, exist_ok=True)

(
    cleaned_hourly
    .orderBy("sensor_id", "timestamp_utc")
    .coalesce(1)
    .write.mode("overwrite")
    .option("header", True)
    .csv("file://" + OUT + "/cleaned_hourly")
)

(
    daily_valid
    .orderBy("sensor_id", "local_date")
    .coalesce(1)
    .write.mode("overwrite")
    .option("header", True)
    .csv("file://" + OUT + "/daily_valid")
)

(
    next_day_dataset
    .orderBy("sensor_id", "local_date")
    .coalesce(1)
    .write.mode("overwrite")
    .option("header", True)
    .csv("file://" + OUT + "/next_day_dataset")
)

# Save the report as a small text file for review documentation.
with open(os.path.join(OUT, "preprocessing_summary.txt"), "w") as report:
    report.write("AirCast India preprocessing summary\n")
    report.write(f"Raw records: {raw_count}\n")
    report.write(f"Invalid records excluded: {invalid_count}\n")
    report.write(f"Duplicate records removed: {duplicates_removed}\n")
    report.write(f"Cleaned hourly records: {after_dedup}\n")
    report.write(f"All station-days: {daily_total}\n")
    report.write(f"Eligible station-days: {daily_eligible}\n")
    report.write(f"Labelled rows: {labelled_count}\n")
    report.write(f"Positive cases: {positive_count}\n")
    report.write(f"Negative PM2.5 measurements: {raw_negative_value_count}\n")
    report.write(f"Negative hazard cases: {negative_class_count}\n")
    report.write(f"Unlabelled rows: {unlabelled_count}\n")
    report.write(f"Threshold: {HAZARD_THRESHOLD} µg/m³\n")
    report.write(f"Minimum readings/day: {MIN_VALID_HOURS}\n")

print(f"\nOutput directory: {OUT}")
print("Preprocessing outputs written successfully.")

spark.stop()
