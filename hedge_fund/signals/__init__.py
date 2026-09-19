"""Alpha models — view-forming components of the quant stack.

See hedge_fund/signals/base.py for the AlphaModel / QuantModel interface.
Concrete models register here as they are implemented. Two flavors, one
interface: LLM investor agents (persona system prompts on LLMAgent) and
quant models (pure math).
"""

from __future__ import annotations

from hedge_fund.signals.ackman import AckmanAgent
from hedge_fund.signals.base import AlphaModel, QuantModel
from hedge_fund.signals.buffett import BuffettAgent
from hedge_fund.signals.burry import BurryAgent
from hedge_fund.signals.damodaran import DamodaranAgent
from hedge_fund.signals.druckenmiller import DruckenmillerAgent
from hedge_fund.signals.graham import GrahamAgent
from hedge_fund.signals.llm_agent import LLMAgent
from hedge_fund.signals.lynch import LynchAgent
from hedge_fund.signals.munger import MungerAgent
from hedge_fund.signals.pead import PEADModel
from hedge_fund.signals.wood import WoodAgent

# Keys are last-name slugs (buffett, wood, damodaran) — short, stable ids
# for strategy YAML and Signal.model_name.
ALPHA_MODEL_REGISTRY: dict[str, type[AlphaModel]] = {
    # Quant models
    "pead": PEADModel,
    # LLM investor agents
    "buffett": BuffettAgent,
    "munger": MungerAgent,
    "graham": GrahamAgent,
    "lynch": LynchAgent,
    "druckenmiller": DruckenmillerAgent,
    "wood": WoodAgent,
    "burry": BurryAgent,
    "ackman": AckmanAgent,
    "damodaran": DamodaranAgent,
}

__all__ = [
    "AlphaModel",
    "QuantModel",
    "LLMAgent",
    "BuffettAgent",
    "MungerAgent",
    "GrahamAgent",
    "LynchAgent",
    "DruckenmillerAgent",
    "WoodAgent",
    "BurryAgent",
    "AckmanAgent",
    "DamodaranAgent",
    "PEADModel",
    "ALPHA_MODEL_REGISTRY",
]
