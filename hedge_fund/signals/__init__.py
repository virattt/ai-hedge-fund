"""Registered alpha models and their static investment approaches."""

from __future__ import annotations

from typing import cast

from hedge_fund.signals.base import AlphaModel, InvestmentApproach, QuantModel
from hedge_fund.signals.buffett import BuffettAgent
from hedge_fund.signals.druckenmiller import DruckenmillerAgent
from hedge_fund.signals.graham import GrahamAgent
from hedge_fund.signals.llm_agent import LLMAgent
from hedge_fund.signals.lynch import LynchAgent
from hedge_fund.signals.munger import MungerAgent
from hedge_fund.signals.news_analyst import NewsAnalystAgent
from hedge_fund.signals.news_sentiment import NewsSentimentModel
from hedge_fund.signals.pead import PEADModel

ALPHA_MODEL_REGISTRY: dict[str, type[AlphaModel]] = {
    # Quant models
    "pead": PEADModel,
    "news_sentiment": NewsSentimentModel,
    # LLM investor agents
    "buffett": BuffettAgent,
    "munger": MungerAgent,
    "graham": GrahamAgent,
    "lynch": LynchAgent,
    "druckenmiller": DruckenmillerAgent,
    "news_analyst": NewsAnalystAgent,
}


def get_investment_approach(name: str) -> InvestmentApproach:
    """Read an analyst's declared approach without constructing a model or client.

    Raise ValueError for an unknown analyst or missing or invalid metadata.
    Profiles must be declared on the registered class, not inherited.
    """
    if name not in ALPHA_MODEL_REGISTRY:
        raise ValueError(f"unknown analyst {name!r}; available: {', '.join(sorted(ALPHA_MODEL_REGISTRY))}")
    approach = vars(ALPHA_MODEL_REGISTRY[name]).get("investment_approach")
    if approach not in ("long_only", "long_short"):
        raise ValueError(f"analyst {name!r} must declare investment_approach as long_only or long_short")
    return cast(InvestmentApproach, approach)


__all__ = [
    "AlphaModel",
    "InvestmentApproach",
    "QuantModel",
    "LLMAgent",
    "BuffettAgent",
    "MungerAgent",
    "GrahamAgent",
    "LynchAgent",
    "DruckenmillerAgent",
    "NewsAnalystAgent",
    "PEADModel",
    "NewsSentimentModel",
    "ALPHA_MODEL_REGISTRY",
    "get_investment_approach",
]
