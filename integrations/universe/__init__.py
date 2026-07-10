"""Intelligent universe selection — quantitative ranking of tradable US equities.

Pipeline: candidate pool -> cheap filters -> factor scoring -> alpha
learnability -> diversified selection -> versioned universe artifact that
the live alpaca-fund CLI/daemon consumes via ``--universe``.
"""

from integrations.universe.config import UniverseConfig, load_universe_config
from integrations.universe.models import FactorScore, TickerScore, UniverseSnapshot
from integrations.universe.store import (
    load_latest_universe,
    load_universe,
    resolve_universe_tickers,
    save_universe,
)

__all__ = [
    "UniverseConfig",
    "load_universe_config",
    "FactorScore",
    "TickerScore",
    "UniverseSnapshot",
    "save_universe",
    "load_universe",
    "load_latest_universe",
    "resolve_universe_tickers",
]
