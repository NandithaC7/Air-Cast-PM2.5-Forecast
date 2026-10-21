from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from aircast.paths import repo_root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIRCAST_", env_file=".env", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    timezone: str = "Asia/Kolkata"
    mongodb_uri: str = ""
    root: Path | None = None

    @property
    def repo(self) -> Path:
        return Path(self.root).resolve() if self.root else repo_root()

    @property
    def origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def mongodb_enabled(self) -> bool:
        return bool(self.mongodb_uri.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
