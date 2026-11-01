"""TradingCosts — the half-spread, the commission and the impact, by hand."""

import pytest
from pydantic import ValidationError

from hedge_fund.brokers.costs import TradingCosts


def test_defaults_are_a_liquid_large_cap_at_retail_rates():
    costs = TradingCosts()
    assert costs.spread_bps == 5.0
    assert costs.commission_per_share == 0.005
    assert costs.impact_coefficient == 1.0
    assert costs.min_trade_pct == 0.005


def test_buy_pays_the_half_spread_and_sell_receives_it():
    costs = TradingCosts(spread_bps=5, commission_per_share=0.005)
    assert costs.fill_price("buy", 100.0) == pytest.approx(100.05)
    assert costs.fill_price("sell", 100.0) == pytest.approx(99.95)
    assert costs.commission(100) == pytest.approx(0.50)


def test_impact_is_the_square_root_law():
    # 1% of the day's volume in a name with 2% daily vol: 1.0 x 0.02 x sqrt(0.01) = 20 bps.
    costs = TradingCosts(spread_bps=5, commission_per_share=0)
    assert costs.impact(participation=0.01, volatility=0.02) == pytest.approx(0.002)
    assert costs.fill_price("buy", 100.0, participation=0.01, volatility=0.02) == pytest.approx(100.25)
    assert costs.fill_price("sell", 100.0, participation=0.01, volatility=0.02) == pytest.approx(99.75)
    # Four times the size costs twice the impact.
    assert costs.impact(participation=0.04, volatility=0.02) == pytest.approx(0.004)


def test_no_participation_or_no_vol_or_no_coefficient_is_the_spread_alone():
    costs = TradingCosts(spread_bps=5, commission_per_share=0)
    assert costs.fill_price("buy", 100.0, participation=0.0, volatility=0.02) == pytest.approx(100.05)
    assert costs.fill_price("buy", 100.0, participation=0.01, volatility=0.0) == pytest.approx(100.05)
    off = TradingCosts(spread_bps=5, commission_per_share=0, impact_coefficient=0)
    assert off.fill_price("buy", 100.0, participation=0.5, volatility=0.5) == pytest.approx(100.05)


def test_zero_on_every_field_is_a_free_fill():
    costs = TradingCosts(spread_bps=0, commission_per_share=0, impact_coefficient=0, min_trade_pct=0)
    assert costs.fill_price("buy", 100.0, participation=0.5, volatility=0.5) == 100.0
    assert costs.fill_price("sell", 100.0, participation=0.5, volatility=0.5) == 100.0
    assert costs.commission(1_000) == 0.0


@pytest.mark.parametrize("bad", [
    {"spread_bps": -1}, {"commission_per_share": -0.01}, {"impact_coefficient": -0.5},
    {"min_trade_pct": -0.1}, {"min_trade_pct": 1.0}, {"impact": 0.1},
])
def test_negative_or_unknown_fields_are_rejected(bad):
    with pytest.raises(ValidationError):
        TradingCosts(**bad)
