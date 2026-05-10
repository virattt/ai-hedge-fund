"""v2 event study framework.

CARs around earnings, market model for expected returns,
cross-sectional t-tests and bootstrap confidence intervals.
"""

from v2.event_study.engine import compute_car
from v2.event_study.models import (
    AggregateResult,
    BootstrapCI,
    EventCAR,
    EventStudyResult,
    MarketModelFit,
    WindowStats,
)
from v2.event_study.plot import (
    plot_car_by_source,
    plot_car_distribution,
    plot_cumulative_ar,
)

__all__ = [
    "compute_car",
    "AggregateResult",
    "BootstrapCI",
    "EventCAR",
    "EventStudyResult",
    "MarketModelFit",
    "WindowStats",
    "plot_car_by_source",
    "plot_car_distribution",
    "plot_cumulative_ar",
]
