"""The scorecard tables render every field, and say so when there is nothing yet."""

from __future__ import annotations

from hedge_fund.scorecard import AnalystScore, Scorecard, StrategyScore
from hedge_fund.tui.fixtures import render
from hedge_fund.tui.scorecard_view import analyst_table, strategy_table


def _card(analysts=(), strategies=(), fund_pnl=0.0, trading_cost=0.0) -> Scorecard:
    return Scorecard(fund="alpha", first_session="2025-01-06", last_session="2025-03-03", horizon="weekly",
                     analysts=list(analysts), strategies=list(strategies), fund_pnl=fund_pnl,
                     trading_cost=trading_cost)


def test_analyst_table_shows_rates_with_their_counts():
    card = _card(analysts=[
        AnalystScore(name="buffett", n_views=40, n_directional=32, n_abstained=3, hit_rate=0.5625,
                     slugging=1.8, ic_mean=0.042, ic_std=0.11, ic_t_stat=1.2, n_dates=10),
        AnalystScore(name="pead", n_views=4, n_directional=0, n_abstained=36, hit_rate=None,
                     slugging=None, ic_mean=None, ic_std=None, ic_t_stat=None, n_dates=0),
    ])
    text = render(analyst_table(card))
    assert "judged over one weekly period" in text
    assert "Buffett" in text and "56% of 32" in text and "1.80×" in text and "+0.042" in text
    assert "PEAD" in text and "36" in text
    assert text.count("–") >= 4  # every missing PEAD number renders as a dash


def test_strategy_table_reports_the_unattributed_gap():
    card = _card(strategies=[
        StrategyScore(name="fundamental-ls", n_periods=8, pnl=2450.0, return_pct=0.0245, win_rate=0.625,
                      share_of_pnl=1.2, max_drawdown_pct=0.013),
    ], fund_pnl=2040.0, trading_cost=300.0)
    text = render(strategy_table(card))
    assert "fundamental-ls" in text and "+2,450" in text and "+2.45%" in text and "62% of 8" in text
    assert "fund P&L +2,040" in text and "unattributed -410" in text and "trading costs -300" in text


def test_empty_scorecard_says_why():
    card = _card()
    assert "nothing to grade yet" in render(analyst_table(card))
    assert "nothing to attribute yet" in render(strategy_table(card))
    assert "no decisions yet" in render(analyst_table(card.model_copy(update={"horizon": None})))
