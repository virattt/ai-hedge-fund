"""Local file storage for saved snapshots and side-by-side comparisons.

Saved analyses live at:
    ~/.strategist/saved/<TICKER>/<YYYY-MM-DD_HH-MM-SS>.json

Each file is a JSON-serialised SnapshotReport plus a `_meta` block carrying
an optional user note. We keep a flat layout — no DB, no index file — so
the user can `git init` the directory if they want versioned history.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SAVED_DIR = Path(os.environ.get("STRATEGIST_SAVED_DIR", str(Path.home() / ".strategist" / "saved")))


def _coerce(obj: Any):
    """Recursively convert dataclasses, datetimes, NaN floats, etc. into
    plain JSON-safe primitives."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _coerce(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _coerce(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def save_snapshot(report, *, note: str = "") -> dict:
    """Persist a SnapshotReport to disk. Returns the metadata dict."""
    ticker = report.ticker.upper()
    ticker_dir = SAVED_DIR / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = ticker_dir / f"{timestamp}.json"

    data = _coerce(report)
    data["_meta"] = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "note": note.strip()[:500],
        "ticker": ticker,
        "current_price_at_save": report.current_price,
    }
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    return {
        "ticker": ticker,
        "timestamp": timestamp,
        "path": str(path),
        "saved_at": data["_meta"]["saved_at"],
        "note": data["_meta"]["note"],
        "price_at_save": report.current_price,
    }


def list_saved(ticker: Optional[str] = None) -> list[dict]:
    """List saved snapshots, newest first.

    If `ticker` is provided, restrict to that ticker. Otherwise return all
    saves across all tickers.
    """
    if not SAVED_DIR.exists():
        return []
    if ticker:
        tdir = SAVED_DIR / ticker.upper()
        ticker_dirs = [tdir] if tdir.exists() else []
    else:
        ticker_dirs = [d for d in SAVED_DIR.iterdir() if d.is_dir()]

    out: list[dict] = []
    for tdir in ticker_dirs:
        for f in sorted(tdir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = data.get("_meta", {})
            fv = data.get("final_verdict") or {}
            out.append(
                {
                    "ticker": tdir.name,
                    "timestamp": f.stem,
                    "path": str(f),
                    "saved_at": meta.get("saved_at", f.stem),
                    "note": meta.get("note", ""),
                    "price_at_save": data.get("current_price"),
                    "verdict": fv.get("action", "—"),
                    "score": fv.get("composite_score"),
                    "company_name": data.get("company_name", ""),
                }
            )
    # Sort: newest first across tickers
    out.sort(key=lambda x: x["saved_at"], reverse=True)
    return out


def load_saved(ticker: str, timestamp: str) -> Optional[dict]:
    """Load one saved snapshot by (ticker, timestamp). Returns the raw dict
    (not a reconstructed dataclass) for cheap rendering."""
    path = SAVED_DIR / ticker.upper() / f"{timestamp}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_saved(ticker: str, timestamp: str) -> bool:
    path = SAVED_DIR / ticker.upper() / f"{timestamp}.json"
    if path.exists():
        path.unlink()
        return True
    return False
