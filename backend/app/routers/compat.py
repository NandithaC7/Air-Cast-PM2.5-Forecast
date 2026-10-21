from fastapi import APIRouter, Query

from backend.app.deps import get_catalog, get_store
from backend.app.errors import ApiMessage
from backend.app.services.predictor import run_prediction

router = APIRouter()


@router.get("/forecast")
def forecast(station_id: int = Query(...), target_date: str | None = None) -> dict:
    store = get_store()
    if not store.ready or not store.metrics:
        return {
            "station_id": station_id,
            "available": False,
            "reason": store.reason or "Trained models are not available.",
            "input_date": None,
            "input_data_timestamp": None,
            "target_date": target_date,
            "pm25_input_daily_mean": None,
            "unit": "µg/m³",
            "hazard_class": None,
            "probability": None,
            "probability_supported": False,
            "threshold_ug_m3": None,
            "decision_threshold": None,
            "model": None,
        }
    preferred = store.metrics["selection"]["preferred_model"]
    try:
        return run_prediction(get_catalog(), store, preferred, station_id, target_date, None)
    except ApiMessage as exc:
        if exc.code in {"insufficient_history", "unknown_station", "invalid_date"}:
            return {
                "station_id": station_id,
                "available": False,
                "reason": exc.message,
                "input_date": None,
                "input_data_timestamp": None,
                "target_date": target_date,
                "pm25_input_daily_mean": None,
                "unit": "µg/m³",
                "hazard_class": None,
                "probability": None,
                "probability_supported": False,
                "threshold_ug_m3": None,
                "decision_threshold": None,
                "model": None,
            }
        raise


@router.get("/model/metrics")
def legacy_metrics(station_id: int = Query(...)) -> dict:
    store = get_store()
    if not store.ready or not store.metrics:
        return {
            "available": False,
            "reason": store.reason or "Evaluation artifacts are not available.",
            "model": None,
            "threshold_ug_m3": None,
            "decision_threshold": None,
            "target_recall": None,
            "test": None,
            "baseline": None,
        }
    metrics = store.metrics
    preferred = metrics["selection"]["preferred_model"]
    test = metrics["models"][preferred]["test"]
    persistence = metrics["baselines"]["persistence"]
    _ = station_id
    return {
        "available": True,
        "reason": None,
        "model": {
            "name": preferred,
            "version": metrics["artifact_version"],
            "training_period": {
                "start": metrics["split"]["train"]["first_date"],
                "end": metrics["split"]["train"]["last_date"],
            },
        },
        "threshold_ug_m3": metrics["project"]["hazard_threshold_ug_m3"],
        "decision_threshold": test.get("decision_threshold"),
        "target_recall": None,
        "test": {
            "precision": test.get("precision"),
            "recall": test.get("recall"),
            "f1": test.get("f1"),
            "pr_auc": test.get("pr_auc"),
            "auc_roc": test.get("roc_auc"),
            "n": test.get("n"),
            "confusion": {
                "tp": test["tp"],
                "fp": test["fp"],
                "fn": test["fn"],
                "tn": test["tn"],
            },
        },
        "baseline": {
            "description": persistence.get("description"),
            "precision": persistence.get("precision"),
            "recall": persistence.get("recall"),
            "f1": persistence.get("f1"),
            "pr_auc": persistence.get("pr_auc"),
            "confusion": {
                "tp": persistence["tp"],
                "fp": persistence["fp"],
                "fn": persistence["fn"],
                "tn": persistence["tn"],
            },
            "model_precision_at_baseline_recall": None,
        },
    }
