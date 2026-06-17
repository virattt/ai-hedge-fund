"""v2 backtesting — simulate trading an alpha model's signals over time."""

from v2.backtesting.engine import BacktestEngine
from v2.backtesting.models import (
    BacktestResult,
    PerformanceMetrics,
    Trade,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "PerformanceMetrics",
    "Trade",
]
