"""Discovery source registry. Add a new source by appending to SOURCES."""

from collections.abc import Awaitable, Callable

from . import (
    activist_13d,
    analyst,
    cluster_buy,
    commodity_tailwind,
    contrarian_setup,
    csuite_buy,
    dividend_grower,
    fcf_yield,
    first_time_buyer,
    high_roic,
    insider_doubling_down,
    mega_dollar_buy,
    quality_score,
    relative_strength,
    repeat_buyer,
    revenue_acceleration,
    spinoff,
    squeeze,
    valuation_score,
)
from app.backend.models.discovery_schemas import IdeaSignal

# Each source: async () -> list[(key, IdeaSignal)]
# `key` = ticker symbol, OR "cik:N" for entities without a public ticker yet.
SourceFn = Callable[[], Awaitable[list[tuple[str, IdeaSignal]]]]

SOURCES: list[tuple[str, SourceFn]] = [
    ("spinoff", spinoff.fetch),
    ("csuite_buy", csuite_buy.fetch),
    ("squeeze", squeeze.fetch),
    ("cluster_buy", cluster_buy.fetch),
    ("analyst", analyst.fetch),
    ("commodity_tailwind", commodity_tailwind.fetch),
    ("insider_doubling_down", insider_doubling_down.fetch),
    ("first_time_buyer", first_time_buyer.fetch),
    ("mega_dollar_buy", mega_dollar_buy.fetch),
    ("repeat_buyer", repeat_buyer.fetch),
    ("relative_strength", relative_strength.fetch),
    ("contrarian_setup", contrarian_setup.fetch),
    ("activist_13d", activist_13d.fetch),
    ("revenue_acceleration", revenue_acceleration.fetch),
    ("quality_score", quality_score.fetch),
    ("valuation_score", valuation_score.fetch),
    ("dividend_grower", dividend_grower.fetch),
    ("fcf_yield", fcf_yield.fetch),
    ("high_roic", high_roic.fetch),
]
