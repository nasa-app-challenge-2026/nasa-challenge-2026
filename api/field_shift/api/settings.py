"""Settings of the server, read from environment variables.

FIELD_SHIFT_WEATHER        "nasa" (default: real NASA POWER weather) or "demo" (fictitious, offline)
FIELD_SHIFT_CORS_ORIGINS   web origins allowed to call the server, separated by commas

The addresses of the NASA and partner data sources (FIELD_SHIFT_DATA_SOURCES, FIELD_SHIFT_URL_…)
are read by `data_access/data_source_config.py`, which documents them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from field_shift.data_access.data_source_config import DataSourceConfig

WEATHER_ENV: Final = "FIELD_SHIFT_WEATHER"
CORS_ENV: Final = "FIELD_SHIFT_CORS_ORIGINS"
#: The development servers of the front end (Vite dev and Vite preview).
DEFAULT_CORS_ORIGINS: Final = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
WEATHER_MODES: Final = ("nasa", "demo")

WeatherMode = Literal["nasa", "demo"]


@dataclass(frozen=True)
class Settings:
    weather: WeatherMode = "nasa"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    #: Addresses of the data sources (the defaults of the code unless read from the environment).
    data_sources: DataSourceConfig = field(default_factory=DataSourceConfig)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environment is None else environment
        weather = env.get(WEATHER_ENV, "nasa").strip().lower() or "nasa"
        if weather not in WEATHER_MODES:
            raise ValueError(
                f"{WEATHER_ENV} doit valoir {' ou '.join(WEATHER_MODES)}, pas {weather!r}"
            )
        origins = tuple(o.strip() for o in env.get(CORS_ENV, "").split(",") if o.strip())
        return cls(
            weather=weather,
            cors_origins=origins or DEFAULT_CORS_ORIGINS,
            data_sources=DataSourceConfig.load(env),
        )
