from __future__ import annotations

from fastapi import APIRouter

from aircast.constants import MODEL_KEYS, MODEL_ORDER
from backend.app.deps import get_store
from backend.app.errors import ApiMessage

router = APIRouter()


def _metrics():
    store = get_store()
    if not store.ready:
        raise ApiMessage(503, store.reason or "Evaluation artifacts are not ready.", "not_ready")
    return store.metrics, store.charts


@router.get("/models")
def list_models() -> dict[str, object]:
    store = get_store()
    return {"models": store.model_status(), "ready": store.ready, "reason": store.reason}


@router.get("/models/metrics")
def model_metrics() -> dict[str, object]:
    metrics, _ = _metrics()
    return metrics


@router.get("/models/comparison")
def model_comparison() -> dict[str, object]:
    _, charts = _metrics()
    assert charts is not None
    return {
        "comparison": charts["comparison"],
        "runtime": charts["runtime"],
        "baselines": charts.get("baselines", {}),
    }


@router.get("/overview")
def overview() -> dict[str, object]:
    from backend.app.deps import get_catalog

    catalog = get_catalog()
    store = get_store()
    payload = catalog.overview()
    if store.ready and store.metrics:
        payload["preferred_model"] = store.metrics["selection"]["preferred_model"]
        payload["preferred_display_name"] = store.metrics["selection"]["preferred_display_name"]
        payload["selection_criterion"] = store.metrics["selection"]["criterion"]
        payload["split"] = store.metrics["split"]
    else:
        payload["preferred_model"] = None
        payload["preferred_display_name"] = None
        payload["selection_criterion"] = None
        payload["split"] = None
    return payload


@router.get("/charts")
def charts() -> dict[str, object]:
    _, charts_payload = _metrics()
    assert charts_payload is not None
    return charts_payload


@router.get("/models/{model_name}")
def model_detail(model_name: str) -> dict[str, object]:
    metrics, charts = _metrics()
    key = _resolve(model_name)
    row = metrics["models"][key]
    return {
        "name": key,
        "display_name": MODEL_KEYS[key],
        "preferred": key == metrics["selection"]["preferred_model"],
        "selection_criterion": metrics["selection"]["criterion"],
        "hyperparameters": row["hyperparameters"],
        "runtime": row["runtime"],
        "validation": row["validation"],
        "test": {k: v for k, v in row["test"].items() if k not in {"roc", "pr"}},
        "split": metrics["split"],
        "feature_schema": metrics["dataset"],
        "available": row["available"],
        "attribution_note": row.get("attribution_note"),
        "charts": {
            "confusion": charts["confusion"][key],
            "curves": charts["curves"][key],
            "feature_attribution": charts["feature_attribution"][key],
        },
    }


@router.get("/models/{model_name}/confusion-matrix")
def confusion_matrix(model_name: str) -> dict[str, object]:
    _, charts = _metrics()
    return charts["confusion"][_resolve(model_name)]


@router.get("/models/{model_name}/curves")
def curves(model_name: str) -> dict[str, object]:
    _, charts = _metrics()
    return charts["curves"][_resolve(model_name)]


@router.get("/models/{model_name}/feature-importance")
def feature_importance(model_name: str) -> dict[str, object]:
    _, charts = _metrics()
    return charts["feature_attribution"][_resolve(model_name)]


def _resolve(name: str) -> str:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "lr": "logistic_regression",
        "logistic": "logistic_regression",
        "dt": "decision_tree",
        "rf": "random_forest",
        "svm": "linear_svm",
        "linearsvc": "linear_svm",
    }
    key = aliases.get(key, key)
    if key not in MODEL_ORDER:
        raise ApiMessage(404, f"Unknown model '{name}'.", "unknown_model")
    return key
