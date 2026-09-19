"""Allocator (CIO) unit tests — protocol, static math, equal-weight stub."""

import pytest

from hedge_fund.fund.allocator import (
    ALLOCATOR_NAMES,
    Allocator,
    AllocatorContext,
    EqualWeightAllocator,
    StaticAllocator,
    StrategyAllocationView,
    get_allocator,
    require_slices,
)


def _ctx(*weights: tuple[str, float], **kwargs) -> AllocatorContext:
    return AllocatorContext(
        as_of="2024-06-03",
        equity=100_000.0,
        strategies=tuple(
            StrategyAllocationView(name=name, spec_weight=weight)
            for name, weight in weights
        ),
        **kwargs,
    )


def test_static_and_equal_weight_satisfy_the_protocol():
    assert isinstance(StaticAllocator(), Allocator)
    assert isinstance(EqualWeightAllocator(), Allocator)
    assert StaticAllocator().name == "static"
    assert EqualWeightAllocator().name == "equal_weight"


def test_static_allocator_is_weight_over_sum():
    """The default CIO is exactly today's slice math, not an approximation."""
    ctx = _ctx(("s1", 3.0), ("s2", 1.0))
    slices = StaticAllocator().allocate(ctx)
    total = 3.0 + 1.0
    assert slices == {"s1": 3.0 / total, "s2": 1.0 / total}
    assert slices["s1"] + slices["s2"] == 1.0


def test_static_allocator_two_over_two_equals_one_over_one():
    a = StaticAllocator()
    assert a.allocate(_ctx(("s1", 2.0), ("s2", 2.0))) == a.allocate(
        _ctx(("s1", 1.0), ("s2", 1.0))
    )


def test_equal_weight_allocator_ignores_mandate_slices():
    slices = EqualWeightAllocator().allocate(_ctx(("s1", 3.0), ("s2", 1.0)))
    assert slices == {"s1": 0.5, "s2": 0.5}


def test_get_allocator_selects_by_name():
    assert isinstance(get_allocator("static"), StaticAllocator)
    assert isinstance(get_allocator("equal_weight"), EqualWeightAllocator)
    with pytest.raises(ValueError, match="unknown allocator"):
        get_allocator("risk_parity")
    assert ALLOCATOR_NAMES == frozenset({"static", "equal_weight"})


def test_require_slices_rejects_missing_extra_and_nonpositive():
    names = ["s1", "s2"]
    good = {"s1": 0.75, "s2": 0.25}
    assert require_slices(good, names) is good

    with pytest.raises(ValueError, match="expected"):
        require_slices({"s1": 1.0}, names)
    with pytest.raises(ValueError, match="expected"):
        require_slices({"s1": 0.5, "s2": 0.5, "s3": 0.0}, names)
    with pytest.raises(ValueError, match="finite and > 0"):
        require_slices({"s1": 1.0, "s2": 0.0}, names)
    with pytest.raises(ValueError, match="finite and > 0"):
        require_slices({"s1": 1.0, "s2": float("nan")}, names)


def test_empty_context_fails_loud():
    empty = AllocatorContext(as_of="2024-06-03", equity=1.0, strategies=())
    with pytest.raises(ValueError, match="no strategies"):
        StaticAllocator().allocate(empty)
    with pytest.raises(ValueError, match="no strategies"):
        EqualWeightAllocator().allocate(empty)
