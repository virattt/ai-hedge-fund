"""Contract tests for shared pipeline models."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from hedge_fund.models import Signal


def _signal(value: float) -> Signal:
    return Signal(model_name="test", ticker="AAPL", date="2024-06-03", value=value)


@pytest.mark.parametrize("value", [-1.0, 0.0, 1.0])
def test_signal_accepts_conviction_bounds(value: float):
    assert _signal(value).value == value


@pytest.mark.parametrize("value", [-1.000001, 1.000001, math.inf, -math.inf, math.nan])
def test_signal_rejects_non_finite_or_out_of_range_conviction(value: float):
    with pytest.raises(ValidationError):
        _signal(value)
