"""v2 backtesting — simulate a fund (or a single alpha model) over history."""

from v2.backtesting.engine import BacktestEngine
from v2.backtesting.fund import (
    FundBacktestMetrics,
    FundBacktestResult,
    backtest_fund,
    rebalance_grid,
)
from v2.backtesting.models import (
    BacktestResult,
    PerformanceMetrics,
    Trade,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "FundBacktestMetrics",
    "FundBacktestResult",
    "PerformanceMetrics",
    "Trade",
    "backtest_fund",
    "rebalance_grid",
]
