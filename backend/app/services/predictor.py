from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from aircast.constants import FEATURE_COLUMNS, HAZARD_THRESHOLD_UG_M3, MODEL_KEYS, TIMEZONE
from aircast.inference import predict_from_features
from backend.app.errors import ApiMessage
from backend.app.services.catalog import DataCatalog
from backend.app.services.store import ArtifactStore


def next_day(value: date) -> date:
    return value + timedelta(days=1)


def previous_day(value: date) -> date:
    return value - timedelta(days=1)


def parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiMessage(422, f"{field} must be an ISO calendar date (YYYY-MM-DD).", "invalid_date") from exc


def run_prediction(
    catalog: DataCatalog,
    store: ArtifactStore,
    model_name: str,
    sensor_id: int | None,
    target_date: str | None,
    features: dict[str, float | None] | None,
) -> dict[str, Any]:
    metrics, bundle = store.require()
    if model_name not in MODEL_KEYS:
        raise ApiMessage(404, f"Unknown model '{model_name}'.", "unknown_model")
    if model_name not in bundle["models"]:
        raise ApiMessage(503, f"Model '{model_name}' has no inference artifact.", "model_unavailable")

    row = None
    input_date: date | None = None
    station_name = None
    if features is None:
        if sensor_id is None:
            raise ApiMessage(422, "Provide sensor_id or a complete features object.", "invalid_request")
        if catalog.station_or_none(sensor_id) is None:
            raise ApiMessage(404, f"No feature coverage for sensor {sensor_id}.", "unknown_station")
        if target_date:
            forecast_day = parse_iso_date(target_date, "target_date")
            input_date = previous_day(forecast_day)
            row = catalog.feature_row(sensor_id, input_date)
            if row is None:
                raise ApiMessage(
                    422,
                    (
                        f"Prediction unavailable: sensor {sensor_id} has no labelled feature row "
                        f"for {input_date.isoformat()}, the local day before {forecast_day.isoformat()}."
                    ),
                    "insufficient_history",
                )
        else:
            row = catalog.latest_feature_row(sensor_id)
            if row is None:
                raise ApiMessage(422, "Prediction unavailable: insufficient historical observations.", "insufficient_history")
            input_date = row["local_date"]
        station_name = str(row["station"])
        feature_values = {name: _optional_float(row[name]) for name in FEATURE_COLUMNS}
        forecast_day = next_day(input_date)
    else:
        missing = [name for name in FEATURE_COLUMNS if name not in features]
        if missing:
            raise ApiMessage(422, f"features is missing required keys: {missing}.", "invalid_features")
        feature_values = {name: features[name] for name in FEATURE_COLUMNS}
        if target_date:
            forecast_day = parse_iso_date(target_date, "target_date")
            input_date = previous_day(forecast_day)
        else:
            forecast_day = None
            input_date = None

    result = predict_from_features(model_name, feature_values, bundle)
    predicted = int(result["predicted_class"])
    hazard_class = "hazard" if predicted == 1 else "no_hazard"
    probability_supported = result["score_kind"] == "probability" and result["probability"] is not None
    interpretation = (
        "Elevated PM2.5 hazard predicted for the next local calendar day."
        if predicted == 1
        else "No elevated hazard predicted by this model."
    )
    return {
        "available": True,
        "reason": None,
        "station_id": sensor_id,
        "station": station_name,
        "input_date": input_date.isoformat() if input_date else None,
        "input_data_timestamp": None,
        "target_date": forecast_day.isoformat() if forecast_day else None,
        "forecast_target_date": forecast_day.isoformat() if forecast_day else None,
        "pm25_input_daily_mean": feature_values.get("daily_mean_pm25"),
        "unit": "µg/m³",
        "hazard_class": hazard_class,
        "predicted_class": predicted,
        "interpretation": interpretation,
        "probability": result["probability"] if probability_supported else None,
        "probability_supported": probability_supported,
        "decision_score": result["decision_score"],
        "score_kind": result["score_kind"],
        "threshold_ug_m3": HAZARD_THRESHOLD_UG_M3,
        "decision_threshold": result["decision_threshold"],
        "timezone": TIMEZONE,
        "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_validation": "ok",
        "model": {
            "name": model_name,
            "display_name": MODEL_KEYS[model_name],
            "version": bundle.get("artifact_version"),
            "training_period": {
                "start": metrics["split"]["train"]["first_date"],
                "end": metrics["split"]["train"]["last_date"],
            },
        },
    }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
