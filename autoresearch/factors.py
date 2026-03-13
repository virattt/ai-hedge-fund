"""
autoresearch/factors.py — Fundamental & event-based helper signals.

This module reads cached fundamentals/events from autoresearch/cache/ and
exposes small, interpretable factor snapshots that the fast backtester can use
as filters or sizing multipliers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


CACHE_DIR = Path(__file__).resolve().parent / "cache"


@dataclass
class FactorSnapshot:
    ticker: str
    as_of: str
    value_score: float | None
    quality_score: float | None
    leverage_score: float | None
    insider_net_shares: float | None


_METRICS_DF: Dict[str, pd.DataFrame] | None = None
_INSIDER_MAP: Dict[str, List[dict]] | None = None


def _load_metrics(prefix: str) -> Dict[str, pd.DataFrame]:
    global _METRICS_DF
    if _METRICS_DF is not None:
        return _METRICS_DF

    path = CACHE_DIR / f"financial_metrics_{prefix}.json"
    if not path.exists():
        _METRICS_DF = {}
        return _METRICS_DF

    with open(path) as f:
        raw: Dict[str, List[dict]] = json.load(f)

    frames: Dict[str, pd.DataFrame] = {}
    for ticker, rows in raw.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if "report_period" in df.columns:
            df["report_period"] = pd.to_datetime(df["report_period"])
            df = df.sort_values("report_period")
        frames[ticker] = df

    _METRICS_DF = frames
    return frames


def _load_insider(prefix: str) -> Dict[str, List[dict]]:
    global _INSIDER_MAP
    if _INSIDER_MAP is not None:
        return _INSIDER_MAP

    path = CACHE_DIR / f"insider_trades_{prefix}.json"
    if not path.exists():
        _INSIDER_MAP = {}
        return _INSIDER_MAP

    with open(path) as f:
        raw: Dict[str, List[dict]] = json.load(f)

    _INSIDER_MAP = raw
    return raw


def _latest_metrics_before(
    ticker: str,
    as_of: datetime,
    prefix: str,
) -> Optional[pd.Series]:
    frames = _load_metrics(prefix)
    df = frames.get(ticker)
    if df is None or df.empty:
        return None
    if "report_period" not in df.columns:
        return df.iloc[-1]

    mask = df["report_period"] <= as_of
    if not mask.any():
        return None
    return df.loc[mask].iloc[-1]


def _insider_net_shares(
    ticker: str,
    as_of: datetime,
    prefix: str,
    lookback_days: int,
) -> Optional[float]:
    data = _load_insider(prefix)
    trades = data.get(ticker, [])
    if not trades:
        return None

    cutoff = as_of - timedelta(days=lookback_days)
    net = 0.0
    for t in trades:
        filing = t.get("filing_date")
        if not filing:
            continue
        try:
            fd = datetime.fromisoformat(filing.replace("Z", ""))
        except Exception:
            continue
        if fd.date() < cutoff.date() or fd.date() > as_of.date():
            continue
        shares = t.get("transaction_shares")
        if shares is None:
            continue
        try:
            net += float(shares)
        except (TypeError, ValueError):
            continue
    return net


def compute_factor_snapshot(
    ticker: str,
    date_str: str,
    prefix: str,
    insider_lookback_days: int = 365,
) -> Optional[FactorSnapshot]:
    """Return a compact factor snapshot for one ticker as of date_str."""
    try:
        as_of = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    row = _latest_metrics_before(ticker, as_of, prefix)
    if row is None:
        return None

    # Simple, bounded scores based on a handful of intuitive fields.
    pe = float(row.get("price_to_earnings_ratio") or 0.0)
    ev_ebitda = float(row.get("enterprise_value_to_ebitda_ratio") or 0.0)
    ps = float(row.get("price_to_sales_ratio") or 0.0)

    # Value: lower multiples are better. Treat <=0 as neutral.
    comps = [x for x in (pe, ev_ebitda, ps) if x > 0]
    value_score = None
    if comps:
        avg_mult = sum(comps) / len(comps)
        # Map multiples into a 0–1 band (cheap→1, expensive→0) with soft clipping.
        value_score = max(0.0, min(1.0, (30.0 - min(avg_mult, 60.0)) / 30.0))

    roe = float(row.get("return_on_equity") or 0.0)
    roic = float(row.get("return_on_invested_capital") or 0.0)
    gross = float(row.get("gross_margin") or 0.0)
    op_margin = float(row.get("operating_margin") or 0.0)
    net_margin = float(row.get("net_margin") or 0.0)

    quality_components = [roe, roic, gross, op_margin, net_margin]
    qs = [c for c in quality_components if c is not None]
    quality_score = None
    if qs:
        avg_q = sum(qs) / len(qs)
        # Map margins/returns into 0–1 (0%→0, 40%+→1).
        quality_score = max(0.0, min(1.0, avg_q / 40.0))

    debt_to_equity = row.get("debt_to_equity")
    interest_cov = row.get("interest_coverage")
    leverage_score = None
    try:
        d2e = float(debt_to_equity) if debt_to_equity is not None else None
        cov = float(interest_cov) if interest_cov is not None else None
    except (TypeError, ValueError):
        d2e = cov = None

    if d2e is not None or cov is not None:
        # Very rough: penalize very levered names or those with weak coverage.
        score = 0.5
        if d2e is not None:
            if d2e > 3.0:
                score -= 0.25
            elif d2e < 1.0:
                score += 0.1
        if cov is not None:
            if cov < 2.0:
                score -= 0.25
            elif cov > 6.0:
                score += 0.1
        leverage_score = max(0.0, min(1.0, score))

    insider_net = _insider_net_shares(
        ticker=ticker,
        as_of=as_of,
        prefix=prefix,
        lookback_days=insider_lookback_days,
    )

    return FactorSnapshot(
        ticker=ticker,
        as_of=date_str,
        value_score=value_score,
        quality_score=quality_score,
        leverage_score=leverage_score,
        insider_net_shares=insider_net,
    )


def apply_fundamental_rules(
    snapshot: FactorSnapshot | None,
    params,
) -> tuple[bool, float]:
    """
    Apply simple filter/sizing rules based on params.

    Returns:
        (allowed, size_multiplier)
    """
    if snapshot is None:
        # No data → allow but do not scale.
        return True, 1.0

    mult = 1.0
    allowed = True

    # Value filter: penalize expensive names via sizing, but don't hard-ban.
    use_value = getattr(params, "USE_VALUE_FILTER", False)
    min_value = getattr(params, "MIN_VALUE_SCORE", 0.0)
    if use_value and snapshot.value_score is not None:
        if snapshot.value_score < min_value:
            # Down-weight instead of outright blocking the name.
            mult *= getattr(params, "INSIDER_SIZE_MULTIPLIER", 0.5)

    # Quality filter: penalize low-quality names via sizing, but don't hard-ban.
    use_quality = getattr(params, "USE_QUALITY_FILTER", False)
    min_quality = getattr(params, "MIN_QUALITY_SCORE", 0.0)
    if use_quality and snapshot.quality_score is not None:
        if snapshot.quality_score < min_quality:
            mult *= getattr(params, "INSIDER_SIZE_MULTIPLIER", 0.5)

    # Insider filter: down-weight persistent net sellers
    use_insider = getattr(params, "USE_INSIDER_FILTER", False)
    sell_threshold = getattr(params, "INSIDER_NET_SELL_THRESHOLD", 0.0)
    insider_mult = getattr(params, "INSIDER_SIZE_MULTIPLIER", 0.5)
    if use_insider and snapshot.insider_net_shares is not None:
        if snapshot.insider_net_shares < sell_threshold:
            mult *= insider_mult

    return allowed, mult


