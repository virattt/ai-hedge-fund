"""Alpha models — view-forming components of the quant stack.

See v2/signals/base.py for the AlphaModel / QuantModel interface.
Concrete models register here as they are implemented.
"""

from __future__ import annotations

from v2.signals.base import AlphaModel, QuantModel
from v2.signals.buffett import BuffettAgent
from v2.signals.llm_agent import LLMAgent
from v2.signals.pead import PEADModel

ALPHA_MODEL_REGISTRY: dict[str, type[AlphaModel]] = {
    "pead": PEADModel,
    "buffett": BuffettAgent,
}

__all__ = [
    "AlphaModel",
    "QuantModel",
    "LLMAgent",
    "BuffettAgent",
    "PEADModel",
    "ALPHA_MODEL_REGISTRY",
]
