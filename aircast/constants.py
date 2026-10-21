"""Project constants shared by preprocessing, training, serving, and tests."""

from __future__ import annotations

FEATURE_COLUMNS: list[str] = [
    "valid_reading_count",
    "daily_mean_pm25",
    "daily_min_pm25",
    "daily_max_pm25",
    "pm25_lag1",
    "pm25_lag2",
    "pm25_lag3",
    "pm25_roll7",
    "pm25_delta1",
    "month_sin",
    "month_cos",
    "is_winter",
    "dow",
]

IDENTIFIER_COLUMNS: list[str] = ["sensor_id", "station", "local_date"]
LABEL_COLUMN = "label"
PROHIBITED_PREDICTORS: list[str] = [
    "label",
    "next_day_mean_pm25",
    "next_day_hazard",
    "next_day_valid_reading_count",
    "sensor_id",
    "station",
    "local_date",
]

NULLABLE_FEATURE_COLUMNS: list[str] = [
    "pm25_lag1",
    "pm25_lag2",
    "pm25_lag3",
    "pm25_roll7",
    "pm25_delta1",
]

MISSING_INDICATOR_COLUMNS: list[str] = [f"{name}_missing" for name in NULLABLE_FEATURE_COLUMNS]
ASSEMBLED_FEATURE_COLUMNS: list[str] = FEATURE_COLUMNS + MISSING_INDICATOR_COLUMNS

EXPECTED_FEATURE_SCHEMA: list[str] = IDENTIFIER_COLUMNS + FEATURE_COLUMNS + [LABEL_COLUMN]

MODEL_KEYS: dict[str, str] = {
    "logistic_regression": "Logistic Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "linear_svm": "Linear SVM",
}

MODEL_ORDER: list[str] = list(MODEL_KEYS.keys())

HAZARD_THRESHOLD_UG_M3 = 60.0
MIN_VALID_HOURS = 18
TIMEZONE = "Asia/Kolkata"
POSITIVE_CLASS = 1
NEGATIVE_CLASS = 0
RANDOM_SEED = 42
ARTIFACT_VERSION = "1.0.0"

# Chronological split of unique local calendar dates.
TRAIN_DATE_FRACTION = 0.70
VALIDATION_DATE_FRACTION = 0.15
TEST_DATE_FRACTION = 0.15

# Predeclared selection rule, fixed before test metrics are inspected.
SELECTION_CRITERION = (
    "Choose the classifier with the highest validation-set F1-score for the "
    "hazard class (label=1). Break remaining ties with validation recall, then "
    "with the simpler estimator in this order: logistic_regression, "
    "decision_tree, linear_svm, random_forest. The untouched chronological "
    "test set is not used for model or threshold selection."
)

SELECTION_TIE_BREAK: list[str] = [
    "logistic_regression",
    "decision_tree",
    "linear_svm",
    "random_forest",
]

# Logistic Regression
LR_MAX_ITER = 100
LR_REG_PARAM = 0.10
LR_ELASTIC_NET = 0.0  # L2

# Decision Tree
DT_MAX_DEPTH = 6
DT_MIN_INSTANCES = 8
DT_IMPURITY = "gini"

# Random Forest
RF_NUM_TREES = 40
RF_MAX_DEPTH = 6
RF_MIN_INSTANCES = 8
RF_FEATURE_SUBSET = "sqrt"
RF_IMPURITY = "gini"

# Linear SVM
SVM_MAX_ITER = 100
SVM_REG_PARAM = 0.10
