"""Diversified final selection.

Greedy walk down the composite ranking, admitting a candidate only if it
does not breach the sector cap and is not too correlated with anything
already selected. If strict constraints can't fill the target size, they are
relaxed in documented passes (correlation first, then sector) so the
universe always reaches the requested count when enough candidates exist.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from integrations.universe.config import UniverseConfig
from integrations.universe.models import TickerScore

logger = logging.getLogger(__name__)

_UNKNOWN_SECTOR = "UNKNOWN"


def returns_matrix(
    price_frames: dict[str, pd.DataFrame], window_days: int
) -> pd.DataFrame:
    """Aligned daily-returns matrix (columns = tickers) over the trailing window."""
    closes = {
        ticker: frame["close"] for ticker, frame in price_frames.items() if not frame.empty
    }
    if not closes:
        return pd.DataFrame()
    aligned = pd.DataFrame(closes).tail(window_days + 1)
    return aligned.pct_change().dropna(how="all")


def _max_correlation(
    candidate: str, selected: list[str], corr: pd.DataFrame
) -> float:
    if not selected or candidate not in corr.columns:
        return 0.0
    peers = [t for t in selected if t in corr.columns]
    if not peers:
        return 0.0
    values = corr.loc[candidate, peers].abs()
    result = float(values.max())
    return result if math.isfinite(result) else 0.0


def select_universe(
    scores: list[TickerScore],
    price_frames: dict[str, pd.DataFrame],
    config: UniverseConfig,
) -> list[str]:
    """Pick ``config.size`` tickers maximizing score under diversification limits."""
    ranked = sorted(scores, key=lambda s: s.composite, reverse=True)
    returns = returns_matrix(price_frames, config.correlation_window_days)
    corr = returns.corr() if not returns.empty else pd.DataFrame()

    sector_cap = max(1, math.ceil(config.size * config.sector_cap_pct))

    selected: list[str] = []
    sector_counts: dict[str, int] = {}

    def sector_of(score: TickerScore) -> str:
        return (score.sector or _UNKNOWN_SECTOR).upper()

    # Pass 1: strict — sector cap + correlation limit.
    # Pass 2: sector cap only. Pass 3: score order, no constraints.
    for pass_index, (use_corr, use_sector) in enumerate(
        [(True, True), (False, True), (False, False)], start=1
    ):
        for score in ranked:
            if len(selected) >= config.size:
                break
            ticker = score.ticker
            if ticker in selected:
                continue
            sector = sector_of(score)
            if use_sector and sector_counts.get(sector, 0) >= sector_cap:
                continue
            if use_corr and not corr.empty:
                if _max_correlation(ticker, selected, corr) > config.max_correlation:
                    continue
            selected.append(ticker)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= config.size:
            if pass_index > 1:
                logger.info("Selection needed relaxation pass %d to fill %d slots", pass_index, config.size)
            break

    return selected[: config.size]
