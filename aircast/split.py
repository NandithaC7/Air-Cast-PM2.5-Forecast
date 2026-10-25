"""Deterministic chronological split on unique local calendar dates."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from aircast.constants import (
    TEST_DATE_FRACTION,
    TRAIN_DATE_FRACTION,
    VALIDATION_DATE_FRACTION,
)


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    return date.fromisoformat(text)


def unique_sorted_dates(frame: pd.DataFrame, column: str = "local_date") -> list[date]:
    values = sorted({_as_date(value) for value in frame[column].tolist()})
    return values


def chronological_boundaries(
    dates: list[date],
    train_fraction: float = TRAIN_DATE_FRACTION,
    validation_fraction: float = VALIDATION_DATE_FRACTION,
    test_fraction: float = TEST_DATE_FRACTION,
) -> dict[str, Any]:
    """Split unique dates, not CSV row order.

    All stations that share a calendar date stay in the same partition so the
    test set is a later time period rather than a random station holdout.
    """
    if not dates:
        raise ValueError("Cannot compute a chronological split without dates.")
    total = train_fraction + validation_fraction + test_fraction
    if abs(total - 1.0) > 1e-9:
        raise ValueError("Train, validation, and test fractions must sum to 1.")
    n = len(dates)
    n_train = max(1, int(round(n * train_fraction)))
    n_val = max(1, int(round(n * validation_fraction)))
    if n_train + n_val >= n:
        n_train = max(1, n - 2)
        n_val = 1
    n_test = n - n_train - n_val
    if n_test < 1:
        raise ValueError(f"Not enough unique dates ({n}) for a 70/15/15 split.")
    train_dates = dates[:n_train]
    val_dates = dates[n_train : n_train + n_val]
    test_dates = dates[n_train + n_val :]
    if not (train_dates[-1] < val_dates[0] and val_dates[-1] < test_dates[0]):
        raise ValueError("Chronological partitions are not strictly ordered.")
    return {
        "rule": (
            "Global chronological split on unique local_date values. "
            f"Earliest {train_fraction:.0%} of dates → train, next "
            f"{validation_fraction:.0%} → validation, latest {test_fraction:.0%} → test. "
            "Rows that share a calendar date are never split across partitions."
        ),
        "unique_dates": n,
        "train": _span(train_dates),
        "validation": _span(val_dates),
        "test": _span(test_dates),
        "embargo_rows": 0,
        "embargo_reason": (
            "No embargo gap was added. Lag and rolling features use only past "
            "calendar days, so a date-boundary split does not leak future labels "
            "into the predictors."
        ),
    }


def assign_partition(frame: pd.DataFrame, boundaries: dict[str, Any]) -> pd.Series:
    train_end = date.fromisoformat(boundaries["train"]["last_date"])
    val_end = date.fromisoformat(boundaries["validation"]["last_date"])
    dates = frame["local_date"].map(_as_date)
    out = np.full(len(frame), "test", dtype=object)
    out[dates <= train_end] = "train"
    out[(dates > train_end) & (dates <= val_end)] = "validation"
    return pd.Series(out, index=frame.index, name="partition")


def partition_label_report(frame: pd.DataFrame, partition: pd.Series) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for name in ("train", "validation", "test"):
        part = frame.loc[partition == name]
        labels = part["label"].astype(int)
        n = int(len(part))
        n_pos = int((labels == 1).sum())
        n_neg = int((labels == 0).sum())
        report[name] = {
            "rows": n,
            "positive": n_pos,
            "negative": n_neg,
            "prevalence": (n_pos / n) if n else None,
            "stations": int(part["station"].nunique()) if n else 0,
        }
    return report


def _span(dates: list[date]) -> dict[str, Any]:
    return {
        "first_date": dates[0].isoformat(),
        "last_date": dates[-1].isoformat(),
        "date_count": len(dates),
    }
