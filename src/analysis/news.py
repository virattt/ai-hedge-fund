"""Pull recent ticker news via yfinance.

yfinance's `.news` attribute returns a list of recent news items shaped:
    [{"title": ..., "publisher": ..., "link": ..., "providerPublishTime": int, ...}, ...]

We normalise into a flat dict and cache for 10 minutes per ticker.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

_TTL = 600
_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _normalise(item: dict) -> Optional[dict]:
    """Normalise the various yfinance news shapes (the schema has changed over versions)."""
    # New shape (Aug 2024+): wraps each entry under "content"
    if isinstance(item.get("content"), dict):
        c = item["content"]
        # Date: ISO string in pubDate
        ts = None
        pub = c.get("pubDate") or c.get("displayTime")
        if pub:
            try:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                ts = None
        link_obj = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
        link = link_obj.get("url") if isinstance(link_obj, dict) else None
        provider_obj = c.get("provider") or {}
        return {
            "title": c.get("title") or "",
            "link": link or "",
            "publisher": (provider_obj.get("displayName") if isinstance(provider_obj, dict) else "") or "",
            "summary": (c.get("summary") or "")[:300],
            "published": ts.isoformat() if ts else "",
            "published_ts": int(ts.timestamp()) if ts else 0,
        }

    # Old shape (≤2024 versions)
    ts = item.get("providerPublishTime")
    return {
        "title": item.get("title") or "",
        "link": item.get("link") or "",
        "publisher": item.get("publisher") or "",
        "summary": (item.get("summary") or "")[:300],
        "published": datetime.fromtimestamp(ts).isoformat() if ts else "",
        "published_ts": int(ts) if ts else 0,
    }


def fetch_news(ticker: str, *, limit: int = 12) -> list[dict]:
    """Return up to `limit` recent news items for the ticker. Cached 10 min."""
    ticker = ticker.upper().strip()
    now = time.time()
    cached = _CACHE.get(ticker)
    if cached and now - cached[0] < _TTL:
        return cached[1][:limit]

    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news or []
    except Exception:
        raw = []

    items: list[dict] = []
    for r in raw:
        n = _normalise(r)
        if n and n["title"]:
            items.append(n)

    # Sort newest first
    items.sort(key=lambda x: x["published_ts"], reverse=True)
    _CACHE[ticker] = (now, items)
    return items[:limit]


def relative_time(iso_string: str) -> str:
    if not iso_string:
        return ""
    try:
        ts = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except Exception:
        return ""
    if ts.tzinfo:
        # Strip tz so we can subtract from naive now() reliably
        ts = ts.replace(tzinfo=None)
    delta = datetime.now() - ts
    s = delta.total_seconds()
    if s < 0:
        return "just now"
    if s < 60:
        return f"{int(s)}s ago"
    if s < 3600:
        return f"{int(s/60)}m ago"
    if s < 86400:
        return f"{int(s/3600)}h ago"
    if s < 86400 * 14:
        return f"{int(s/86400)}d ago"
    return ts.strftime("%Y-%m-%d")
