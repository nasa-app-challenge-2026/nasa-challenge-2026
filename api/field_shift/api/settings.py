"""Settings of the server, read from environment variables.

FIELD_SHIFT_CORS_ORIGINS   web origins allowed to call the server, separated by commas
FIELD_SHIFT_WORKERS        worker processes that plan the sections of a farm at the same time
                           (`services/parallel_plan_service.py`); 0 = one section after the other

The addresses of the data services (FIELD_SHIFT_DATA_SOURCES, FIELD_SHIFT_URL_…) are read by
`data_access/data_source_config.py`, which documents them. There is no demo mode: the server
always reads the real data, and answers 502 when a service fails.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from field_shift.data_access.data_source_config import DataSourceConfig
from field_shift.services.parallel_plan_service import workers_from_environment

CORS_ENV: Final = "FIELD_SHIFT_CORS_ORIGINS"
#: The development servers of the front end (Vite dev and Vite preview).
DEFAULT_CORS_ORIGINS: Final = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    #: Addresses of the data services (the defaults of the code unless read from the environment).
    data_sources: DataSourceConfig = field(default_factory=DataSourceConfig)
    #: Worker processes of the plan (0: the tests and `Settings()` plan in one process).
    workers: int = 0

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environment is None else environment
        origins = tuple(o.strip() for o in env.get(CORS_ENV, "").split(",") if o.strip())
        return cls(
            cors_origins=origins or DEFAULT_CORS_ORIGINS,
            data_sources=DataSourceConfig.load(env),
            workers=workers_from_environment(env),
        )
