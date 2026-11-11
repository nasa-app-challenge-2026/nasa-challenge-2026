"""HTTP access to the NASA POWER Daily API (acquisition only: no parsing, no caching).

Documentation: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

DAILY_POINT_PATH = "/api/temporal/daily/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")
COMMUNITY = "AG"
TIME_STANDARD = "LST"
"""Local solar time: daily minimum and maximum refer to the local day (the API default)."""
USER_AGENT = "fieldshift/0.1 (NASA Space Apps 2026 prototype)"
RETRYABLE_STATUS = frozenset({500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class PowerDailyRequest:
    latitude: float
    longitude: float
    start: date
    end: date
    parameters: tuple[str, ...] = PARAMETERS
    community: str = COMMUNITY
    time_standard: str = TIME_STANDARD

    def query(self) -> dict[str, str]:
        return {
            "parameters": ",".join(self.parameters),
            "community": self.community,
            "latitude": f"{self.latitude:.4f}",
            "longitude": f"{self.longitude:.4f}",
            "start": self.start.strftime("%Y%m%d"),
            "end": self.end.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": self.time_standard,
        }

    def key(self) -> str:
        """Stable file-name-safe identifier of the request."""
        raw = (
            f"daily_lat{self.latitude:+.3f}_lon{self.longitude:+.3f}_"
            f"{self.start:%Y%m%d}-{self.end:%Y%m%d}_{self.community}_{self.time_standard}_"
            f"{'-'.join(self.parameters)}"
        )
        return re.sub(r"[^A-Za-z0-9_.+-]", "_", raw)


@dataclass(frozen=True, slots=True)
class RawResponse:
    body: bytes
    url: str
    retrieved_at: datetime


class PowerClientError(Exception):
    """The provider could not deliver a response. The message never contains secrets."""


class PowerRateLimitedError(PowerClientError):
    pass


class PowerClient:
    def __init__(
        self,
        http: httpx.Client,
        base_url: str,
        *,
        max_attempts: int = 2,
        backoff_seconds: float = 2.0,
        max_concurrent_requests: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._http = http
        self._url = base_url.rstrip("/") + DAILY_POINT_PATH
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._slots = threading.BoundedSemaphore(max_concurrent_requests)
        self._sleep = sleep
        self._clock = clock

    def fetch(self, request: PowerDailyRequest) -> RawResponse:
        last_error = PowerClientError("no attempt made")
        for attempt in range(1, self._max_attempts + 1):
            try:
                with self._slots:
                    response = self._http.get(self._url, params=request.query())
            except httpx.TimeoutException:
                last_error = PowerClientError("NASA POWER did not answer before the timeout")
            except httpx.TransportError as error:
                last_error = PowerClientError(f"network error: {type(error).__name__}")
            else:
                if response.status_code == 200:
                    return RawResponse(response.content, str(response.url), self._clock())
                if response.status_code == 429:
                    raise PowerRateLimitedError("NASA POWER rate limit reached (HTTP 429)")
                last_error = PowerClientError(f"NASA POWER answered HTTP {response.status_code}")
                if response.status_code not in RETRYABLE_STATUS:
                    raise last_error
            if attempt < self._max_attempts:
                self._sleep(self._backoff_seconds * attempt)
        raise last_error


def build_http_client(timeout_seconds: float) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(timeout_seconds, connect=10.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=False,
    )
