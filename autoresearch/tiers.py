"""
autoresearch/tiers.py — Sleeve + tier metadata wired from SOUL.md.

This module encodes the tier (A/B/C) and sleeve for each ticker in the two-sleeve
AI infra thesis, so portfolio sizing and reporting code can reason about core
choke points vs builders vs satellites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class TickerMeta:
    tier: str  # "A", "B", "C"
    sleeve: str  # "tastytrade" or "hyperliquid"


TICKER_META: Dict[str, TickerMeta] = {
    # Tastytrade sleeve — Tier A (core choke points)
    "ASML": TickerMeta(tier="A", sleeve="tastytrade"),
    "AMAT": TickerMeta(tier="A", sleeve="tastytrade"),
    "KLAC": TickerMeta(tier="A", sleeve="tastytrade"),
    "LRCX": TickerMeta(tier="A", sleeve="tastytrade"),
    "SNPS": TickerMeta(tier="A", sleeve="tastytrade"),
    "CDNS": TickerMeta(tier="A", sleeve="tastytrade"),
    "ANET": TickerMeta(tier="A", sleeve="tastytrade"),
    "AVGO": TickerMeta(tier="A", sleeve="tastytrade"),
    "VRT": TickerMeta(tier="A", sleeve="tastytrade"),
    # Tastytrade sleeve — Tier B (builders / extensions)
    "MRVL": TickerMeta(tier="B", sleeve="tastytrade"),
    "CEG": TickerMeta(tier="B", sleeve="tastytrade"),
    "EQT": TickerMeta(tier="B", sleeve="tastytrade"),
    "WDC": TickerMeta(tier="B", sleeve="tastytrade"),
    "STX": TickerMeta(tier="B", sleeve="tastytrade"),
    # Tastytrade sleeve — Tier C (satellites)
    "LITE": TickerMeta(tier="C", sleeve="tastytrade"),
    # Hyperliquid sleeve — Tier A
    "NVDA": TickerMeta(tier="A", sleeve="hyperliquid"),
    "TSM": TickerMeta(tier="A", sleeve="hyperliquid"),
    "MSFT": TickerMeta(tier="A", sleeve="hyperliquid"),
    "META": TickerMeta(tier="A", sleeve="hyperliquid"),
    "AMZN": TickerMeta(tier="A", sleeve="hyperliquid"),
    "GOOGL": TickerMeta(tier="A", sleeve="hyperliquid"),
    # Hyperliquid sleeve — Tier B
    "PLTR": TickerMeta(tier="B", sleeve="hyperliquid"),
    "ORCL": TickerMeta(tier="B", sleeve="hyperliquid"),
    "MU": TickerMeta(tier="B", sleeve="hyperliquid"),
    "COIN": TickerMeta(tier="B", sleeve="hyperliquid"),
    "HOOD": TickerMeta(tier="B", sleeve="hyperliquid"),
    "AAPL": TickerMeta(tier="B", sleeve="hyperliquid"),
    # Hyperliquid sleeve — Tier C
    "TSLA": TickerMeta(tier="C", sleeve="hyperliquid"),
    "RTX": TickerMeta(tier="C", sleeve="hyperliquid"),
    "GLD": TickerMeta(tier="C", sleeve="hyperliquid"),
    "SLV": TickerMeta(tier="C", sleeve="hyperliquid"),
}


# Base size multipliers by tier (A/B/C) — neutral overall but encode the intent
TIER_BASE_MULTIPLIER = {
    "A": 1.20,  # choke points can run a bit bigger
    "B": 1.00,
    "C": 0.60,  # satellites / ballast stay smaller
}


# Regime overlay per tier; these are additional multipliers applied on top of
# TIER_BASE_MULTIPLIER in paper_trading for live/paper sizing.
REGIME_TIER_MULTIPLIER = {
    "bull": {
        "A": 1.10,
        "B": 1.05,
        "C": 0.80,
    },
    "bear": {
        "A": 0.90,
        "B": 0.75,
        "C": 0.60,
    },
    "sideways": {
        "A": 1.00,
        "B": 0.85,
        "C": 0.75,
    },
}


def get_ticker_meta(ticker: str) -> TickerMeta | None:
    """Return tier/sleeve metadata for a ticker, if known."""
    return TICKER_META.get(ticker.upper())


