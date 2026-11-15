"""What the data services answered, kept on disk: a request is made once, then read from here.

Every reader of `data_access` goes through `DataCache.get_or_fetch(namespace, key, fetch)`:

    - the answer is in memory (the last ones read)          → returned at once;
    - it is on disk (a previous request, even before a restart of the server) → read, returned;
    - else `fetch()` reads the service; its answer is written to disk, then returned.

Two requests of the same key at the same time wait for each other: the service is read once (the
sections of a farm are planned in parallel and share the weather of their place). A failure is
never kept: the service is tried again at the next request.

Several processes share the folder (`services/parallel_plan_service.py`). Two of them may write the
same answer at the same time; on Windows, replacing a file another process is replacing or reading
is refused for a moment. The write is then tried again, and given up after a few tries: the answer
stays in memory, and the other process has written the same one.

The folder is `api/.cache_field_shift/` (excluded from git), or the one named by the environment
variable FIELD_SHIFT_CACHE_DIR. Deleting it only means the services are read again.

The values are JSON (dicts, lists, numbers, strings). A key is any text; the file name is its
SHA-256, and the key itself is written in the file to be read by a human.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeVar

T = TypeVar("T")

CACHE_DIR_ENV: Final = "FIELD_SHIFT_CACHE_DIR"
DEFAULT_CACHE_DIR: Final = Path(__file__).resolve().parents[2] / ".cache_field_shift"
#: Answers kept in memory as well (the biggest, the weather of a place, is about 2 MB).
MEMORY_ENTRIES: Final = 64
_FILE_NAME_CHARS: Final = 32
#: Tries to replace a file another process holds for a moment (Windows), and the wait between.
REPLACE_ATTEMPTS: Final = 5
REPLACE_WAIT_S: Final = 0.05


class DataCache:
    """A cache of the answers of the data services, on disk (and the last ones in memory).

    `root=None` keeps everything in memory only (the tests)."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._memory: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[tuple[str, str], threading.Lock] = {}

    @classmethod
    def default(cls) -> DataCache:
        """The cache of the server: FIELD_SHIFT_CACHE_DIR, else api/.cache_field_shift/."""
        named = os.environ.get(CACHE_DIR_ENV, "").strip()
        return cls(Path(named) if named else DEFAULT_CACHE_DIR)

    @classmethod
    def in_memory(cls) -> DataCache:
        return cls(None)

    @property
    def root(self) -> Path | None:
        return self._root

    def _path(self, namespace: str, key: str) -> Path | None:
        if self._root is None:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:_FILE_NAME_CHARS]
        return self._root / namespace / f"{digest}.json"

    def _remember(self, entry: tuple[str, str], value: Any) -> None:
        with self._lock:
            self._memory[entry] = value
            self._memory.move_to_end(entry)
            while len(self._memory) > MEMORY_ENTRIES:
                self._memory.popitem(last=False)

    def get(self, namespace: str, key: str) -> Any | None:
        """The value kept for the key, or None."""
        entry = (namespace, key)
        with self._lock:
            if entry in self._memory:
                self._memory.move_to_end(entry)
                return self._memory[entry]
        path = self._path(namespace, key)
        if path is None or not path.is_file():
            return None
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # a file cut by a crash: the service is read again
        if not isinstance(stored, dict) or stored.get("key") != key:
            return None
        self._remember(entry, stored["value"])
        return stored["value"]

    def remember(self, namespace: str, key: str, value: Any) -> None:
        """Keeps the value in memory only, until the server stops: an answer the service may
        complete later (a catalogue still being filled), read again at the next start."""
        self._remember((namespace, key), value)

    def put(self, namespace: str, key: str, value: Any) -> None:
        """Keeps the value (atomically on disk: a file is never half written)."""
        self._remember((namespace, key), value)
        path = self._path(namespace, key)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            # NaN is written as Python's json writes it (and reads it back): a missing value
            temporary.write_text(
                json.dumps({"key": key, "value": value}, ensure_ascii=False), encoding="utf-8"
            )
            _replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def get_or_fetch(self, namespace: str, key: str, fetch: Callable[[], T]) -> T:
        """The kept value, or the one `fetch()` reads (then kept). Exceptions are not kept."""
        value = self.get(namespace, key)
        if value is not None:
            return value
        entry = (namespace, key)
        with self._lock:
            key_lock = self._key_locks.setdefault(entry, threading.Lock())
        with key_lock:  # the same key asked twice at once: read once
            value = self.get(namespace, key)
            if value is None:
                value = fetch()
                self.put(namespace, key, value)
        return value


def _replace(temporary: Path, path: Path) -> None:
    """Moves the written file in place; gives up quietly when another process keeps the file busy
    (it is writing the same answer)."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt + 1 < REPLACE_ATTEMPTS:
                time.sleep(REPLACE_WAIT_S * (attempt + 1))
