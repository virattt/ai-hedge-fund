"""Allocator (CIO) — pluggable capital allocation across strategies.

Portfolio construction (``hedge_fund/portfolio``) blends model views into
target weights *inside* one strategy. The allocator sits one level up: it
maps strategy performance / risk / mandate context into capital slices
across strategies. ``run_cycle`` then scales each sleeve by those slices
when it nets the book.

StaticAllocator is the default: it normalizes ``StrategySpec.weight`` the
same way the pipeline always has. EqualWeightAllocator is a selectable
stub so a second policy can be invoked without claiming production-ready
math. Risk-parity and dynamic CIOs plug in here later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StrategyAllocationView:
    """What the CIO sees about one strategy this tick.

    ``spec_weight`` is the mandate's static slice (``StrategySpec.weight``).
    ``realized_vol`` and ``nav_return`` are optional risk / performance
    inputs — today's policies may ignore them; a later risk-parity or
    dynamic CIO consumes them. Missing values stay ``None``; an allocator
    that needs them should fail loud rather than invent numbers.
    """

    name: str
    spec_weight: float
    realized_vol: float | None = None
    nav_return: float | None = None


@dataclass(frozen=True)
class AllocatorContext:
    """Mandate context for one allocation decision.

    ``as_of`` is the cycle date. ``equity`` is the book the slices will
    size against. ``strategies`` is every pod, in mandate order.
    """

    as_of: str
    equity: float
    strategies: tuple[StrategyAllocationView, ...]
    extra: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Allocator(Protocol):
    """Protocol every capital allocator must satisfy.

    Contract: ``allocate`` returns a ``strategy_name -> weight`` map that
    covers every strategy in ``context``, each weight finite and ``> 0``.
    ``run_cycle`` uses the weights as-is (no renormalization) so the
    static path stays bit-identical to ``weight / sum(weights)``.

    A missing name, an extra name, or a non-positive / non-finite weight
    is a bug — the pipeline fails loud rather than silently rebalance.
    """

    def allocate(self, context: AllocatorContext) -> dict[str, float]:
        """Map strategy performance / risk / mandate context to capital weights."""
        ...


class StaticAllocator:
    """Human-set dial: normalize ``StrategySpec.weight`` across siblings.

    Weights 2/2 mean the same as 1/1. This is today's mandate behavior.
    """

    name = "static"

    def allocate(self, context: AllocatorContext) -> dict[str, float]:
        if not context.strategies:
            raise ValueError("allocator: no strategies to allocate across")
        total = sum(s.spec_weight for s in context.strategies)
        return {s.name: s.spec_weight / total for s in context.strategies}


class EqualWeightAllocator:
    """Stub: ignore mandate slices and split capital evenly.

    Skeleton for a second CIO policy. Not a production risk model — it
    exists so the interface is selectable and testable. A later
    inverse-vol / risk-parity allocator can replace this slot.
    """

    name = "equal_weight"

    def allocate(self, context: AllocatorContext) -> dict[str, float]:
        n = len(context.strategies)
        if n == 0:
            raise ValueError("allocator: no strategies to allocate across")
        share = 1.0 / n
        return {s.name: share for s in context.strategies}


ALLOCATORS: dict[str, type[Allocator]] = {
    "static": StaticAllocator,
    "equal_weight": EqualWeightAllocator,
}

ALLOCATOR_NAMES = frozenset(ALLOCATORS)


def get_allocator(name: str) -> Allocator:
    """Build an allocator by registry key. Unknown names fail loud."""
    try:
        cls = ALLOCATORS[name]
    except KeyError:
        raise ValueError(
            f"unknown allocator {name!r}; available: {sorted(ALLOCATORS)}"
        ) from None
    return cls()


def require_slices(
    slices: dict[str, float],
    names: list[str],
) -> dict[str, float]:
    """Validate allocator output. Does not renormalize.

    Returning the same dict (when valid) keeps the static path's floats
    identical to ``weight / sum(weights)``.
    """
    expected = set(names)
    got = set(slices)
    if got != expected:
        raise ValueError(
            f"allocator returned {sorted(got)}, expected {sorted(expected)}"
        )
    for name, weight in slices.items():
        if not isfinite(weight) or weight <= 0:
            raise ValueError(
                f"allocator weight for {name!r} must be finite and > 0, "
                f"got {weight!r}"
            )
    return slices
