"""
autoresearch/cache_worldmonitor.py — cache helpers for World Monitor features.

Phase 0 scaffold:
- Persist and load a canonical latest snapshot.
- Keep a jsonl history for research reproducibility.
- No automatic strategy wiring yet.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).resolve().parent / "cache"
LATEST_PATH = CACHE_DIR / "worldmonitor_latest.json"
HISTORY_PATH = CACHE_DIR / "worldmonitor_history.jsonl"


def save_worldmonitor_snapshot(snapshot: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(snapshot, indent=2))

    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot))
        handle.write("\n")


def load_worldmonitor_snapshot() -> dict[str, Any] | None:
    if not LATEST_PATH.exists():
        return None
    try:
        return json.loads(LATEST_PATH.read_text())
    except json.JSONDecodeError:
        return None


def is_snapshot_stale(snapshot: dict[str, Any], max_age_minutes: int) -> bool:
    as_of = snapshot.get("as_of_utc")
    if not isinstance(as_of, str):
        return True
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        return True

    age_seconds = (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()
    return age_seconds > max_age_minutes * 60


def format_worldmonitor_status_line(
    *,
    enabled: bool,
    prefix: str = "  World Monitor:",
    max_age_minutes: int = 180,
) -> str:
    """
    Build a compact status line for logs/CLI output.
    """
    if not enabled:
        return f"{prefix} DISABLED"

    snapshot = load_worldmonitor_snapshot()
    if not snapshot:
        return f"{prefix} ENABLED (snapshot missing)"

    as_of = snapshot.get("as_of_utc", "unknown")
    regime = snapshot.get("wm_macro_regime", "unknown")
    risk = snapshot.get("wm_global_risk_score", "n/a")
    freshness = snapshot.get("wm_data_freshness_seconds")
    freshness_txt = f"{freshness}s" if isinstance(freshness, int) else "n/a"
    stale = is_snapshot_stale(snapshot, max_age_minutes=max_age_minutes)
    stale_txt = "stale" if stale else "fresh"

    return (
        f"{prefix} ENABLED ({stale_txt}, as_of={as_of}, "
        f"regime={regime}, risk={risk}, freshness={freshness_txt})"
    )

