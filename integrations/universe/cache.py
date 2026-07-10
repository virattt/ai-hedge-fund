"""Tiny JSON disk cache so universe builds and backtests don't re-hit APIs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize(part: str) -> str:
    return _SAFE.sub("_", part)


class JsonDiskCache:
    """Namespaced JSON cache: one file per (namespace, key)."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, namespace: str, key: str) -> Path:
        return self._root / _sanitize(namespace) / f"{_sanitize(key)}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        path = self._path(namespace, key)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
