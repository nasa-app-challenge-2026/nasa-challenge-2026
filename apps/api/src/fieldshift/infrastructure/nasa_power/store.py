"""File storage of raw provider responses: local cache and versioned snapshots.

Each entry is two files: ``<key>.json`` holds the response body byte for byte, and
``<key>.meta.json`` records where and when it was obtained plus its SHA-256. An entry whose
checksum does not match is ignored, so a truncated or edited file can never be served.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from fieldshift.infrastructure.nasa_power.client import PowerDailyRequest, RawResponse

logger = logging.getLogger(__name__)
META_SUFFIX = ".meta.json"


@dataclass(frozen=True, slots=True)
class StoredResponse:
    key: str
    body: bytes
    request_url: str
    retrieved_at: datetime
    sha256: str
    start: date
    end: date
    latitude: float
    longitude: float


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


class ResponseStore:
    def __init__(self, directory: Path, *, writable: bool) -> None:
        self._directory = directory
        self._writable = writable

    @property
    def directory(self) -> Path:
        return self._directory

    def get(self, key: str) -> StoredResponse | None:
        meta_path = self._directory / f"{key}{META_SUFFIX}"
        body_path = self._directory / f"{key}.json"
        if not meta_path.is_file() or not body_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            body = body_path.read_bytes()
            stored = StoredResponse(
                key=key,
                body=body,
                request_url=str(meta["request_url"]),
                retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
                sha256=str(meta["sha256"]),
                start=date.fromisoformat(meta["request"]["start"]),
                end=date.fromisoformat(meta["request"]["end"]),
                latitude=float(meta["request"]["latitude"]),
                longitude=float(meta["request"]["longitude"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("unreadable stored response ignored", extra={"key": key})
            return None
        if sha256_hex(body) != stored.sha256:
            logger.error("stored response failed its checksum and is ignored", extra={"key": key})
            return None
        return stored

    def put(self, request: PowerDailyRequest, raw: RawResponse) -> StoredResponse:
        if not self._writable:
            raise PermissionError("this response store is read-only")
        key = request.key()
        digest = sha256_hex(raw.body)
        meta = {
            "provider": "NASA POWER Daily API",
            "request_url": raw.url,
            "retrieved_at": raw.retrieved_at.isoformat(),
            "sha256": digest,
            "request": {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "parameters": list(request.parameters),
                "community": request.community,
                "time_standard": request.time_standard,
            },
        }
        _atomic_write(self._directory / f"{key}.json", raw.body)
        _atomic_write(
            self._directory / f"{key}{META_SUFFIX}",
            (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
        return StoredResponse(
            key=key,
            body=raw.body,
            request_url=raw.url,
            retrieved_at=raw.retrieved_at,
            sha256=digest,
            start=request.start,
            end=request.end,
            latitude=request.latitude,
            longitude=request.longitude,
        )

    def best_overlap(self, request: PowerDailyRequest) -> StoredResponse | None:
        """Entry for the same cell and parameters overlapping the requested period the most."""
        if not self._directory.is_dir():
            return None
        best: tuple[int, StoredResponse] | None = None
        for meta_path in sorted(self._directory.glob(f"*{META_SUFFIX}")):
            key = meta_path.name.removesuffix(META_SUFFIX)
            stored = self.get(key)
            if stored is None or not _same_series(stored, request):
                continue
            overlap = (min(stored.end, request.end) - max(stored.start, request.start)).days
            if overlap >= 0 and (best is None or overlap > best[0]):
                best = (overlap, stored)
        return best[1] if best else None


def _same_series(stored: StoredResponse, request: PowerDailyRequest) -> bool:
    """Same cell, parameters, community and time standard; only the period may differ."""
    return stored.key == replace(request, start=stored.start, end=stored.end).key()
