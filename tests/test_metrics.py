import numpy as np

from aircast.inference import predict_from_features
from aircast.metrics import binary_scores, confusion_counts, roc_auc, threshold_from_f1


def test_confusion_and_f1_on_known_counts():
    y = np.array([1, 1, 0, 0])
    pred = np.array([1, 0, 0, 0])
    cm = confusion_counts(y, pred)
    assert cm == {"tp": 1, "tn": 2, "fp": 0, "fn": 1, "n": 4}
    scores = binary_scores(cm)
    assert scores["precision"] == 1.0
    assert scores["recall"] == 0.5
    assert abs(scores["f1"] - (2 * 1 * 0.5) / 1.5) < 1e-9


def test_roc_auc_perfect_and_degenerate():
    y = np.array([0, 0, 1, 1])
    perfect = np.array([0.1, 0.2, 0.8, 0.9])
    assert roc_auc(y, perfect) == 1.0
    assert roc_auc(np.array([1, 1, 1]), np.array([0.2, 0.3, 0.4])) is None


def test_threshold_selection_uses_validation_scores_only():
    y = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.4, 0.6, 0.9])
    chosen = threshold_from_f1(y, scores, np.array([0.05, 0.5, 0.95]))
    assert chosen["threshold"] == 0.5
    assert chosen["f1"] == 1.0


def test_logistic_inference_bundle_roundtrip():
    bundle = {
        "artifact_version": "test",
        "assembled_features": ["daily_mean_pm25", "pm25_lag1_missing"],
        "imputer": [{"column": "daily_mean_pm25", "value": 40.0}],
        "models": {
            "logistic_regression": {
                "type": "logistic_regression",
                "uses_scaler": False,
                "coefficients": [0.0, 0.0],
                "intercept": 10.0,
                "decision_threshold": 0.5,
                "score_kind": "probability",
            }
        },
    }
    # High intercept => probability near 1 regardless of unused extra features.
    result = predict_from_features(
        "logistic_regression",
        {
            "valid_reading_count": 24,
            "daily_mean_pm25": 80,
            "daily_min_pm25": 10,
            "daily_max_pm25": 90,
            "pm25_lag1": None,
            "pm25_lag2": 20,
            "pm25_lag3": 20,
            "pm25_roll7": 30,
            "pm25_delta1": None,
            "month_sin": 0,
            "month_cos": 1,
            "is_winter": 1,
            "dow": 2,
        },
        bundle,
    )
    assert result["predicted_class"] == 1
    assert result["probability"] is not None and result["probability"] > 0.99
