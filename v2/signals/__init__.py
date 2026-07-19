"""Alpha models — view-forming components of the quant stack.

See v2/signals/base.py for the AlphaModel / QuantModel interface.
Concrete models register here as they are implemented. Two flavors, one
interface: LLM investor agents (persona system prompts on LLMAgent) and
quant models (pure math).
"""

from __future__ import annotations

from v2.signals.base import AlphaModel, QuantModel
from v2.signals.buffett import BuffettAgent
from v2.signals.druckenmiller import DruckenmillerAgent
from v2.signals.graham import GrahamAgent
from v2.signals.llm_agent import LLMAgent
from v2.signals.lynch import LynchAgent
from v2.signals.munger import MungerAgent
from v2.signals.pead import PEADModel

ALPHA_MODEL_REGISTRY: dict[str, type[AlphaModel]] = {
    # Quant models
    "pead": PEADModel,
    # LLM investor agents
    "buffett": BuffettAgent,
    "munger": MungerAgent,
    "graham": GrahamAgent,
    "lynch": LynchAgent,
    "druckenmiller": DruckenmillerAgent,
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
    "PEADModel",
    "ALPHA_MODEL_REGISTRY",
]
