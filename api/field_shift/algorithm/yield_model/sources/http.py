"""Injectable synchronous HTTP transport. No fictitious data or network fallback."""
from __future__ import annotations

import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from field_shift.algorithm.yield_model.config import CONFIG


class Response:
    def __init__(self, response, timeout_ms):
        self._response = response
        self.status = response.status
        self.ok = 200 <= self.status < 300
        self.headers = response.headers
        self.deadline = time.monotonic() + timeout_ms / 1000

    def read(self, size=-1):
        if time.monotonic() > self.deadline:
            raise TimeoutError("Délai HTTP dépassé.")
        data = self._response.read(size)
        if time.monotonic() > self.deadline:
            raise TimeoutError("Délai HTTP dépassé.")
        return data

    def close(self):
        self._response.close()


def fetch(url, *, method="GET", headers=None, body=None, timeout_ms=None):
    """Patch this function in source tests to inject recorded or mock responses."""
    timeout_ms = CONFIG["httpTimeoutMs"] if timeout_ms is None else timeout_ms
    if isinstance(body, str):
        body = body.encode("utf-8")
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        response = urlopen(request, timeout=timeout_ms / 1000)
    except HTTPError as error:
        response = error
    return Response(response, timeout_ms)
