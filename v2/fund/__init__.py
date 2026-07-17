"""v2 fund — mandates as data, and the Fund object that lives them."""

from v2.fund.spec import (
    ModelSpec,
    BlendPolicy,
    Fund,
    FundSpec,
    StrategySpec,
    load_spec,
    load_strategy,
)

__all__ = [
    "ModelSpec",
    "BlendPolicy",
    "Fund",
    "FundSpec",
    "StrategySpec",
    "load_spec",
    "load_strategy",
]
