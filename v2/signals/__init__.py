"""Quantitative signal registry.

Concrete signals register here as they are implemented.
See v2/signals/base.py for the BaseSignal ABC.
"""

from __future__ import annotations

from v2.signals.base import BaseSignal

SIGNAL_REGISTRY: dict[str, type[BaseSignal]] = {}
