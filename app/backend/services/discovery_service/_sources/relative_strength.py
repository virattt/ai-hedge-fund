"""Discovery source: tickers outperforming their sector ETF over trailing 90 days.

Technical confirmation signal — prevents the "value trap" of buying tickers
that look great fundamentally but are technically broken charts. A ticker
beating its sector by 5%+ over 90 days is showing real institutional accumulation.

Sector ETF basis (not SPY) so the comparison is fair across cycles — energy
shouldn't be punished when oil is cyclical, semis shouldn't be punished when
they're rotating. SMH used for semiconductors (vs the broader XLK) since semi
prices cycle independently from the rest of tech.

Score tiers:
  - +15 when alpha vs sector ≥ 5%
  - +25 when alpha vs sector ≥ 15%
  - +35 when alpha vs sector ≥ 30% (extreme RS: small cap doubling while sector flat)
"""

import asyncio
import logging
from datetime import date, timedelta

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 90
_MIN_ALPHA_PCT = 5.0
_STRONG_ALPHA_PCT = 15.0
_EXTREME_ALPHA_PCT = 30.0


# Ticker → sector ETF benchmark for relative-strength comparison.
# Curated list of ~60 large caps across 11 sectors. Add tickers as needed.
_TICKER_SECTOR_ETF: dict[str, str] = {
    # Semiconductors (use SMH, the dedicated semi ETF — cycles independently from XLK)
    "NVDA": "SMH", "AMD": "SMH", "INTC": "SMH", "MU": "SMH", "TSM": "SMH",
    "AVGO": "SMH", "QCOM": "SMH", "TXN": "SMH", "MRVL": "SMH", "AMAT": "SMH",
    "LRCX": "SMH", "KLAC": "SMH", "ASML": "SMH", "SNDK": "SMH", "WDC": "SMH",
    # Tech (non-semi) — XLK
    "AAPL": "XLK", "MSFT": "XLK", "ORCL": "XLK", "CRM": "XLK", "ADBE": "XLK",
    "NOW": "XLK", "INTU": "XLK", "CSCO": "XLK", "IBM": "XLK", "ACN": "XLK",
    # Communication services — XLC
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC", "DIS": "XLC", "T": "XLC",
    "VZ": "XLC", "CMCSA": "XLC",
    # Financials — XLF
    "JPM": "XLF", "BAC": "XLF", "WFC": "XLF", "GS": "XLF", "MS": "XLF",
    "C": "XLF", "AXP": "XLF", "BLK": "XLF", "SCHW": "XLF",
    # Healthcare — XLV
    "JNJ": "XLV", "UNH": "XLV", "PFE": "XLV", "LLY": "XLV", "ABBV": "XLV",
    "MRK": "XLV", "TMO": "XLV", "ABT": "XLV", "DHR": "XLV",
    # Energy — XLE
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "OXY": "XLE", "EOG": "XLE",
    "SLB": "XLE", "PSX": "XLE", "VLO": "XLE", "MPC": "XLE", "HAL": "XLE",
    "BKR": "XLE", "KMI": "XLE", "WMB": "XLE", "EQT": "XLE",
    # Consumer discretionary — XLY
    "AMZN": "XLY", "TSLA": "XLY", "HD": "XLY", "MCD": "XLY", "NKE": "XLY",
    "SBUX": "XLY", "LOW": "XLY", "BKNG": "XLY",
    # Consumer staples — XLP
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "WMT": "XLP", "COST": "XLP",
    "PM": "XLP", "MO": "XLP",
    # Industrials — XLI
    "CAT": "XLI", "BA": "XLI", "HON": "XLI", "UPS": "XLI", "GE": "XLI",
    "LMT": "XLI", "RTX": "XLI", "DE": "XLI",
    # Materials — XLB
    "LIN": "XLB", "APD": "XLB", "SHW": "XLB", "NEM": "XLB", "FCX": "XLB",
    "SCCO": "XLB",
    # Utilities — XLU
    "NEE": "XLU", "DUK": "XLU", "SO": "XLU", "AEP": "XLU",
    # Real estate — XLRE
    "PLD": "XLRE", "AMT": "XLRE", "EQIX": "XLRE", "SPG": "XLRE",
}


async def fetch() -> list[tuple[str, IdeaSignal]]:
    from app.backend.services.pricing_service import get_period_return

    since = date.today() - timedelta(days=_LOOKBACK_DAYS)

    # Pre-fetch all unique sector ETFs in parallel (cached after first call)
    unique_etfs = sorted(set(_TICKER_SECTOR_ETF.values()))
    etf_returns: dict[str, float] = {}
    etf_tasks = [get_period_return(etf, since) for etf in unique_etfs]
    etf_results = await asyncio.gather(*etf_tasks, return_exceptions=True)
    for etf, res in zip(unique_etfs, etf_results, strict=True):
        if isinstance(res, BaseException) or res is None:
            continue
        etf_returns[etf] = (res.end_price / res.start_price - 1.0) * 100.0

    if not etf_returns:
        logger.info("relative_strength: no sector ETF returns available")
        return []

    # Compute per-ticker returns in parallel
    eligible: list[tuple[str, str]] = [
        (t, sector_etf)
        for t, sector_etf in _TICKER_SECTOR_ETF.items()
        if sector_etf in etf_returns
    ]
    ticker_tasks = [get_period_return(t, since) for t, _ in eligible]
    ticker_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)

    out: list[tuple[str, IdeaSignal]] = []
    for (ticker, sector_etf), res in zip(eligible, ticker_results, strict=True):
        if isinstance(res, BaseException) or res is None:
            continue
        ticker_return_pct = (res.end_price / res.start_price - 1.0) * 100.0
        sector_return_pct = etf_returns[sector_etf]
        alpha = ticker_return_pct - sector_return_pct
        if alpha < _MIN_ALPHA_PCT:
            continue

        if alpha >= _EXTREME_ALPHA_PCT:
            score = 35.0
        elif alpha >= _STRONG_ALPHA_PCT:
            score = 25.0
        else:
            score = 15.0

        label = f"+{alpha:.0f}% vs {sector_etf} (90d)"
        out.append((ticker, IdeaSignal(
            source="relative_strength",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "sector_etf": sector_etf,
                "ticker_return_pct": ticker_return_pct,
                "sector_return_pct": sector_return_pct,
                "alpha_pct": alpha,
                "lookback_days": _LOOKBACK_DAYS,
            },
        )))
    return out
