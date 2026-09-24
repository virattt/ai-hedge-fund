"""Execution eligibility for configured investment rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hedge_fund.signals import get_investment_approach

if TYPE_CHECKING:
    from hedge_fund.fund.spec import FundSpec


def execution_unavailable(spec: FundSpec) -> str | None:
    """Return an explanation if any strategy requires unsupported enforcement.

    Portfolio construction supports only long/short strategies staffed entirely
    by long/short analysts. It does not enforce analyst-specific permissions or
    preserve dollar neutrality after risk adjustments.
    """
    blocked: list[str] = []
    for strategy in spec.strategies:
        long_only = [m.name for m in strategy.models if get_investment_approach(m.name) == "long_only"]
        if strategy.blend.mode != "long_short" or long_only:
            reason = strategy.blend.mode.replace("_", "-")
            if long_only:
                reason += f"; long-only analysts: {', '.join(long_only)}"
            blocked.append(f"{strategy.title} ({reason})")
    if blocked:
        return "Execution unavailable for these strategy rules: " + "; ".join(blocked) + ". Only long/short strategies staffed entirely by long/short analysts can run. " "You can save and inspect this fund."
    return None


def require_executable(spec: FundSpec) -> None:
    """Raise ValueError for unsupported rules before any external activity."""
    reason = execution_unavailable(spec)
    if reason:
        raise ValueError(reason)
