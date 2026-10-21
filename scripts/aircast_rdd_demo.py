import csv
import os
from pyspark.sql import SparkSession

# Read the existing raw OpenAQ dataset; do not modify the source CSV.
INPUT = os.path.expanduser("~/aircast_pm25_hourly_expanded.csv")

# Start a local Spark session with two worker threads.
spark = (
    SparkSession.builder
    .appName("AirCast-RDD-Demonstration")
    .master("local[2]")
    .config("spark.sql.session.timeZone", "Asia/Kolkata")
    .config("spark.hadoop.fs.defaultFS", "file:///")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")
sc = spark.sparkContext

# Read the CSV as text lines, which creates the initial RDD.
lines = sc.textFile("file://" + os.path.abspath(INPUT))

# Remove the CSV header using the first line's index.
data_lines = (
    lines.zipWithIndex()
    .filter(lambda item: item[1] > 0)
    .map(lambda item: item[0])
)

# Parse each CSV line and extract station, value, unit and sensor ID.
# csv.reader handles quoted fields more safely than splitting on commas.
def parse_row(line):
    try:
        fields = next(csv.reader([line]))
        if len(fields) < 8:
            return None

        station = fields[7].strip()
        value = float(fields[3])
        unit = fields[4].strip()
        sensor_id = fields[6].strip()

        # Reject missing station/sensor IDs, invalid values and wrong units.
        if (
            not station
            or not sensor_id
            or value < 0
            or unit != "µg/m³"
        ):
            return None

        return (station, value)
    except (ValueError, csv.Error, IndexError):
        return None

# Transformation: parse records and filter invalid measurements.
# Cache the validated RDD because multiple actions will reuse it.
valid_readings = (
    data_lines
    .map(parse_row)
    .filter(lambda row: row is not None)
    .repartition(4)  # Shuffle validated readings into four RDD partitions.
    .cache()
)

# Action 1: count the validated hourly records.
valid_count = valid_readings.count()

# Transform into key-value pairs: station -> (PM2.5 sum, reading count).
station_pairs = valid_readings.map(
    lambda row: (row[0], (row[1], 1))
)

# Transformation: aggregate sums and counts for each station.
station_totals = station_pairs.reduceByKey(
    lambda left, right: (left[0] + right[0], left[1] + right[1])
)

# Action 2: collect the small station-level aggregate for display.
results = station_totals.collect()

# Print evidence of RDD execution and aggregation.
print("\n========== AIRCAST RDD DEMONSTRATION ==========")
print("Input file:", INPUT)
print("Valid hourly records:", valid_count)
print("RDD partition count:", valid_readings.getNumPartitions())
print("\nRDD lineage / execution plan:")
print(valid_readings.toDebugString().decode("utf-8", errors="replace"))

print("\n========== STATION AGGREGATES ==========")
print("Station | Valid readings | Mean PM2.5 (µg/m³)")
for station, (total, count) in sorted(results):
    print(f"{station} | {count} | {total / count:.2f}")

# Release cached RDD resources and stop Spark cleanly.
valid_readings.unpersist()
spark.stop()
