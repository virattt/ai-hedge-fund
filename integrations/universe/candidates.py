"""Stage 0 — build the candidate pool with cheap eligibility filters.

Starts from every active, tradable US equity on the broker's asset master,
then removes anything we could never trade well: sub-$5 names, thin books,
short histories, and non-common-share tickers (preferred, warrants, units).
Only daily bars are needed, fetched in bulk and disk-cached.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from integrations.universe.config import UniverseConfig
from integrations.universe.data import AssetRecord, UniverseDataSource

logger = logging.getLogger(__name__)

# Plain common-share tickers only. Dots/slashes/hyphens denote share classes,
# preferred stock, warrants, or units on Alpaca's asset master.
_COMMON_TICKER = re.compile(r"^[A-Z]{1,5}$")

# Alpaca's US_EQUITY class includes ETFs/ETNs. These name markers identify
# funds without false-positives on operating companies.
_FUND_NAME_MARKERS = (
    "ETF",
    "ETN",
    "ISHARES",
    "SPDR",
    "PROSHARES",
    "DIREXION",
    "INDEX FUND",
    "BOND FUND",
    "MUTUAL FUND",
    "CLOSED-END",
    "CLOSED END",
    # Spot-crypto trusts file 10-Ks, so the fundamentals gate can't catch them.
    "BITCOIN",
    "ETHEREUM",
    "GRAYSCALE",
)


def looks_like_fund(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _FUND_NAME_MARKERS)

_DOLLAR_VOLUME_WINDOW = 63  # trading days used for the median dollar-volume gate


@dataclass
class Candidate:
    """One Stage-0 survivor with its point-in-time price history."""

    symbol: str
    exchange: str
    shortable: bool
    easy_to_borrow: bool
    prices: pd.DataFrame  # daily bars truncated to <= as_of


def bars_start_date(as_of: str, config: UniverseConfig) -> str:
    start = datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=config.lookback_calendar_days)
    return start.strftime("%Y-%m-%d")


def eligible_assets(assets: list[AssetRecord], config: UniverseConfig) -> list[AssetRecord]:
    exchanges = {e.upper() for e in config.exchanges}
    out = []
    for asset in assets:
        if asset.exchange not in exchanges:
            continue
        if not _COMMON_TICKER.match(asset.symbol):
            continue
        if config.exclude_funds and looks_like_fund(asset.name):
            continue
        out.append(asset)
    return out


def passes_stage0(prices: pd.DataFrame, config: UniverseConfig) -> bool:
    if len(prices) < config.min_history_days:
        return False
    last_close = float(prices["close"].iloc[-1])
    if last_close < config.min_price:
        return False
    recent = prices.tail(_DOLLAR_VOLUME_WINDOW)
    median_dollar_volume = float((recent["close"] * recent["volume"]).median())
    return median_dollar_volume >= config.min_median_dollar_volume


def build_candidate_pool(
    source: UniverseDataSource,
    config: UniverseConfig,
    as_of: str,
) -> list[Candidate]:
    """Assets -> exchange/symbol filters -> bulk bars -> price/volume/history gates."""
    assets = eligible_assets(source.list_assets(), config)
    logger.info("Stage 0: %d eligible assets after exchange/symbol filters", len(assets))

    start_date = bars_start_date(as_of, config)
    bars = source.get_bars([a.symbol for a in assets], start_date, as_of)

    cutoff = pd.Timestamp(as_of)
    candidates: list[Candidate] = []
    for asset in assets:
        prices = bars.get(asset.symbol)
        if prices is None or prices.empty:
            continue
        prices = prices.loc[prices.index <= cutoff]
        if prices.empty or not passes_stage0(prices, config):
            continue
        candidates.append(
            Candidate(
                symbol=asset.symbol,
                exchange=asset.exchange,
                shortable=asset.shortable,
                easy_to_borrow=asset.easy_to_borrow,
                prices=prices,
            )
        )
    logger.info("Stage 0: %d candidates passed price/volume/history gates", len(candidates))
    return candidates
