from __future__ import annotations

from functools import lru_cache

from backend.app.config import get_settings
from backend.app.services.catalog import DataCatalog
from backend.app.services.store import ArtifactStore


@lru_cache
def get_store() -> ArtifactStore:
    return ArtifactStore(get_settings().repo)


@lru_cache
def get_catalog() -> DataCatalog:
    return DataCatalog(get_settings().repo)
