from fastapi import APIRouter, Query

from backend.app.deps import get_catalog, get_store
from backend.app.errors import ApiMessage

router = APIRouter()


@router.get("/stations")
def stations() -> dict:
    return {"stations": get_catalog().stations}


@router.get("/observations")
def observations(
    station_id: int = Query(...),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    if page < 1 or page_size < 1 or page_size > 200:
        raise ApiMessage(422, "page must be >= 1 and page_size must be between 1 and 200.", "invalid_page")
    catalog = get_catalog()
    if catalog.station_or_none(station_id) is None:
        raise ApiMessage(404, f"Unknown station {station_id}.", "unknown_station")
    return catalog.observations(station_id, from_, to, page, page_size)


@router.get("/summary")
def summary(
    station_id: int = Query(...),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
) -> dict:
    catalog = get_catalog()
    if catalog.station_or_none(station_id) is None:
        raise ApiMessage(404, f"Unknown station {station_id}.", "unknown_station")
    return catalog.summary(station_id, from_, to)


@router.get("/pipeline/status")
def pipeline_status() -> dict:
    store = get_store()
    preferred = store.metrics["selection"]["preferred_model"] if store.ready and store.metrics else None
    return get_catalog().pipeline_status(store.ready, preferred)
