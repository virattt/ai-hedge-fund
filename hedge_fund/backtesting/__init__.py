"""v2 backtesting — simulate a fund over history."""

from hedge_fund.backtesting.fund import (
    backtest_fund,
    build_schedule,
    DailyValuation,
    FundBacktestMetrics,
    FundBacktestResult,
    performance_metrics,
    rebalance_grid,
    ReplaySchedule,
)
from hedge_fund.backtesting.research import (
    last_score,
    last_universe,
    receipts,
    save_result,
    summarize,
)

__all__ = [
    "DailyValuation",
    "FundBacktestMetrics",
    "FundBacktestResult",
    "ReplaySchedule",
    "backtest_fund",
    "build_schedule",
    "performance_metrics",
    "rebalance_grid",
    "receipts",
    "save_result",
    "summarize",
    "last_score",
    "last_universe",
]
