"""
autoresearch/cache_worldmonitor_signals.py — fetch and cache World Monitor signals.

Phase 1 (initial):
- Pulls a concrete endpoint from World Monitor API.
- Derives a coarse global risk score from quote data (VIX-aware when present).
- Normalizes to canonical feature schema and stores latest + history cache.

Usage:
    poetry run python -m autoresearch.cache_worldmonitor_signals
    poetry run python -m autoresearch.cache_worldmonitor_signals --symbols SPY,VIX,QQQ
"""

from __future__ import annotations

import argparse
from typing import Any

from autoresearch.cache_worldmonitor import save_worldmonitor_snapshot
from src.data.worldmonitor_client import WorldMonitorClient
from src.data.worldmonitor_features import normalize_worldmonitor_payload

DEFAULT_QUOTES_ENDPOINT = "/api/market/v1/list-market-quotes"


def _extract_quotes(raw: dict[str, Any]) -> dict[str, float]:
    """
    Best-effort parser for quote payloads with unknown exact schema.
    Returns symbol -> last_price.
    """
    candidates = []
    if isinstance(raw.get("quotes"), list):
        candidates = raw["quotes"]
    elif isinstance(raw.get("data"), list):
        candidates = raw["data"]
    elif isinstance(raw.get("results"), list):
        candidates = raw["results"]
    elif isinstance(raw, list):
        candidates = raw

    out: dict[str, float] = {}
    for row in candidates:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol") or row.get("ticker")
        price = row.get("price") or row.get("last") or row.get("close")
        if not isinstance(symbol, str) or not isinstance(price, (int, float)):
            continue
        out[symbol.upper()] = float(price)
    return out


def _global_risk_from_quotes(quotes: dict[str, float]) -> float | None:
    """
    Coarse mapping from VIX-like quote to 0-100 risk scale.
    """
    vix = None
    for key in ("VIX", "^VIX", "VIXY"):
        if key in quotes:
            vix = quotes[key]
            break
    if vix is None:
        return None
    # vix=10 -> 0, vix=20 -> 40, vix=30 -> 80, clipped 0-100
    score = (vix - 10.0) * 4.0
    return max(0.0, min(100.0, score))


def fetch_and_cache_worldmonitor_signals(
    *,
    endpoint: str = DEFAULT_QUOTES_ENDPOINT,
    symbols: str = "SPY,VIX,QQQ",
    source_version: str = "phase1-market-quotes",
    ttl_seconds: int = 1800,
) -> dict[str, Any]:
    client = WorldMonitorClient()
    raw = client.get_json(endpoint, params={"symbols": symbols})

    quotes = _extract_quotes(raw if isinstance(raw, dict) else {})
    payload = {
        "global_risk_score": _global_risk_from_quotes(quotes),
        "quotes": quotes,
        "data_freshness_seconds": 0,
    }
    snapshot = normalize_worldmonitor_payload(
        payload,
        source_endpoint=endpoint,
        source_version=source_version,
        ttl_seconds=ttl_seconds,
    )
    snapshot_dict = snapshot.to_dict()
    save_worldmonitor_snapshot(snapshot_dict)
    return snapshot_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache World Monitor feature snapshot")
    parser.add_argument(
        "--endpoint",
        type=str,
        default=DEFAULT_QUOTES_ENDPOINT,
        help="World Monitor API endpoint path",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,VIX,QQQ",
        help="Comma-separated symbol list for market quotes endpoint",
    )
    parser.add_argument(
        "--source-version",
        type=str,
        default="phase1-market-quotes",
        help="Source version tag stored with snapshot metadata",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=1800,
        help="TTL metadata for downstream freshness checks",
    )
    args = parser.parse_args()

    snapshot = fetch_and_cache_worldmonitor_signals(
        endpoint=args.endpoint,
        symbols=args.symbols,
        source_version=args.source_version,
        ttl_seconds=args.ttl_seconds,
    )
    print(
        "World Monitor snapshot cached:",
        {
            "as_of_utc": snapshot.get("as_of_utc"),
            "wm_macro_regime": snapshot.get("wm_macro_regime"),
            "wm_global_risk_score": snapshot.get("wm_global_risk_score"),
            "source_endpoint": snapshot.get("source_endpoint"),
        },
    )


if __name__ == "__main__":
    main()

