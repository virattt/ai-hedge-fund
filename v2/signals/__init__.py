"""Quantitative signal registry.

Signals will be added here as they are built during the learning path.
See v2/signals/base.py for the BaseSignal ABC.
"""

from __future__ import annotations

from v2.signals.base import BaseSignal

SIGNAL_REGISTRY: dict[str, type[BaseSignal]] = {}
