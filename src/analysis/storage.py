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


def save_snapshot(
    report,
    *,
    note: str = "",
    tags: Optional[list[str]] = None,
    source: str = "manual",
) -> dict:
    """Persist a SnapshotReport to disk. Returns the metadata dict.

    Args:
        report: SnapshotReport instance.
        note: Free-text user note (≤500 chars).
        tags: Optional list of tags (research / watchlist / decision /
              position-entered / auto / custom).
        source: 'manual' or 'auto' — recorded in _meta.
    """
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
        "tags": [t.strip().lower() for t in (tags or []) if t and t.strip()][:8],
        "source": source,
    }
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    return {
        "ticker": ticker,
        "timestamp": timestamp,
        "path": str(path),
        "saved_at": data["_meta"]["saved_at"],
        "note": data["_meta"]["note"],
        "tags": data["_meta"]["tags"],
        "source": source,
        "price_at_save": report.current_price,
    }


def already_saved_today(ticker: str, source: str = "auto") -> bool:
    """Idempotency check for auto-save: did we already save this ticker today
    via the given source? Used so opening a detail page repeatedly with
    auto-save on doesn't create dozens of identical files per day."""
    ticker_dir = SAVED_DIR / ticker.upper()
    if not ticker_dir.exists():
        return False
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    for f in ticker_dir.glob(f"{today_prefix}_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("_meta", {}).get("source") == source:
                return True
        except Exception:
            continue
    return False


def update_tags(ticker: str, timestamp: str, tags: list[str]) -> bool:
    """Rewrite the _meta.tags for an existing saved snapshot."""
    path = SAVED_DIR / ticker.upper() / f"{timestamp}.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("_meta", {})["tags"] = [
            t.strip().lower() for t in tags if t and t.strip()
        ][:8]
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return True
    except Exception:
        return False


def list_saved(
    ticker: Optional[str] = None,
    *,
    tag: Optional[str] = None,
) -> list[dict]:
    """List saved snapshots, newest first.

    Args:
        ticker: Restrict to one ticker.
        tag: Restrict to saves that include this tag.
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
            tags = meta.get("tags") or []
            if tag and tag.lower() not in [t.lower() for t in tags]:
                continue
            out.append(
                {
                    "ticker": tdir.name,
                    "timestamp": f.stem,
                    "path": str(f),
                    "saved_at": meta.get("saved_at", f.stem),
                    "note": meta.get("note", ""),
                    "tags": tags,
                    "source": meta.get("source", "manual"),
                    "price_at_save": data.get("current_price"),
                    "verdict": fv.get("action", "—"),
                    "score": fv.get("composite_score"),
                    "price_target_mid": fv.get("price_target_mid"),
                    "price_target_low": fv.get("price_target_low"),
                    "price_target_high": fv.get("price_target_high"),
                    "hold_period_label": fv.get("hold_period_label"),
                    "hold_period_months_min": fv.get("hold_period_months_min"),
                    "hold_period_months_max": fv.get("hold_period_months_max"),
                    "company_name": data.get("company_name", ""),
                }
            )
    out.sort(key=lambda x: x["saved_at"], reverse=True)
    return out


def list_all_tags() -> list[tuple[str, int]]:
    """All tags seen across saves, with counts. Sorted by count desc."""
    counter: dict[str, int] = {}
    for item in list_saved():
        for t in item.get("tags") or []:
            counter[t] = counter.get(t, 0) + 1
    return sorted(counter.items(), key=lambda kv: -kv[1])


def evaluate_target_hits(
    items: list[dict], current_prices: dict[str, float]
) -> list[dict]:
    """For each saved item, compute whether the saved 12M-mid target has been
    reached (or exceeded) by the current price.

    For BUY/STRONG BUY: hit if current_price >= price_target_mid
    For SELL/REDUCE:   hit if current_price <= price_target_mid
    For HOLD:          no target check (target is "current")
    """
    out = []
    for it in items:
        item = dict(it)  # copy
        cur = current_prices.get(it["ticker"])
        item["current_price_now"] = cur
        item["realized_pct"] = None
        item["target_hit"] = None
        item["target_progress_pct"] = None
        if cur is not None and it.get("price_at_save"):
            try:
                item["realized_pct"] = cur / float(it["price_at_save"]) - 1.0
            except Exception:
                pass
        target = it.get("price_target_mid")
        verdict = (it.get("verdict") or "").upper()
        if target and cur is not None and it.get("price_at_save"):
            try:
                target_f = float(target)
                cur_f = float(cur)
                save_p = float(it["price_at_save"])
                if "BUY" in verdict:
                    item["target_hit"] = cur_f >= target_f
                    # Progress: from save_price to target_price
                    if target_f != save_p:
                        progress = (cur_f - save_p) / (target_f - save_p)
                        item["target_progress_pct"] = max(0.0, min(1.5, progress))
                elif "SELL" in verdict or "REDUCE" in verdict:
                    item["target_hit"] = cur_f <= target_f
                    if target_f != save_p:
                        progress = (save_p - cur_f) / (save_p - target_f)
                        item["target_progress_pct"] = max(0.0, min(1.5, progress))
                else:
                    item["target_hit"] = abs(cur_f / save_p - 1) < 0.15
            except Exception:
                pass
        out.append(item)
    return out


def journal_summary(items: list[dict], current_prices: dict[str, float]) -> dict:
    """Aggregate stats for the journal dashboard."""
    items = evaluate_target_hits(items, current_prices)

    by_verdict: dict[str, list[dict]] = {"BUY": [], "STRONG BUY": [], "HOLD": [], "REDUCE": [], "SELL": []}
    for it in items:
        v = (it.get("verdict") or "").upper()
        if v in by_verdict:
            by_verdict[v].append(it)

    summary = {
        "total": len(items),
        "by_verdict": {k: len(v) for k, v in by_verdict.items()},
        "hit_rate": {},
        "avg_return": {},
        "avg_hold_days": {},
        "target_hit_count": 0,
        "target_miss_count": 0,
    }
    for v, lst in by_verdict.items():
        if not lst:
            continue
        hits = [x for x in lst if x.get("target_hit") is True]
        misses = [x for x in lst if x.get("target_hit") is False]
        if hits or misses:
            summary["hit_rate"][v] = len(hits) / (len(hits) + len(misses)) if (hits or misses) else None
            summary["target_hit_count"] += len(hits)
            summary["target_miss_count"] += len(misses)
        rets = [x.get("realized_pct") for x in lst if x.get("realized_pct") is not None]
        if rets:
            summary["avg_return"][v] = sum(rets) / len(rets)
        # Avg hold days (from saved_at to now)
        from datetime import datetime as _dt
        days = []
        now = _dt.now()
        for x in lst:
            try:
                saved_at = _dt.fromisoformat(x["saved_at"])
                days.append((now - saved_at).total_seconds() / 86400)
            except Exception:
                continue
        if days:
            summary["avg_hold_days"][v] = sum(days) / len(days)

    summary["best"] = sorted(
        [x for x in items if x.get("realized_pct") is not None],
        key=lambda x: x["realized_pct"],
        reverse=True,
    )[:5]
    summary["worst"] = sorted(
        [x for x in items if x.get("realized_pct") is not None],
        key=lambda x: x["realized_pct"],
    )[:5]
    summary["recent"] = items[:10]
    summary["all"] = items
    return summary


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
