"""Discovery source: commodity macro tailwinds via FRED.

For each ticker with known commodity exposure (oil, natural gas, copper, gold,
semiconductor PPI), if the underlying FRED series has risen materially
year-over-year, emit an IdeaSignal. Catches macro setups that precede
insider / corporate-action signals — e.g. NAND/DRAM pricing inflecting up
was the earliest SNDK-thesis signal, before any Form 4 activity.

FRED API docs: https://fred.stlouisfed.org/docs/api/fred/
"""

import asyncio
import logging
import os
import time
from collections import OrderedDict

import httpx

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_FRED_BASE = "https://api.stlouisfed.org/fred"
_PLACEHOLDER_PREFIXES = ("your-", "placeholder", "change-me", "sk-xxx")

_MODERATE_YOY = 10.0   # +20 score
_STRONG_YOY = 25.0     # +30 score
_CACHE_TTL_SECONDS = 24 * 3600.0  # 24h


# commodity_key: (FRED series_id, display_name, unit_label)
# Only series confirmed active on FRED — gold's LBMA fix was discontinued in
# 2017 and the IMF replacement (PGOLDUSDM) also returns 400, so gold needs a
# non-FRED feed (e.g. GLD ETF momentum) before it can be re-introduced.
_SERIES: dict[str, tuple[str, str, str]] = {
    "wti_oil":  ("DCOILWTICO",  "WTI Crude Oil",   "$/bbl"),
    "nat_gas":  ("DHHNGSP",     "Natural Gas",     "$/MMBtu"),
    "copper":   ("PCOPPUSDM",   "Copper",          "$/mt"),
    "semi_ppi": ("PCU334413334413", "Semiconductor PPI", "index"),
}


# Ticker → list of commodity keys it has exposure to
_TICKER_COMMODITY_MAP: dict[str, list[str]] = {
    # Oil / gas majors
    "XOM": ["wti_oil", "nat_gas"], "CVX": ["wti_oil", "nat_gas"],
    "COP": ["wti_oil"], "OXY": ["wti_oil"], "EOG": ["wti_oil"],
    "PSX": ["wti_oil"], "VLO": ["wti_oil"], "MPC": ["wti_oil"],
    "SLB": ["wti_oil"], "HAL": ["wti_oil"], "BKR": ["wti_oil"],
    # Natural gas pure-play
    "KMI": ["nat_gas"], "WMB": ["nat_gas"], "EQT": ["nat_gas"],
    "AR":  ["nat_gas"], "CHK": ["nat_gas"], "RRC": ["nat_gas"],
    # Copper / industrial metals
    "FCX": ["copper"], "SCCO": ["copper"],
    "RIO": ["copper"], "BHP": ["copper"],
    # Semiconductors (SNDK thesis)
    "NVDA": ["semi_ppi"], "AMD": ["semi_ppi"], "INTC": ["semi_ppi"],
    "MU":   ["semi_ppi"], "TSM": ["semi_ppi"], "SNDK": ["semi_ppi"],
    "WDC":  ["semi_ppi"], "AMAT": ["semi_ppi"], "LRCX": ["semi_ppi"],
    "KLAC": ["semi_ppi"], "ASML": ["semi_ppi"], "MRVL": ["semi_ppi"],
    "QCOM": ["semi_ppi"], "AVGO": ["semi_ppi"], "TXN": ["semi_ppi"],
}


# Per-series cache: series_id -> (yoy_pct, timestamp)
_series_cache: OrderedDict[str, tuple[float | None, float]] = OrderedDict()


def _real_fred_key() -> str | None:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        return None
    if any(key.lower().startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return None
    return key


async def _fetch_series_yoy(client: httpx.AsyncClient, series_id: str, api_key: str) -> float | None:
    """Return YoY percent change for a FRED series, or None if unavailable.

    Cached 24h per series.
    """
    now = time.monotonic()
    entry = _series_cache.get(series_id)
    if entry is not None and (now - entry[1]) <= _CACHE_TTL_SECONDS:
        return entry[0]

    url = f"{_FRED_BASE}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": "400",  # ~16 months of daily data; plenty for YoY comparison
    }
    try:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            logger.warning("FRED series %s: HTTP %d", series_id, resp.status_code)
            _series_cache[series_id] = (None, now)
            return None
        data = resp.json()
    except Exception as exc:
        logger.warning("FRED series %s fetch failed: %s", series_id, exc)
        _series_cache[series_id] = (None, now)
        return None

    observations = data.get("observations") or []
    # Extract (date, value) pairs where value is a real number
    parsed: list[tuple[str, float]] = []
    for obs in observations:
        val_str = obs.get("value")
        date = obs.get("date")
        if not val_str or val_str == "." or not date:
            continue
        try:
            parsed.append((date, float(val_str)))
        except (ValueError, TypeError):
            continue

    if len(parsed) < 2:
        _series_cache[series_id] = (None, now)
        return None

    # parsed is in desc order (newest first) — latest is parsed[0]
    latest_date, latest_val = parsed[0]
    # Find observation closest to 12 months prior
    target_year = int(latest_date[:4]) - 1
    target_month = int(latest_date[5:7])
    target_prefix = f"{target_year:04d}-{target_month:02d}"

    prior_val: float | None = None
    # Prefer an exact YYYY-MM match; if none, take the oldest observation available
    for d, v in parsed:
        if d.startswith(target_prefix):
            prior_val = v
            break
    if prior_val is None:
        # Fallback: use the obs closest to target date
        # parsed is desc-ordered; walk forward until we find a date <= target_prefix
        for d, v in parsed:
            if d < target_prefix + "-32":  # i.e. before end of target month
                prior_val = v
                break

    if prior_val is None or prior_val == 0:
        _series_cache[series_id] = (None, now)
        return None

    yoy_pct = ((latest_val - prior_val) / prior_val) * 100.0
    _series_cache[series_id] = (yoy_pct, now)
    return yoy_pct


async def _fetch_all_series_yoy(api_key: str) -> dict[str, float | None]:
    """Fetch YoY for all _SERIES concurrently. Returns commodity_key -> yoy or None."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = {
            ck: _fetch_series_yoy(client, sid, api_key)
            for ck, (sid, _, _) in _SERIES.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    out: dict[str, float | None] = {}
    for ck, res in zip(tasks.keys(), results):
        out[ck] = None if isinstance(res, BaseException) else res
    return out


async def fetch() -> list[tuple[str, IdeaSignal]]:
    api_key = _real_fred_key()
    if not api_key:
        logger.info("commodity_tailwind: FRED_API_KEY not configured, skipping")
        return []

    yoy_by_commodity = await _fetch_all_series_yoy(api_key)
    if not any(v is not None for v in yoy_by_commodity.values()):
        return []

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, commodity_keys in _TICKER_COMMODITY_MAP.items():
        for ck in commodity_keys:
            yoy = yoy_by_commodity.get(ck)
            if yoy is None or yoy < _MODERATE_YOY:
                continue
            series_id, name, _unit = _SERIES[ck]
            score = 30.0 if yoy >= _STRONG_YOY else 20.0
            out.append((ticker, IdeaSignal(
                source="commodity_tailwind",
                score=score,
                label=f"{name} +{yoy:.0f}% YoY",
                detail={
                    "commodity": ck,
                    "yoy_pct": round(yoy, 2),
                    "series_id": series_id,
                    "display_name": name,
                },
            )))
    return out
