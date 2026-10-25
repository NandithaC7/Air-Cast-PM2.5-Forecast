#!/usr/bin/env python3
"""Train and evaluate the four required PySpark MLlib classifiers.

Uses the expanded feature dataset, a chronological date split, training-fitted
imputation/scaling, validation-only threshold and model selection, and an
untouched test set for the published comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aircast.constants import (  # noqa: E402
    ARTIFACT_VERSION,
    ASSEMBLED_FEATURE_COLUMNS,
    DT_IMPURITY,
    DT_MAX_DEPTH,
    DT_MIN_INSTANCES,
    EXPECTED_FEATURE_SCHEMA,
    FEATURE_COLUMNS,
    HAZARD_THRESHOLD_UG_M3,
    LR_ELASTIC_NET,
    LR_MAX_ITER,
    LR_REG_PARAM,
    MISSING_INDICATOR_COLUMNS,
    MODEL_KEYS,
    MODEL_ORDER,
    NULLABLE_FEATURE_COLUMNS,
    RANDOM_SEED,
    RF_FEATURE_SUBSET,
    RF_IMPURITY,
    RF_MAX_DEPTH,
    RF_MIN_INSTANCES,
    RF_NUM_TREES,
    SELECTION_CRITERION,
    SELECTION_TIE_BREAK,
    SVM_MAX_ITER,
    SVM_REG_PARAM,
    TIMEZONE,
)
from aircast.io import load_daily_valid, load_model_features  # noqa: E402
from aircast.metrics import (  # noqa: E402
    average_precision,
    binary_scores,
    candidate_thresholds,
    confusion_counts,
    pr_points,
    roc_auc,
    roc_points,
    threshold_from_f1,
)
from aircast.paths import (  # noqa: E402
    discover_spark_csv,
    evaluation_dir,
    features_dir,
    models_dir,
    repo_root,
)
from aircast.split import (  # noqa: E402
    assign_partition,
    chronological_boundaries,
    partition_label_report,
    unique_sorted_dates,
)
from aircast.spark_session import build_spark, configure_runtime  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train AirCast India's four Spark classifiers.")
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        help="Versioned output directory name. Previous runs are kept.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("bin" if False else "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_missing_indicator_columns(frame):
    from pyspark.sql import functions as F

    out = frame
    for name in NULLABLE_FEATURE_COLUMNS:
        out = out.withColumn(
            f"{name}_missing",
            F.when(F.col(name).isNull() | F.isnan(name), 1.0).otherwise(0.0),
        )
    return out


def extract_score(row: Any, score_kind_hint: str) -> tuple[float, str]:
    mapping = row.asDict() if hasattr(row, "asDict") else dict(row)
    if mapping.get("probability") is not None and score_kind_hint == "probability":
        vector = mapping["probability"]
        values = vector.toArray() if hasattr(vector, "toArray") else list(vector)
        return float(values[1]), "probability"
    raw = mapping.get("rawPrediction")
    if raw is None:
        raise KeyError("Prediction row has neither probability nor rawPrediction.")
    values = raw.toArray() if hasattr(raw, "toArray") else list(raw)
    return float(values[-1]), "decision_function"


def collect_scored(pred_df, score_kind_hint: str) -> pd.DataFrame:
    rows = []
    for row in pred_df.select(
        "sensor_id",
        "station",
        "local_date",
        "label",
        "daily_mean_pm25",
        "prediction",
        "rawPrediction",
        *([c for c in pred_df.columns if c == "probability"]),
    ).collect():
        score, kind = extract_score(row, score_kind_hint)
        rows.append(
            {
                "sensor_id": int(row["sensor_id"]),
                "station": row["station"],
                "local_date": str(row["local_date"]),
                "label": int(row["label"]),
                "daily_mean_pm25": float(row["daily_mean_pm25"]),
                "spark_prediction": int(row["prediction"]),
                "score": score,
                "score_kind": kind,
            }
        )
    return pd.DataFrame(rows)


def evaluate_partition(scored: pd.DataFrame, threshold: float) -> dict[str, Any]:
    y = scored["label"].to_numpy()
    scores = scored["score"].to_numpy()
    pred = (scores >= threshold).astype(int)
    cm = confusion_counts(y, pred)
    block = binary_scores(cm)
    kind = scored["score_kind"].iloc[0] if len(scored) else "unknown"
    roc = roc_points(y, scores)
    pr = pr_points(y, scores)
    block.update(
        {
            "decision_threshold": float(threshold),
            "score_kind": kind,
            "roc_auc": roc_auc(y, scores),
            "pr_auc": average_precision(y, scores),
            "roc": roc,
            "pr": pr,
        }
    )
    return block, pred


def persistence_baseline(scored: pd.DataFrame) -> dict[str, Any]:
    y = scored["label"].to_numpy()
    pred = (scored["daily_mean_pm25"].to_numpy() > HAZARD_THRESHOLD_UG_M3).astype(int)
    cm = confusion_counts(y, pred)
    block = binary_scores(cm)
    roc = roc_points(y, pred.astype(float))
    pr = pr_points(y, pred.astype(float))
    block.update(
        {
            "name": "persistence",
            "description": (
                "Predict next-day hazard if today's daily mean PM2.5 already exceeds "
                f"{HAZARD_THRESHOLD_UG_M3} µg/m³. Uses only information available at "
                "the prediction cutoff."
            ),
            "roc_auc": roc_auc(y, pred.astype(float)),
            "pr_auc": average_precision(y, pred.astype(float)),
            "roc": roc,
            "pr": pr,
            "score_kind": "hard_label",
        }
    )
    return block


def majority_baseline(scored: pd.DataFrame, majority_class: int) -> dict[str, Any]:
    y = scored["label"].to_numpy()
    pred = np.full(y.shape, majority_class, dtype=int)
    cm = confusion_counts(y, pred)
    block = binary_scores(cm)
    block.update(
        {
            "name": "majority_class",
            "description": (
                f"Always predict class {majority_class}, the majority label in the "
                "training partition. This ignores all features and is a weak reference."
            ),
            "roc_auc": None,
            "pr_auc": None,
            "score_kind": "hard_label",
        }
    )
    return block


def select_preferred(val_rows: dict[str, dict[str, Any]]) -> str:
    def key(name: str) -> tuple:
        row = val_rows[name]
        f1 = row["f1"] if row["f1"] is not None else -1.0
        recall = row["recall"] if row["recall"] is not None else -1.0
        simplicity = -SELECTION_TIE_BREAK.index(name)
        return (f1, recall, simplicity)

    return max(val_rows, key=key)


def extract_tree(java_node) -> dict[str, Any]:
    stats = None
    try:
        raw = list(java_node.impurityStats().stats())
        stats = [float(value) for value in raw]
    except Exception:
        stats = None
    prediction = float(java_node.prediction())
    if stats and sum(stats) > 0 and len(stats) > 1:
        probability = float(stats[1] / sum(stats))
    else:
        probability = prediction
    descendants = int(java_node.numDescendants())
    if descendants == 0:
        return {
            "leaf": True,
            "prediction": prediction,
            "probability_positive": probability,
        }
    split = java_node.split()
    return {
        "leaf": False,
        "feature_index": int(split.featureIndex()),
        "threshold": float(split.threshold()),
        "prediction": prediction,
        "probability_positive": probability,
        "left": extract_tree(java_node.leftChild()),
        "right": extract_tree(java_node.rightChild()),
    }


def importance_map(vector, names: list[str]) -> dict[str, float]:
    values = vector.toArray() if hasattr(vector, "toArray") else list(vector)
    return {name: float(value) for name, value in zip(names, values)}


def downsample_curve(points: dict[str, Any] | None, limit: int = 200) -> dict[str, Any] | None:
    if not points:
        return points
    keys = [key for key in points if isinstance(points[key], list)]
    if not keys:
        return points
    n = len(points[keys[0]])
    if n <= limit:
        return points
    idx = np.linspace(0, n - 1, limit, dtype=int)
    out = dict(points)
    for key in keys:
        out[key] = [points[key][i] for i in idx]
    return out


def write_plots(payload: dict[str, Any], plot_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir.mkdir(parents=True, exist_ok=True)
    models = payload["models"]
    names = [MODEL_KEYS[key] for key in MODEL_ORDER]
    colors = ["#2f4a3c", "#5f7a68", "#7a5a20", "#3d5a80"]

    fig, ax = plt.subplots(figsize=(9, 5))
    metrics = ["precision", "recall", "f1", "accuracy"]
    x = np.arange(len(MODEL_ORDER))
    width = 0.18
    for i, metric in enumerate(metrics):
        values = [models[key]["test"].get(metric) or 0 for key in MODEL_ORDER]
        ax.bar(x + (i - 1.5) * width, values, width, label=metric.replace("_", " ").title(), color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("Holdout test performance (hazard class)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "model_performance_comparison.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(9, 8))
    for ax, key, color in zip(axes.ravel(), MODEL_ORDER, colors):
        cm = models[key]["test"]
        grid = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]], dtype=float)
        ax.imshow(grid, cmap="Blues")
        ax.set_xticks([0, 1], ["Predicted negative", "Predicted positive"])
        ax.set_yticks([0, 1], ["Actual negative", "Actual positive"])
        for (r, c), value in np.ndenumerate(grid):
            ax.text(c, r, f"{int(value)}", ha="center", va="center", color="black")
        ax.set_title(MODEL_KEYS[key])
    fig.suptitle("Confusion matrices on the chronological test set (counts)")
    fig.tight_layout()
    fig.savefig(plot_dir / "confusion_matrices.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], "--", color="#999999", label="Random classifier")
    for key, color in zip(MODEL_ORDER, colors):
        roc = models[key]["test"].get("roc")
        if not roc:
            continue
        ax.plot(
            roc["false_positive_rate"],
            roc["true_positive_rate"],
            color=color,
            label=f"{MODEL_KEYS[key]} (AUC={roc['auc']:.3f})" if roc.get("auc") is not None else MODEL_KEYS[key],
        )
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curves (ranking scores; Linear SVM uses the decision function)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "roc_curves.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    prevalence = payload["split"]["label_counts"]["test"]["prevalence"]
    if prevalence is not None:
        ax.axhline(prevalence, color="#999999", linestyle="--", label=f"Test hazard prevalence ({prevalence:.2f})")
    for key, color in zip(MODEL_ORDER, colors):
        pr = models[key]["test"].get("pr")
        if not pr:
            continue
        label = MODEL_KEYS[key]
        if pr.get("average_precision") is not None:
            label += f" (AP={pr['average_precision']:.3f})"
        ax.plot(pr["recall"], pr["precision"], color=color, label=label)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_ylim(0, 1.02)
    ax.set_title("Precision-recall curves on the chronological test set")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "precision_recall_curves.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, key in zip(axes, ("decision_tree", "random_forest", "logistic_regression")):
        importance = models[key].get("feature_importance") or models[key].get("coefficients")
        if not importance:
            ax.set_visible(False)
            continue
        items = sorted(importance.items(), key=lambda item: abs(item[1]))[-10:]
        ax.barh([name for name, _ in items], [value for _, value in items], color="#2f4a3c")
        ax.set_title(MODEL_KEYS[key])
    fig.suptitle("Feature attribution (tree importance vs scaled LR coefficients)")
    fig.tight_layout()
    fig.savefig(plot_dir / "feature_importance.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    train_s = [models[key]["runtime"]["train_seconds"] for key in MODEL_ORDER]
    pred_s = [models[key]["runtime"]["predict_seconds"] for key in MODEL_ORDER]
    x = np.arange(len(MODEL_ORDER))
    ax.bar(x - 0.18, train_s, 0.36, label="Training", color="#2f4a3c")
    ax.bar(x + 0.18, pred_s, 0.36, label="Prediction + evaluation", color="#7a5a20")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15)
    ax.set_ylabel("Seconds")
    ax.set_title("Measured runtime on this machine (local Spark)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "runtime_comparison.png", dpi=140)
    plt.close(fig)

    daily = load_daily_valid()
    daily["local_date"] = pd.to_datetime(daily["local_date"])
    series = daily.groupby("local_date", as_index=False).agg(
        daily_mean_pm25=("daily_mean_pm25", "mean"),
        stations=("station", "nunique"),
    )
    series["hazard"] = (series["daily_mean_pm25"] > HAZARD_THRESHOLD_UG_M3).astype(int)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(series["local_date"], series["daily_mean_pm25"], color="#2f4a3c", label="Cross-station daily mean PM2.5")
    ax.axhline(HAZARD_THRESHOLD_UG_M3, color="#7a5a20", linestyle="--", label="Configured threshold")
    ax.set_ylabel("µg/m³")
    ax.set_title("Historical measured daily mean PM2.5 (not a forecast)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "temporal_hazard_trend.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    errors = payload.get("error_analysis", {})
    for ax, key in zip(axes.ravel(), MODEL_ORDER):
        rows = errors.get(key, [])
        if not rows:
            ax.set_visible(False)
            continue
        stations = [row["station"][:22] for row in rows]
        ax.barh(stations, [row["false_negatives"] for row in rows], color="#7a3b32", label="False negatives")
        ax.barh(stations, [row["false_positives"] for row in rows], left=[row["false_negatives"] for row in rows], color="#7a5a20", label="False positives")
        ax.set_title(MODEL_KEYS[key])
    fig.suptitle("Test-set errors by station")
    handles, labels = axes[0][0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=2)
    fig.tight_layout()
    fig.savefig(plot_dir / "prediction_error_analysis.png", dpi=140)
    plt.close(fig)


def chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = []
    for key in MODEL_ORDER:
        test = payload["models"][key]["test"]
        comparison.append(
            {
                "model": key,
                "display_name": MODEL_KEYS[key],
                "precision": test.get("precision"),
                "recall": test.get("recall"),
                "f1": test.get("f1"),
                "accuracy": test.get("accuracy"),
                "preferred": key == payload["selection"]["preferred_model"],
            }
        )
    confusion = {}
    curves = {}
    importance = {}
    runtime = []
    for key in MODEL_ORDER:
        test = payload["models"][key]["test"]
        confusion[key] = {
            "tn": test["tn"],
            "fp": test["fp"],
            "fn": test["fn"],
            "tp": test["tp"],
            "normalization": "counts",
            "labels": {
                "actual_negative": "Actual negative (no next-day hazard)",
                "actual_positive": "Actual positive (next-day hazard)",
                "predicted_negative": "Predicted negative",
                "predicted_positive": "Predicted positive",
            },
        }
        curves[key] = {
            "score_kind": test.get("score_kind"),
            "roc": downsample_curve(test.get("roc")),
            "pr": downsample_curve(test.get("pr")),
            "roc_unavailable_reason": None
            if test.get("roc")
            else "A ROC curve requires both classes and a ranking score.",
            "pr_unavailable_reason": None
            if test.get("pr")
            else "A precision-recall curve requires at least one positive test label.",
        }
        spec = payload["models"][key]
        if spec.get("feature_importance"):
            importance[key] = {
                "kind": "feature_importance",
                "items": [
                    {"feature": name, "value": value}
                    for name, value in spec["feature_importance"].items()
                ],
            }
        elif spec.get("coefficients"):
            importance[key] = {
                "kind": "coefficients",
                "note": "Scaled-feature coefficients, not tree impurity importance.",
                "items": [
                    {"feature": name, "value": value}
                    for name, value in spec["coefficients"].items()
                ],
            }
        else:
            importance[key] = {
                "kind": "unavailable",
                "note": spec.get("attribution_note")
                or "This estimator does not expose a supported importance measure.",
                "items": [],
            }
        runtime.append(
            {
                "model": key,
                "display_name": MODEL_KEYS[key],
                "train_seconds": spec["runtime"]["train_seconds"],
                "predict_seconds": spec["runtime"]["predict_seconds"],
            }
        )
    daily = load_daily_valid()
    daily["local_date"] = pd.to_datetime(daily["local_date"])
    trend = (
        daily.groupby("local_date", as_index=False)
        .agg(daily_mean_pm25=("daily_mean_pm25", "mean"), stations=("station", "nunique"))
        .sort_values("local_date")
    )
    trend["hazard"] = (trend["daily_mean_pm25"] > HAZARD_THRESHOLD_UG_M3).astype(int)
    return {
        "comparison": comparison,
        "confusion": confusion,
        "curves": curves,
        "feature_attribution": importance,
        "runtime": runtime,
        "temporal_trend": [
            {
                "date": row.local_date.date().isoformat(),
                "daily_mean_pm25": float(row.daily_mean_pm25),
                "stations": int(row.stations),
                "exceeds_threshold": int(row.hazard),
                "series_kind": "historical_observation",
            }
            for row in trend.itertuples()
        ],
        "error_analysis": payload.get("error_analysis", {}),
        "baselines": payload.get("baselines", {}),
    }


def main() -> None:
    args = parse_args()
    root = repo_root()
    runtime_env = configure_runtime()
    feature_csv = discover_spark_csv(features_dir(root))
    pandas_features = load_model_features(feature_csv)
    dates = unique_sorted_dates(pandas_features)
    boundaries = chronological_boundaries(dates)
    partitions = assign_partition(pandas_features, boundaries)
    label_counts = partition_label_report(pandas_features, partitions)
    for name in ("train", "validation", "test"):
        classes = {1 if label_counts[name]["positive"] else None, 0 if label_counts[name]["negative"] else None}
        if label_counts[name]["positive"] == 0 or label_counts[name]["negative"] == 0:
            print(f"WARNING: {name} partition does not contain both classes: {label_counts[name]}")

    extra = [column for column in pandas_features.columns if column not in EXPECTED_FEATURE_SCHEMA]
    if extra:
        raise SystemExit(f"Unexpected feature columns present: {extra}")

    run_eval = evaluation_dir(root) / "runs" / args.run_id
    run_models = models_dir(root) / "runs" / args.run_id
    run_eval.mkdir(parents=True, exist_ok=True)
    run_models.mkdir(parents=True, exist_ok=True)

    spark = build_spark("AirCast-Model-Training")
    from pyspark.ml import Pipeline, PipelineModel
    from pyspark.ml.classification import (
        DecisionTreeClassificationModel,
        DecisionTreeClassifier,
        LinearSVC,
        LinearSVCModel,
        LogisticRegression,
        LogisticRegressionModel,
        RandomForestClassificationModel,
        RandomForestClassifier,
    )
    from pyspark.ml.feature import Imputer, StandardScaler, StandardScalerModel, VectorAssembler
    from pyspark.sql import functions as F
    from pyspark.sql.types import DateType, DoubleType, LongType, StringType, StructField, StructType

    schema = StructType(
        [
            StructField("sensor_id", LongType(), False),
            StructField("station", StringType(), False),
            StructField("local_date", DateType(), False),
            *[StructField(name, DoubleType(), True) for name in FEATURE_COLUMNS],
            StructField("label", DoubleType(), False),
        ]
    )
    df = (
        spark.read.option("header", True)
        .schema(schema)
        .csv(str(feature_csv))
        .withColumn("label", F.col("label").cast("double"))
    )
    df = add_missing_indicator_columns(df)
    train_end = boundaries["train"]["last_date"]
    val_end = boundaries["validation"]["last_date"]
    train = df.filter(F.col("local_date") <= F.lit(date.fromisoformat(train_end)))
    validation = df.filter(
        (F.col("local_date") > F.lit(date.fromisoformat(train_end)))
        & (F.col("local_date") <= F.lit(date.fromisoformat(val_end)))
    )
    test = df.filter(F.col("local_date") > F.lit(date.fromisoformat(val_end)))

    n_pos = train.filter(F.col("label") == 1).count()
    n_neg = train.filter(F.col("label") == 0).count()
    n_train = n_pos + n_neg
    w_pos = (n_train / (2.0 * n_pos)) if n_pos else 1.0
    w_neg = (n_train / (2.0 * n_neg)) if n_neg else 1.0
    train = train.withColumn(
        "class_weight",
        F.when(F.col("label") == 1.0, F.lit(w_pos)).otherwise(F.lit(w_neg)),
    )
    majority_class = 1 if n_pos > n_neg else 0

    imputer = Imputer(inputCols=FEATURE_COLUMNS, outputCols=FEATURE_COLUMNS, strategy="mean")
    assembler = VectorAssembler(
        inputCols=ASSEMBLED_FEATURE_COLUMNS,
        outputCol="features",
        handleInvalid="error",
    )
    preprocess = Pipeline(stages=[imputer, assembler]).fit(train)
    train_p = preprocess.transform(train)
    val_p = preprocess.transform(validation)
    test_p = preprocess.transform(test)
    train_p.cache()
    val_p.cache()
    test_p.cache()
    train_p.count()
    val_p.count()
    test_p.count()

    estimators: dict[str, Any] = {
        "logistic_regression": Pipeline(
            stages=[
                StandardScaler(inputCol="features", outputCol="scaled", withMean=True, withStd=True),
                LogisticRegression(
                    featuresCol="scaled",
                    labelCol="label",
                    weightCol="class_weight",
                    maxIter=LR_MAX_ITER,
                    regParam=LR_REG_PARAM,
                    elasticNetParam=LR_ELASTIC_NET,
                    standardization=False,
                    family="binomial",
                    threshold=0.5,
                ),
            ]
        ),
        "decision_tree": Pipeline(
            stages=[
                DecisionTreeClassifier(
                    featuresCol="features",
                    labelCol="label",
                    weightCol="class_weight",
                    maxDepth=DT_MAX_DEPTH,
                    minInstancesPerNode=DT_MIN_INSTANCES,
                    impurity=DT_IMPURITY,
                    seed=RANDOM_SEED,
                )
            ]
        ),
        "random_forest": Pipeline(
            stages=[
                RandomForestClassifier(
                    featuresCol="features",
                    labelCol="label",
                    weightCol="class_weight",
                    numTrees=RF_NUM_TREES,
                    maxDepth=RF_MAX_DEPTH,
                    minInstancesPerNode=RF_MIN_INSTANCES,
                    featureSubsetStrategy=RF_FEATURE_SUBSET,
                    impurity=RF_IMPURITY,
                    seed=RANDOM_SEED,
                    subsamplingRate=1.0,
                )
            ]
        ),
        "linear_svm": Pipeline(
            stages=[
                StandardScaler(inputCol="features", outputCol="scaled", withMean=True, withStd=True),
                LinearSVC(
                    featuresCol="scaled",
                    labelCol="label",
                    weightCol="class_weight",
                    maxIter=SVM_MAX_ITER,
                    regParam=SVM_REG_PARAM,
                    standardization=False,
                    threshold=0.0,
                    aggregationDepth=2,
                ),
            ]
        ),
    }
    score_kinds = {
        "logistic_regression": "probability",
        "decision_tree": "probability",
        "random_forest": "probability",
        "linear_svm": "decision_function",
    }

    model_rows: dict[str, dict[str, Any]] = {}
    fitted: dict[str, Any] = {}
    test_frames: dict[str, pd.DataFrame] = {}
    inference_models: dict[str, Any] = {}

    for key, pipeline in estimators.items():
        print(f"Training {MODEL_KEYS[key]}...")
        started = time.perf_counter()
        model = pipeline.fit(train_p)
        train_seconds = time.perf_counter() - started
        pred_started = time.perf_counter()
        val_pred = model.transform(val_p)
        test_pred = model.transform(test_p)
        val_scored = collect_scored(val_pred, score_kinds[key])
        test_scored = collect_scored(test_pred, score_kinds[key])
        predict_seconds = time.perf_counter() - pred_started
        tuned = threshold_from_f1(
            val_scored["label"].to_numpy(),
            val_scored["score"].to_numpy(),
            candidate_thresholds(val_scored["score"].to_numpy(), score_kinds[key]),
        )
        threshold = float(tuned["threshold"])
        val_metrics, _ = evaluate_partition(val_scored, threshold)
        test_metrics, test_pred_labels = evaluate_partition(test_scored, threshold)
        test_scored = test_scored.copy()
        test_scored["predicted"] = test_pred_labels
        test_frames[key] = test_scored

        estimator = model.stages[-1]
        scaler = model.stages[0] if isinstance(model.stages[0], StandardScalerModel) else None
        feature_importance = None
        coefficients = None
        attribution_note = None
        bundle: dict[str, Any] = {
            "type": key,
            "uses_scaler": scaler is not None,
            "decision_threshold": threshold,
            "score_kind": score_kinds[key],
        }
        if scaler is not None:
            bundle["scaler_mean"] = [float(v) for v in scaler.mean.toArray()]
            bundle["scaler_std"] = [float(v) for v in scaler.std.toArray()]
        if isinstance(estimator, LogisticRegressionModel):
            coefficients = {
                name: float(value)
                for name, value in zip(ASSEMBLED_FEATURE_COLUMNS, estimator.coefficients.toArray())
            }
            bundle["coefficients"] = list(coefficients.values())
            bundle["intercept"] = float(estimator.intercept)
        elif isinstance(estimator, LinearSVCModel):
            coefficients = {
                name: float(value)
                for name, value in zip(ASSEMBLED_FEATURE_COLUMNS, estimator.coefficients.toArray())
            }
            bundle["coefficients"] = list(coefficients.values())
            bundle["intercept"] = float(estimator.intercept)
            attribution_note = (
                "Linear SVM coefficients after scaling. These are not feature importance."
            )
        elif isinstance(estimator, DecisionTreeClassificationModel):
            feature_importance = importance_map(estimator.featureImportances, ASSEMBLED_FEATURE_COLUMNS)
            bundle["tree"] = extract_tree(estimator._java_obj.rootNode())
        elif isinstance(estimator, RandomForestClassificationModel):
            feature_importance = importance_map(estimator.featureImportances, ASSEMBLED_FEATURE_COLUMNS)
            bundle["trees"] = [extract_tree(tree._java_obj.rootNode()) for tree in estimator.trees]
        inference_models[key] = bundle

        combined = PipelineModel(stages=list(preprocess.stages) + list(model.stages))
        artifact_dir = run_models / key
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        combined.save(str(artifact_dir))
        fitted[key] = combined

        model_rows[key] = {
            "name": key,
            "display_name": MODEL_KEYS[key],
            "artifact_path": str(artifact_dir.relative_to(root)),
            "available": True,
            "validation": {k: v for k, v in val_metrics.items() if k not in {"roc", "pr"}},
            "test": {k: v for k, v in test_metrics.items() if k not in {"roc", "pr"}},
            "feature_importance": feature_importance,
            "coefficients": coefficients,
            "attribution_note": attribution_note,
            "runtime": {
                "train_seconds": round(train_seconds, 4),
                "predict_seconds": round(predict_seconds, 4),
            },
            "hyperparameters": _hyperparameters(key),
            "threshold_selection": tuned,
        }
        model_rows[key]["test"]["roc"] = test_metrics.get("roc")
        model_rows[key]["test"]["pr"] = test_metrics.get("pr")
        print(
            f"  val F1={val_metrics['f1']}  test F1={test_metrics['f1']}  "
            f"threshold={threshold:.4f}  train={train_seconds:.2f}s"
        )

    preferred = select_preferred({key: model_rows[key]["validation"] for key in MODEL_ORDER})
    persistence = persistence_baseline(test_frames[preferred])
    majority = majority_baseline(test_frames[preferred], majority_class)

    error_analysis: dict[str, list[dict[str, Any]]] = {}
    for key, scored in test_frames.items():
        rows = []
        for station, group in scored.groupby("station"):
            y = group["label"].to_numpy()
            p = group["predicted"].to_numpy()
            cm = confusion_counts(y, p)
            rows.append(
                {
                    "station": station,
                    "n": cm["n"],
                    "false_positives": cm["fp"],
                    "false_negatives": cm["fn"],
                    "true_positives": cm["tp"],
                    "true_negatives": cm["tn"],
                }
            )
        error_analysis[key] = sorted(rows, key=lambda item: item["false_negatives"] + item["false_positives"], reverse=True)

    imputer_model = preprocess.stages[0]
    surrogate = imputer_model.surrogateDF.head()
    imputer_values = [
        {"column": column, "value": float(surrogate[column])}
        for column in imputer_model.getInputCols()
    ]
    bundle = {
        "artifact_version": ARTIFACT_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "assembled_features": ASSEMBLED_FEATURE_COLUMNS,
        "feature_columns": FEATURE_COLUMNS,
        "imputer": imputer_values,
        "imputer_strategy": "mean",
        "models": inference_models,
        "preferred_model": preferred,
        "label_definition": (
            "label=1 if the next local calendar day's daily mean PM2.5 exceeds "
            f"{HAZARD_THRESHOLD_UG_M3} µg/m³ (project-configured threshold)."
        ),
    }
    (run_models / "inference_bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    dataset_stats = {
        "feature_rows": int(len(pandas_features)),
        "stations": int(pandas_features["station"].nunique()),
        "positive_labels": int((pandas_features["label"] == 1).sum()),
        "negative_labels": int((pandas_features["label"] == 0).sum()),
        "first_date": boundaries["train"]["first_date"],
        "last_date": boundaries["test"]["last_date"],
        "feature_file": str(feature_csv.relative_to(root)),
        "feature_sha256": sha256_file(feature_csv),
    }
    payload = {
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "name": "AirCast India",
            "title": "Next-Day PM2.5 Hazard Forecasting",
            "timezone": TIMEZONE,
            "hazard_threshold_ug_m3": HAZARD_THRESHOLD_UG_M3,
            "positive_class": 1,
            "spark_version": spark.version,
            "spark_mode": "local[2]",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "java_home": runtime_env.get("java_home"),
        },
        "dataset": dataset_stats,
        "split": {
            **boundaries,
            "label_counts": label_counts,
            "random_seed": RANDOM_SEED,
            "class_weights_train": {"positive": w_pos, "negative": w_neg},
        },
        "selection": {
            "criterion": SELECTION_CRITERION,
            "preferred_model": preferred,
            "preferred_display_name": MODEL_KEYS[preferred],
            "used_test_set": False,
        },
        "models": model_rows,
        "baselines": {"persistence": persistence, "majority": majority},
        "error_analysis": error_analysis,
    }
    charts = chart_payload(payload)
    plot_dir = run_eval / "plots"
    write_plots(payload, plot_dir)

    comparison_rows = []
    for key in MODEL_ORDER:
        test = model_rows[key]["test"]
        comparison_rows.append(
            {
                "model": key,
                "display_name": MODEL_KEYS[key],
                "preferred": key == preferred,
                "accuracy": test.get("accuracy"),
                "precision": test.get("precision"),
                "recall": test.get("recall"),
                "f1": test.get("f1"),
                "macro_f1": test.get("macro_f1"),
                "weighted_f1": test.get("weighted_f1"),
                "roc_auc": test.get("roc_auc"),
                "pr_auc": test.get("pr_auc"),
                "score_kind": test.get("score_kind"),
                "decision_threshold": test.get("decision_threshold"),
                "tn": test.get("tn"),
                "fp": test.get("fp"),
                "fn": test.get("fn"),
                "tp": test.get("tp"),
                "n": test.get("n"),
                "train_seconds": model_rows[key]["runtime"]["train_seconds"],
                "predict_seconds": model_rows[key]["runtime"]["predict_seconds"],
            }
        )
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(run_eval / "model_comparison.csv", index=False)
    (run_eval / "model_metrics.json").write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    (run_eval / "charts.json").write_text(json.dumps(charts, indent=2, default=_json_default), encoding="utf-8")
    (run_eval / "split_report.json").write_text(
        json.dumps({"split": payload["split"], "dataset": dataset_stats}, indent=2),
        encoding="utf-8",
    )
    preferred_frame = test_frames[preferred]
    preferred_frame.to_csv(run_eval / "test_predictions_preferred.csv", index=False)

    active_eval = evaluation_dir(root)
    active_models = models_dir(root)
    for name in ("model_metrics.json", "model_comparison.csv", "charts.json", "split_report.json"):
        shutil.copy2(run_eval / name, active_eval / name)
    plots_active = active_eval / "plots"
    if plots_active.exists():
        shutil.rmtree(plots_active)
    shutil.copytree(plot_dir, plots_active)
    (active_models / "inference_bundle.json").write_text(
        (run_models / "inference_bundle.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (active_models / "current.json").write_text(
        json.dumps({"run_id": args.run_id, "preferred_model": preferred, "artifact_version": ARTIFACT_VERSION}, indent=2),
        encoding="utf-8",
    )
    for key in MODEL_ORDER:
        dest = active_models / key
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(run_models / key, dest)

    print("\nPreferred model:", MODEL_KEYS[preferred])
    print("Selection used validation F1 only.")
    print("Evaluation written to", run_eval)
    print("Active snapshot updated under", active_eval)
    train_p.unpersist()
    val_p.unpersist()
    test_p.unpersist()
    spark.stop()


def _hyperparameters(key: str) -> dict[str, Any]:
    if key == "logistic_regression":
        return {
            "estimator": "pyspark.ml.classification.LogisticRegression",
            "maxIter": LR_MAX_ITER,
            "regParam": LR_REG_PARAM,
            "elasticNetParam": LR_ELASTIC_NET,
            "standardization": "StandardScaler on training features; estimator standardization disabled",
            "family": "binomial",
        }
    if key == "decision_tree":
        return {
            "estimator": "pyspark.ml.classification.DecisionTreeClassifier",
            "maxDepth": DT_MAX_DEPTH,
            "minInstancesPerNode": DT_MIN_INSTANCES,
            "impurity": DT_IMPURITY,
            "seed": RANDOM_SEED,
        }
    if key == "random_forest":
        return {
            "estimator": "pyspark.ml.classification.RandomForestClassifier",
            "numTrees": RF_NUM_TREES,
            "maxDepth": RF_MAX_DEPTH,
            "minInstancesPerNode": RF_MIN_INSTANCES,
            "featureSubsetStrategy": RF_FEATURE_SUBSET,
            "impurity": RF_IMPURITY,
            "seed": RANDOM_SEED,
        }
    return {
        "estimator": "pyspark.ml.classification.LinearSVC",
        "maxIter": SVM_MAX_ITER,
        "regParam": SVM_REG_PARAM,
        "standardization": "StandardScaler on training features; estimator standardization disabled",
        "probability_note": "LinearSVC does not emit calibrated probabilities. Ranking uses the decision function.",
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Cannot serialize {type(value)}")


if __name__ == "__main__":
    main()
