from aircast.constants import (
    EXPECTED_FEATURE_SCHEMA,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    PROHIBITED_PREDICTORS,
)
from aircast.io import load_model_features
from aircast.paths import discover_spark_csv, features_dir
from aircast.split import assign_partition, chronological_boundaries, unique_sorted_dates


def test_feature_columns_and_binary_label():
    frame = load_model_features()
    assert list(frame.columns) == EXPECTED_FEATURE_SCHEMA
    assert set(frame[LABEL_COLUMN].unique()).issubset({0, 1})
    assert frame[LABEL_COLUMN].notna().all()
    for column in FEATURE_COLUMNS:
        assert frame[column].dtype.kind in {"f", "i"}


def test_no_future_or_identifier_predictors():
    frame = load_model_features()
    for column in PROHIBITED_PREDICTORS:
        if column in {"sensor_id", "station", "local_date", "label"}:
            continue
        assert column not in frame.columns


def test_spark_part_file_is_discovered_dynamically():
    path = discover_spark_csv(features_dir())
    assert path.name.startswith("part-")
    assert path.suffix == ".csv"


def test_chronological_split_is_ordered_and_shared_by_date():
    frame = load_model_features()
    dates = unique_sorted_dates(frame)
    boundaries = chronological_boundaries(dates)
    assert boundaries["train"]["last_date"] < boundaries["validation"]["first_date"]
    assert boundaries["validation"]["last_date"] < boundaries["test"]["first_date"]
    partition = assign_partition(frame, boundaries)
    assert set(partition.unique()) == {"train", "validation", "test"}
    crossed = (
        frame.assign(partition=partition)
        .groupby("local_date")["partition"]
        .nunique()
    )
    assert (crossed == 1).all()
