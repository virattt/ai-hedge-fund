"""Scorecard tests: hand-built ledgers with answers computed by hand."""

from __future__ import annotations

from math import sqrt

import numpy as np
import pytest

from hedge_fund.brokers.models import Fill, Order
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import CycleRecord, DecisionRecord, StrategyRecord
from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard import score
from hedge_fund.scorecard.analysts import _average_ranks, _spearman

SPEC = {
    "schema_version": 2, "name": "test", "rebalance": "daily",
    "strategies": [
        {"name": "value", "models": [{"name": "buffett"}, {"name": "munger"}], "blend": {"mode": "long_short"}},
        {"name": "momo", "models": [{"name": "buffett"}], "blend": {"mode": "long_short"}},
    ],
    "risk": {"max_position_pct": 1, "max_gross_exposure": 1},
}
MINUTE_SPEC = {**SPEC, "rebalance": "minute", "interval": 5}

D1, D2, D3 = "2024-06-03", "2024-06-04", "2024-06-05"
TICKERS = ["AAA", "BBB", "CCC", "DDD"]
# Forward returns D1->D2: +.10 -.10 +.05 +.20; D2->D3: +.10 +.08 -.05 -.10
MARKS = {
    D1: {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0, "DDD": 100.0},
    D2: {"AAA": 110.0, "BBB": 90.0, "CCC": 105.0, "DDD": 120.0},
    D3: {"AAA": 121.0, "BBB": 97.2, "CCC": 99.75, "DDD": 108.0},
}
# Buffett ranks the names exactly as they go on to return; Munger is the mirror.
BUFFETT = {
    D1: {"AAA": 0.5, "BBB": -0.5, "CCC": 0.2, "DDD": 0.9},
    D2: {"AAA": 0.5, "BBB": 0.4, "CCC": -0.2, "DDD": -0.9},
}
MUNGER = {day: {t: -v for t, v in views.items()} for day, views in BUFFETT.items()}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _signal(name: str, ticker: str, value: float, *, abstained: bool = False) -> Signal:
    return Signal(model_name=name, ticker=ticker, date="2024-01-01", value=value,
                  metadata={"abstained": True} if abstained else {})


def _signals(name: str, views: dict[str, float]) -> list[Signal]:
    return [_signal(name, ticker, value) for ticker, value in views.items()]


def _decision(as_of: str, marks: dict[str, float], strategies: dict[str, list[Signal]], spec=SPEC) -> DecisionRecord:
    return DecisionRecord(
        fund="test", as_of=as_of, spec=spec, universe=sorted(marks), marks=marks, skipped=[],
        strategies=[StrategyRecord(name=n, slice=0.5, signals=s, convictions={}, weights={})
                    for n, s in strategies.items()],
        target_weights={}, clamps=[], final_weights={},
    )


def _cycle(as_of: str, marks: dict[str, float], contributions: dict[str, dict[str, float]],
           equity_before: float, positions: dict[str, int], cash: float, spec=SPEC) -> CycleRecord:
    return CycleRecord(
        fund="test", as_of=as_of, spec=spec, universe=sorted(marks), marks=marks, skipped=[],
        strategies=[StrategyRecord(name=n, slice=0.5, signals=[], convictions={}, weights={}, final_contribution=c)
                    for n, c in contributions.items()],
        target_weights={}, clamps=[], final_weights={},
        equity_before=equity_before, cash_before=cash, orders=[], fills=[],
        positions=positions, cash=cash, nav=cash + sum(s * marks[t] for t, s in positions.items()),
    )


def _session(session: str, *, decision: DecisionRecord | None = None, executed: CycleRecord | None = None,
             marks: dict[str, float] | None = None, positions: dict[str, int] | None = None,
             benchmark_close: float = 100.0) -> SessionRecord:
    marks = marks or {}
    positions = positions or {}
    cash = 100_000.0 - sum(positions[t] * marks[t] for t in positions)
    return SessionRecord(
        fund="test", session=session, universe=TICKERS, nav=cash + sum(positions[t] * marks[t] for t in positions),
        cash=cash, positions=positions, marks=marks, benchmark="SPY", benchmark_close=benchmark_close,
        rebalance=decision is not None, executed=executed, decision=decision,
        code_version="test", mandate_hash="m",
    )


def _analyst_ledger(buffett=BUFFETT, munger=MUNGER, marks=MARKS, benchmark=(100.0, 100.0, 100.0),
                    both_pods: bool = True) -> list[SessionRecord]:
    """Three daily decisions. Buffett sits in both pods; Munger in one. D3's
    decision has no following decision, so its views must never count."""
    def pods(day):
        value = _signals("buffett", buffett[day]) + _signals("munger", munger[day])
        momo = _signals("buffett", buffett[day]) if both_pods else []
        return {"value": value, "momo": momo}
    return [
        _session(D1, decision=_decision(D1, marks[D1], pods(D1)), benchmark_close=benchmark[0]),
        _session(D2, decision=_decision(D2, marks[D2], pods(D2)), benchmark_close=benchmark[1]),
        _session(D3, decision=_decision(D3, marks[D3], {"value": _signals("buffett", {"AAA": 0.9})}),
                 benchmark_close=benchmark[2]),
    ]


def _by_name(card):
    return {a.name: a for a in card.analysts}


# ---------------------------------------------------------------------------
# Analysts
# ---------------------------------------------------------------------------

def test_always_right_and_always_wrong():
    card = score(_analyst_ledger())
    buffett, munger = _by_name(card)["buffett"], _by_name(card)["munger"]
    assert (buffett.n_views, buffett.n_directional, buffett.n_abstained) == (8, 8, 0)
    assert buffett.hit_rate == 1.0
    assert buffett.ic_mean == pytest.approx(1.0)
    assert buffett.n_dates == 2
    assert buffett.ic_std == pytest.approx(0.0)
    assert buffett.ic_t_stat is None          # no spread, no t-stat
    assert buffett.slugging is None           # no misses to divide by
    assert munger.hit_rate == 0.0
    assert munger.ic_mean == pytest.approx(-1.0)
    assert munger.slugging is None            # no hits
    assert card.horizon == "daily"
    assert (card.first_session, card.last_session) == (D1, D3)


def test_persona_in_two_strategies_counts_once():
    card = score(_analyst_ledger(both_pods=True))
    assert _by_name(card)["buffett"].n_views == 8
    assert [a.name for a in card.analysts] == ["buffett", "munger"]


def test_last_decision_is_excluded():
    # D3's lone AAA +0.9 would be a ninth view if it counted.
    assert _by_name(score(_analyst_ledger()))["buffett"].n_views == 8


def test_ticker_without_a_price_at_the_next_decision_is_dropped():
    marks = {**MARKS, D2: {t: p for t, p in MARKS[D2].items() if t != "DDD"}}
    buffett = _by_name(score(_analyst_ledger(marks=marks)))["buffett"]
    assert buffett.n_views == 6               # DDD drops from both D1->D2 and D2->D3


def test_abstained_and_neutral_views():
    munger = {D1: {**MUNGER[D1], "BBB": 0.0}, D2: MUNGER[D2]}
    records = _analyst_ledger(munger=munger)
    records[0].decision.strategies[0].signals[4] = _signal("munger", "AAA", 0.0, abstained=True)
    m = _by_name(score(records))["munger"]
    assert (m.n_views, m.n_directional, m.n_abstained) == (7, 6, 1)


def test_hit_rate_is_benchmark_relative_and_flat_is_not_a_hit():
    # The benchmark rises 10% over D1->D2. AAA's +10% is then flat: not a hit.
    # BBB (-20% excess vs -0.5) and DDD (+10% vs +0.9) hit; CCC (-5% vs +0.2) misses.
    # D2->D3 the benchmark is flat and all four hit. 6 of 8.
    buffett = _by_name(score(_analyst_ledger(benchmark=(100.0, 110.0, 110.0))))["buffett"]
    assert buffett.hit_rate == pytest.approx(6 / 8)


def test_slugging():
    marks = {D1: MARKS[D1], D2: {"AAA": 110.0, "BBB": 130.0, "CCC": 90.0, "DDD": 100.0}}
    records = [
        _session(D1, decision=_decision(D1, marks[D1], {"value": _signals(
            "buffett", {"AAA": 0.5, "BBB": 0.5, "CCC": 0.5, "DDD": 0.0})})),
        _session(D2, decision=_decision(D2, marks[D2], {})),
    ]
    buffett = _by_name(score(records))["buffett"]
    assert buffett.hit_rate == pytest.approx(2 / 3)  # hits +.10 +.30, miss -.10
    assert buffett.slugging == pytest.approx(0.20 / 0.10)


def test_constant_views_have_no_ic_but_still_a_hit_rate():
    flat = {day: dict.fromkeys(TICKERS, 0.5) for day in (D1, D2)}
    buffett = _by_name(score(_analyst_ledger(buffett=flat)))["buffett"]
    assert buffett.ic_mean is None
    assert buffett.n_dates == 0
    assert buffett.hit_rate == pytest.approx(5 / 8)


def test_average_ranks_and_spearman():
    assert _average_ranks(np.array([10, 20, 20, 30])).tolist() == [1.0, 2.5, 2.5, 4.0]
    assert _spearman(np.array([10, 20, 20, 30]), np.array([1, 2, 3, 4])) == pytest.approx(3 / sqrt(10))
    assert _spearman(np.array([1, 2]), np.array([1, 2])) is None
    assert _spearman(np.array([1, 1, 1]), np.array([1, 2, 3])) is None


def test_ic_series_mean_std_and_t_stat():
    # D1 keeps IC 1. D2's convictions rank 1..4 against returns ranked 2,4,1,3: IC 0.
    buffett = {D1: BUFFETT[D1], D2: {"AAA": 0.1, "BBB": 0.2, "CCC": 0.3, "DDD": 0.4}}
    marks = {**MARKS, D3: {"AAA": 112.2, "BBB": 99.0, "CCC": 99.75, "DDD": 126.0}}
    b = _by_name(score(_analyst_ledger(buffett=buffett, marks=marks)))["buffett"]
    assert b.n_dates == 2
    assert b.ic_mean == pytest.approx(0.5)
    assert b.ic_std == pytest.approx(sqrt(0.5))
    assert b.ic_t_stat == pytest.approx(1.0)


def test_minute_fund_scores_bar_prints_never_the_daily_close():
    bars = ["2024-06-03T13:00:00", "2024-06-03T13:05:00", "2024-06-03T13:10:00"]
    daily_close = {"AAA": 100.0}  # what the assessment marks every bar of the day with
    def decision(bar):
        return _decision(bar, daily_close, {"value": _signals("buffett", {"AAA": 0.5})}, spec=MINUTE_SPEC)
    def cycle(bar, price):
        return _cycle(bar, {"AAA": price}, {"value": {"AAA": 0.5}}, 100_000.0, {"AAA": 480}, 52_000.0, spec=MINUTE_SPEC)
    records = [
        _session(bars[0], decision=decision(bars[0])),
        _session(bars[1], decision=decision(bars[1]), executed=cycle(bars[1], 104.0),
                 marks={"AAA": 104.0}, positions={"AAA": 480}),
        _session(bars[2], decision=decision(bars[2]), executed=cycle(bars[2], 106.0),
                 marks={"AAA": 106.0}, positions={"AAA": 480}),
    ]
    card = score(records)
    buffett = _by_name(card)["buffett"]
    assert buffett.n_views == 1               # bar 1 has no print; bar 3 is last
    assert buffett.hit_rate == 1.0
    assert card.horizon == "every 5m"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def _attribution_ledger(momo: dict[str, float] | None = None, d3_decision_marks: dict[str, float] | None = None):
    momo = momo or {"AAA": 0.20}
    e2_marks = {"AAA": 110.0, "BBB": 45.0, "CCC": 100.0}
    e3_marks = {"AAA": 115.5, "BBB": 54.0}
    positions = {"AAA": 454, "BBB": -222}
    contributions = {"value": {"AAA": 0.30, "BBB": -0.10}, "momo": momo}
    d3 = _decision(D3, d3_decision_marks, {}) if d3_decision_marks is not None else None
    return [
        _session(D1, decision=_decision(D1, MARKS[D1], {})),
        _session(D2, executed=_cycle(D1, e2_marks, contributions, 100_000.0, positions, 60_050.0),
                 marks={"AAA": 110.0, "BBB": 45.0}, positions=positions),
        _session(D3, executed=_cycle(D2, e3_marks, contributions, 100_499.0, positions, 60_050.0),
                 marks=e3_marks, positions=positions, decision=d3),
    ]


def test_strategy_attribution_by_hand():
    card = score(_attribution_ledger())
    value, momo = card.strategies
    assert [s.name for s in card.strategies] == ["value", "momo"]
    # value: .30 * +5% + (-.10) * +20% = -0.5% ; momo: .20 * +5% = +1%
    assert value.pnl == pytest.approx(-500.0)
    assert value.return_pct == pytest.approx(-0.005)
    assert value.win_rate == 0.0
    assert value.max_drawdown_pct == pytest.approx(0.005)
    assert momo.pnl == pytest.approx(1000.0)
    assert momo.win_rate == 1.0
    assert momo.max_drawdown_pct == 0.0
    assert (value.n_periods, momo.n_periods) == (1, 1)
    assert card.fund_pnl == pytest.approx(499.0)       # 454 * 5.5 - 222 * 9
    assert card.unattributed == pytest.approx(-1.0)    # whole-share rounding
    assert value.share_of_pnl == pytest.approx(-500 / 499)
    assert momo.share_of_pnl == pytest.approx(1000 / 499)


def test_unfilled_target_is_priced_from_the_next_decision_on_a_daily_fund():
    momo = {"AAA": 0.20, "CCC": 0.00001}  # sub-share target: in the marks at E, never held
    priced = score(_attribution_ledger(momo=momo, d3_decision_marks={"CCC": 200.0}))
    assert priced.strategies[1].pnl == pytest.approx(1001.0)
    assert priced.unattributed == pytest.approx(-2.0)
    dropped = score(_attribution_ledger(momo=momo, d3_decision_marks={"AAA": 115.5}))
    assert dropped.strategies[1].pnl == pytest.approx(1000.0)


def test_no_executions_and_no_records():
    card = score([_session(D1, decision=_decision(D1, MARKS[D1], {}))])
    assert card.strategies == []
    assert card.analysts == []
    assert card.fund_pnl == 0.0
    assert card.unattributed == 0.0
    with pytest.raises(ValueError):
        score([])


def test_trading_cost_counts_every_execution_but_the_last():
    """fund_pnl runs to the last execution's pre-fill equity, so that
    execution's own spread and commission fall outside the window."""
    def charged(record: SessionRecord) -> SessionRecord:
        x = record.executed
        order = Order(ticker="AAA", side="buy", quantity=10, price=100.0)
        fill = Fill(ticker="AAA", side="buy", quantity=10, price=100.05)
        costed = x.model_copy(update={"orders": [order], "fills": [fill],
                                      "cash_before": x.cash + 10 * 100.05 + 0.05})
        assert costed.slippage == pytest.approx(0.50) and costed.commission == pytest.approx(0.05)
        return record.model_copy(update={"executed": costed})
    records = [charged(r) if r.executed is not None else r for r in _attribution_ledger()]
    card = score(records)
    assert card.trading_cost == pytest.approx(0.55)   # E2 only; E3 is the last execution
    assert card.unattributed == pytest.approx(-1.0)   # unchanged: equity_before is pre-fill


def test_max_drawdown_of_a_sleeve():
    prices = [100.0, 110.0, 88.0, 92.4]  # +10%, -20%, +5%
    days = ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"]
    records = [
        _session(day, executed=_cycle(day, {"AAA": price}, {"momo": {"AAA": 1.0}}, 100_000.0, {"AAA": 1}, 0.0),
                 marks={"AAA": price}, positions={"AAA": 1})
        for day, price in zip(days, prices)
    ]
    momo = score(records).strategies[0]
    assert momo.n_periods == 3
    assert momo.max_drawdown_pct == pytest.approx(0.2)
    assert momo.return_pct == pytest.approx(-0.076)
    assert momo.win_rate == pytest.approx(2 / 3)
