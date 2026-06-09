"""Shared utilities + cache config for fundamentals_service submodules."""

import logging
from typing import Protocol, cast

import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS: float = 24 * 3600.0
CACHE_MAX_SIZE: int = 500


class _DataFrameProto(Protocol):
    """Minimal subset of pandas DataFrame surface we use against yfinance frames."""
    index: object
    loc: object


def safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def stringify_period(period: object) -> str:
    """Pandas Timestamp / datetime / date / str → 'YYYY-MM-DD'."""
    from datetime import date as date_type

    if isinstance(period, date_type):
        return period.strftime("%Y-%m-%d")
    text = str(period)
    return text[:10] if len(text) >= 10 else text


def line_item(df: object, candidates: tuple[str, ...]) -> object:
    """Look up the first matching row in a yfinance financial-statement frame.

    Covers naming drift (e.g. "EBIT" vs "Operating Income" vs "Total Operating
    Income") by trying each candidate in order. Returns the row (a pandas
    Series) or None when nothing matches.
    """
    if df is None:
        return None
    frame = cast(_DataFrameProto, df)
    try:
        index = frame.index
    except AttributeError:
        return None
    for name in candidates:
        if name in index:
            try:
                return frame.loc[name]
            except Exception:
                continue
    return None


def consecutive_dividend_growth_years(ticker_obj: yf.Ticker) -> int:
    """Count years of consecutive *annual* dividend increases ending most recently.

    Aggregates yfinance's per-payment dividend series by calendar year, walks
    backwards from the latest *complete* year, increments a counter while
    each year's total exceeds the prior year's. Stops on the first non-increase.
    """
    from datetime import datetime as _dt

    try:
        series = ticker_obj.dividends
    except Exception:
        return 0
    if series is None or series.empty:
        return 0

    by_year: dict[int, float] = {}
    for ts, amount in series.items():
        try:
            year = ts.year
            value = float(amount)
        except (AttributeError, TypeError, ValueError):
            continue
        if value <= 0:
            continue
        by_year[year] = by_year.get(year, 0.0) + value

    if len(by_year) < 2:
        return 0

    # Drop the current calendar year — payouts may not be complete yet, so
    # comparing it to the prior full year would understate streaks.
    current_year = _dt.utcnow().year
    by_year.pop(current_year, None)

    sorted_years = sorted(by_year.keys(), reverse=True)
    if len(sorted_years) < 2:
        return 0

    consecutive = 0
    for i in range(len(sorted_years) - 1):
        cur_year = sorted_years[i]
        prev_year = sorted_years[i + 1]
        if cur_year - prev_year != 1:
            break
        if by_year[cur_year] > by_year[prev_year]:
            consecutive += 1
        else:
            break
    return consecutive
