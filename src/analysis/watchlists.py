"""Persistent watchlists stored at ``~/.strategist/watchlists.json``.

Survives browser changes, reinstalls, and machine moves (as long as the
directory is preserved). One flat JSON file — list of {id, name, tickers,
created_at, updated_at}.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("STRATEGIST_DATA_DIR", str(Path.home() / ".strategist")))
WATCHLISTS_FILE = DATA_DIR / "watchlists.json"


def _read() -> list[dict]:
    if not WATCHLISTS_FILE.exists():
        return []
    try:
        return json.loads(WATCHLISTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WATCHLISTS_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def list_watchlists() -> list[dict]:
    return _read()


def get_watchlist(wl_id: str) -> Optional[dict]:
    for w in _read():
        if w.get("id") == wl_id:
            return w
    return None


def create_watchlist(name: str, tickers: list[str]) -> dict:
    items = _read()
    wl = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip()[:80] or "Untitled",
        "tickers": _clean_tickers(tickers),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    items.insert(0, wl)
    _write(items)
    return wl


def update_watchlist(wl_id: str, *, name: Optional[str] = None, tickers: Optional[list[str]] = None) -> Optional[dict]:
    items = _read()
    for w in items:
        if w.get("id") == wl_id:
            if name is not None:
                w["name"] = name.strip()[:80] or w["name"]
            if tickers is not None:
                w["tickers"] = _clean_tickers(tickers)
            w["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _write(items)
            return w
    return None


def delete_watchlist(wl_id: str) -> bool:
    items = _read()
    remaining = [w for w in items if w.get("id") != wl_id]
    if len(remaining) == len(items):
        return False
    _write(remaining)
    return True


def _clean_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tickers or []:
        if not isinstance(t, str):
            continue
        ticker = t.strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append(ticker)
    return out[:200]
