"""Fundamentals service — quarterly revenue, company quality/valuation/cash
metrics, and multi-year ROIC history via yfinance.

Powers six Discovery sources via `from app.backend.services.fundamentals_service
import ...`:
  - revenue_acceleration  → get_revenue_growth*
  - quality_score         → get_company_metrics*
  - valuation_score       → get_company_metrics*
  - dividend_grower       → get_company_metrics*
  - fcf_yield             → get_company_metrics*
  - high_roic             → get_roic_history*

Each ticker is cached 24h (fundamentals refresh quarterly at most).

Why yfinance vs paid fundamental APIs:
  - Free, no auth, no rate-limit concerns
  - Already a dependency across the platform
  - Standard GAAP line items map consistently
"""

from ._metrics import (
    CompanyMetrics,
    get_company_metrics,
    get_company_metrics_batch,
)
from ._revenue import (
    RevenueGrowthAnalysis,
    RevenuePoint,
    get_revenue_growth,
    get_revenue_growth_batch,
)
from ._roic import (
    RoicHistory,
    RoicYear,
    get_roic_history,
    get_roic_history_batch,
)
