"""Portable inference for Spark-trained classifiers.

Parameters are extracted from fitted Spark models during training. The backend
applies the same imputer, scaler, and decision rule without retraining.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aircast.constants import (
    ASSEMBLED_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    MISSING_INDICATOR_COLUMNS,
    MODEL_KEYS,
    NULLABLE_FEATURE_COLUMNS,
)


def add_missing_indicators(values: dict[str, float | None]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in FEATURE_COLUMNS:
        raw = values.get(name)
        missing = raw is None or (isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)))
        if name in NULLABLE_FEATURE_COLUMNS:
            out[f"{name}_missing"] = 1.0 if missing else 0.0
        out[name] = float("nan") if missing else float(raw)  # type: ignore[arg-type]
    return out


def impute_vector(values: dict[str, float], bundle: dict[str, Any]) -> list[float]:
    surrogates = {item["column"]: float(item["value"]) for item in bundle["imputer"]}
    vector: list[float] = []
    for name in bundle["assembled_features"]:
        if name in MISSING_INDICATOR_COLUMNS:
            vector.append(float(values[name]))
            continue
        raw = values.get(name)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            if name not in surrogates:
                raise ValueError(f"No training-fitted surrogate for missing feature {name}.")
            vector.append(surrogates[name])
        else:
            vector.append(float(raw))
    return vector


def scale_vector(vector: list[float], spec: dict[str, Any]) -> list[float]:
    mean = spec["scaler_mean"]
    std = spec["scaler_std"]
    scaled = []
    for value, centre, spread in zip(vector, mean, std):
        denom = spread if spread and abs(spread) > 1e-12 else 1.0
        scaled.append((value - centre) / denom)
    return scaled


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _walk_tree(node: dict[str, Any], vector: list[float]) -> tuple[float, float]:
    if node.get("leaf"):
        return float(node["prediction"]), float(node.get("probability_positive", node["prediction"]))
    feature_value = vector[int(node["feature_index"])]
    branch = node["left"] if feature_value <= float(node["threshold"]) else node["right"]
    return _walk_tree(branch, vector)


def score_model(model_name: str, vector: list[float], spec: dict[str, Any]) -> dict[str, Any]:
    if model_name not in MODEL_KEYS:
        raise ValueError(f"Unknown model '{model_name}'.")
    features = scale_vector(vector, spec) if spec.get("uses_scaler") else list(vector)
    kind = spec["type"]
    threshold = float(spec["decision_threshold"])
    if kind == "logistic_regression":
        margin = float(spec["intercept"]) + float(np.dot(spec["coefficients"], features))
        score = _sigmoid(margin)
        predicted = 1 if score >= threshold else 0
        return {
            "predicted_class": predicted,
            "score": score,
            "score_kind": "probability",
            "probability": score,
            "decision_score": margin,
            "decision_threshold": threshold,
        }
    if kind == "linear_svm":
        margin = float(spec["intercept"]) + float(np.dot(spec["coefficients"], features))
        predicted = 1 if margin >= threshold else 0
        return {
            "predicted_class": predicted,
            "score": margin,
            "score_kind": "decision_function",
            "probability": None,
            "decision_score": margin,
            "decision_threshold": threshold,
        }
    if kind == "decision_tree":
        pred, prob = _walk_tree(spec["tree"], features)
        predicted = 1 if prob >= threshold else 0
        return {
            "predicted_class": predicted,
            "score": prob,
            "score_kind": "probability",
            "probability": prob,
            "decision_score": prob,
            "decision_threshold": threshold,
        }
    if kind == "random_forest":
        probs = [_walk_tree(tree, features)[1] for tree in spec["trees"]]
        prob = float(np.mean(probs)) if probs else 0.0
        predicted = 1 if prob >= threshold else 0
        return {
            "predicted_class": predicted,
            "score": prob,
            "score_kind": "probability",
            "probability": prob,
            "decision_score": prob,
            "decision_threshold": threshold,
        }
    raise ValueError(f"Unsupported estimator type '{kind}'.")


def predict_from_features(
    model_name: str,
    raw_features: dict[str, float | None],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    if model_name not in bundle["models"]:
        raise ValueError(f"Model '{model_name}' is not in the inference bundle.")
    prepared = add_missing_indicators(raw_features)
    vector = impute_vector(prepared, bundle)
    spec = bundle["models"][model_name]
    result = score_model(model_name, vector, spec)
    result["model_name"] = model_name
    result["model_version"] = bundle.get("artifact_version")
    result["assembled_features"] = ASSEMBLED_FEATURE_COLUMNS
    result["imputed_vector"] = vector
    return result
