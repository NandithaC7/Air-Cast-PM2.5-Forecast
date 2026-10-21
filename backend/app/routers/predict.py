from fastapi import APIRouter

from aircast.constants import MODEL_KEYS
from backend.app.deps import get_catalog, get_store
from backend.app.errors import ApiMessage
from backend.app.schemas import PredictRequest
from backend.app.services.predictor import run_prediction

router = APIRouter()


@router.post("/predict")
def predict(payload: PredictRequest) -> dict:
    store = get_store()
    if not store.ready:
        raise ApiMessage(503, store.reason or "Models are not ready.", "not_ready")
    return run_prediction(
        get_catalog(),
        store,
        payload.validated_model_name(),
        payload.sensor_id,
        payload.target_date,
        payload.features,
    )


@router.get("/predictions/history")
def prediction_history() -> dict:
    return {
        "persisted": False,
        "reason": "MongoDB is not configured. Prediction history is not stored.",
        "items": [],
        "supported_models": list(MODEL_KEYS.keys()),
    }
