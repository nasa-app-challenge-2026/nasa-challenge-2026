"""Runtime configuration, read from ``FIELDSHIFT_*`` environment variables (or ``.env``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from fieldshift.infrastructure.nasa_power.provider import ClimateSourceMode

REPO_ROOT = Path(__file__).resolve().parents[5]
"""``apps/api/src/fieldshift/infrastructure/settings.py`` -> repository root."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FIELDSHIFT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    climate_source: ClimateSourceMode = ClimateSourceMode.LIVE
    """``live`` (cache, then API, then snapshot on failure) or ``snapshot_only`` (offline)."""
    power_base_url: str = "https://power.larc.nasa.gov"
    power_timeout_seconds: float = 60.0
    power_max_attempts: int = 2
    power_max_concurrent_requests: int = 2
    data_dir: Path = REPO_ROOT / "data"
    cache_dir: Path = REPO_ROOT / ".cache"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    @property
    def reference_dir(self) -> Path:
        return self.data_dir / "reference"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots" / "nasa-power"

    @property
    def power_cache_dir(self) -> Path:
        return self.cache_dir / "nasa-power"
