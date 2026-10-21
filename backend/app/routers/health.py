from fastapi import APIRouter, Response

from backend.app.deps import get_store

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aircast-india"}


@router.get("/ready")
def ready(response: Response) -> dict[str, object]:
    store = get_store()
    if not store.ready:
        response.status_code = 503
        return {"ready": False, "reason": store.reason}
    metrics, _ = store.require()
    return {
        "ready": True,
        "preferred_model": metrics["selection"]["preferred_model"],
        "generated_at": metrics["generated_at"],
    }
