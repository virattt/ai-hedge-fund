"""FRED (Federal Reserve Economic Data) access for top-down macro inputs.

Provides a single helper, get_macro_snapshot(), returning the macro regime as of a
date: policy rate + direction, yield-curve slope, inflation, and labor trend.

Requires a free FRED API key (https://fred.stlouisfed.org/docs/api/api_key.html)
set as FRED_API_KEY. If the key is absent the snapshot reports available=False and
callers degrade gracefully to a neutral macro reading.
"""

import os
from datetime import datetime

import requests
from dateutil.relativedelta import relativedelta

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# FRED series IDs
_SERIES = {
    "fed_funds": "FEDFUNDS",   # Effective federal funds rate (monthly, %)
    "yield_curve": "T10Y2Y",   # 10Y minus 2Y Treasury spread (daily, %)
    "cpi": "CPIAUCSL",         # CPI-U index, all items (monthly) -> compute YoY
    "unemployment": "UNRATE",  # Unemployment rate (monthly, %)
}

# Simple module-level cache keyed by (series_id, start, end)
_macro_cache: dict[str, list[tuple[str, float]]] = {}


def _fetch_series(series_id: str, start_date: str, end_date: str, api_key: str | None) -> list[tuple[str, float]]:
    """Fetch one FRED series as a list of (date, value), skipping missing points."""
    cache_key = f"{series_id}_{start_date}_{end_date}"
    if cache_key in _macro_cache:
        return _macro_cache[cache_key]

    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        return []

    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
    }
    try:
        response = requests.get(_FRED_BASE, params=params, timeout=30)
        if response.status_code != 200:
            return []
        observations = response.json().get("observations", [])
    except Exception:
        return []

    parsed: list[tuple[str, float]] = []
    for obs in observations:
        value = obs.get("value")
        if value in (None, ".", ""):  # FRED marks missing values with "."
            continue
        try:
            parsed.append((obs["date"], float(value)))
        except (ValueError, KeyError):
            continue

    _macro_cache[cache_key] = parsed
    return parsed


def get_macro_snapshot(end_date: str, api_key: str | None = None) -> dict:
    """Return macro indicators as of end_date, with recent trend where relevant.

    Keys (present only when the underlying series is available):
      fed_funds_rate, fed_funds_6m_change, yield_curve_10y2y,
      cpi_yoy, unemployment_rate, unemployment_6m_change, available
    """
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = (end - relativedelta(years=2)).strftime("%Y-%m-%d")  # 2y window: trend + YoY

    snapshot: dict = {"available": False}

    fed = _fetch_series(_SERIES["fed_funds"], start, end_date, api_key)
    if fed:
        latest = fed[-1][1]
        prior = fed[-7][1] if len(fed) >= 7 else fed[0][1]  # ~6 monthly points back
        snapshot["fed_funds_rate"] = latest
        snapshot["fed_funds_6m_change"] = latest - prior
        snapshot["available"] = True

    curve = _fetch_series(_SERIES["yield_curve"], start, end_date, api_key)
    if curve:
        snapshot["yield_curve_10y2y"] = curve[-1][1]
        snapshot["available"] = True

    cpi = _fetch_series(_SERIES["cpi"], start, end_date, api_key)
    if len(cpi) >= 13:
        latest_cpi = cpi[-1][1]
        year_ago_cpi = cpi[-13][1]
        if year_ago_cpi > 0:
            snapshot["cpi_yoy"] = (latest_cpi / year_ago_cpi - 1) * 100
            snapshot["available"] = True

    unemployment = _fetch_series(_SERIES["unemployment"], start, end_date, api_key)
    if unemployment:
        latest_u = unemployment[-1][1]
        prior_u = unemployment[-7][1] if len(unemployment) >= 7 else unemployment[0][1]
        snapshot["unemployment_rate"] = latest_u
        snapshot["unemployment_6m_change"] = latest_u - prior_u
        snapshot["available"] = True

    return snapshot
