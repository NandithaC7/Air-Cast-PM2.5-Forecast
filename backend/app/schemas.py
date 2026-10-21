from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aircast.constants import FEATURE_COLUMNS, MODEL_ORDER


class PredictRequest(BaseModel):
    model_name: str = Field(..., description="One of the four trained classifier keys.")
    sensor_id: int | None = Field(default=None, alias="station_id")
    target_date: str | None = None
    features: dict[str, float | None] | None = None

    model_config = {"populate_by_name": True}

    def validated_model_name(self) -> str:
        key = self.model_name.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "lr": "logistic_regression",
            "logistic": "logistic_regression",
            "dt": "decision_tree",
            "rf": "random_forest",
            "svm": "linear_svm",
            "linearsvc": "linear_svm",
        }
        return aliases.get(key, key)


class PredictHistoryResponse(BaseModel):
    persisted: bool
    reason: str
    items: list[dict[str, Any]]
