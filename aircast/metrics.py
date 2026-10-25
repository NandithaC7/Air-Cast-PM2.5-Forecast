"""Leakage-free classification metrics. Positive class is next-day PM2.5 hazard."""

from __future__ import annotations

from typing import Any

import numpy as np


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(y_pred, dtype=int)
    tp = int(np.sum((y == 1) & (p == 1)))
    tn = int(np.sum((y == 0) & (p == 0)))
    fp = int(np.sum((y == 0) & (p == 1)))
    fn = int(np.sum((y == 1) & (p == 0)))
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "n": int(y.size)}


def _safe_div(num: float, den: float) -> float | None:
    if den == 0:
        return None
    return float(num / den)


def binary_scores(cm: dict[str, int]) -> dict[str, Any]:
    tp, tn, fp, fn = cm["tp"], cm["tn"], cm["fp"], cm["fn"]
    n = cm["n"]
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    neg_precision = _safe_div(tn, tn + fn)
    neg_recall = _safe_div(tn, tn + fp)
    pos_f1 = _f1(precision, recall)
    neg_f1 = _f1(neg_precision, neg_recall)
    support_pos = tp + fn
    support_neg = tn + fp
    macro_f1 = None
    if pos_f1 is not None and neg_f1 is not None:
        macro_f1 = float((pos_f1 + neg_f1) / 2.0)
    weighted_f1 = None
    if n and pos_f1 is not None and neg_f1 is not None:
        weighted_f1 = float((pos_f1 * support_pos + neg_f1 * support_neg) / n)
    return {
        "accuracy": _safe_div(tp + tn, n),
        "precision": precision,
        "recall": recall,
        "f1": pos_f1,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "hazard_prevalence": _safe_div(support_pos, n),
        "positive_support": support_pos,
        "negative_support": support_neg,
        **cm,
    }


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    return _safe_div(2.0 * precision * recall, precision + recall)


def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    pos = s[y == 1]
    neg = s[y == 0]
    if pos.size == 0 or neg.size == 0:
        return None
    # Wilcoxon-Mann-Whitney AUC; 0.5 credit for ties.
    correct = 0.0
    for value in pos:
        correct += float(np.sum(neg < value) + 0.5 * np.sum(neg == value))
    return float(correct / (pos.size * neg.size))


def roc_points(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any] | None:
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    if np.unique(y).size < 2:
        return None
    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    tpr = tp / tp[-1]
    fpr = fp / fp[-1] if fp[-1] else np.zeros_like(fp, dtype=float)
    fpr = np.concatenate([[0.0], fpr, [1.0]])
    tpr = np.concatenate([[0.0], tpr, [1.0]])
    auc = roc_auc(y, s)
    return {
        "false_positive_rate": [float(v) for v in fpr],
        "true_positive_rate": [float(v) for v in tpr],
        "auc": auc,
    }


def average_precision(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    curve = pr_points(y_true, scores)
    if curve is None:
        return None
    return curve["average_precision"]


def pr_points(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any] | None:
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    positives = int(np.sum(y == 1))
    if positives == 0:
        return None
    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    recall = tp / positives
    precision = tp / np.maximum(tp + fp, 1)
    precision = np.concatenate([[1.0], precision])
    recall = np.concatenate([[0.0], recall])
    ap = float(np.sum((recall[1:] - recall[:-1]) * precision[1:]))
    return {
        "precision": [float(v) for v in precision],
        "recall": [float(v) for v in recall],
        "average_precision": ap,
        "prevalence": float(positives / y.size) if y.size else None,
    }


def threshold_from_f1(y_true: np.ndarray, scores: np.ndarray, candidates: np.ndarray) -> dict[str, Any]:
    """Pick a decision threshold on a validation partition only."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    best = {
        "threshold": float(np.median(s)) if s.size else 0.5,
        "f1": None,
        "recall": None,
        "precision": None,
    }
    for raw in candidates:
        pred = (s >= raw).astype(int)
        cm = confusion_counts(y, pred)
        scores_block = binary_scores(cm)
        f1 = scores_block["f1"]
        recall = scores_block["recall"]
        better = False
        if best["f1"] is None and f1 is not None:
            better = True
        elif f1 is not None and best["f1"] is not None:
            if f1 > best["f1"] + 1e-12:
                better = True
            elif abs(f1 - best["f1"]) <= 1e-12 and recall is not None and (
                best["recall"] is None or recall > best["recall"]
            ):
                better = True
        if better:
            best = {
                "threshold": float(raw),
                "f1": f1,
                "recall": recall,
                "precision": scores_block["precision"],
            }
    return best


def candidate_thresholds(scores: np.ndarray, score_kind: str) -> np.ndarray:
    s = np.asarray(scores, dtype=float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return np.array([0.5 if score_kind == "probability" else 0.0])
    quantiles = np.unique(np.quantile(s, np.linspace(0.05, 0.95, 37)))
    if score_kind == "probability":
        extras = np.linspace(0.20, 0.80, 25)
        return np.unique(np.concatenate([quantiles, extras]))
    extras = np.array([0.0])
    return np.unique(np.concatenate([quantiles, extras]))
