"""The allocator — mandate weights moved by the scorecard, by hand."""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from unittest.mock import Mock

import pytest

from hedge_fund.fund import FundSpec
from hedge_fund.pipeline.models import Allocated, AllocationRecord
from hedge_fund.pipeline.session import FundState
from hedge_fund.scorecard import allocate, current_allocation, score
from hedge_fund.scorecard.test_scorecard import _cycle, _decision, _session, _signals

SPEC = FundSpec(**{
    "schema_version": 2, "name": "test", "rebalance": "daily",
    "strategies": [
        {"name": "value", "models": [{"name": "buffett"}, {"name": "munger"}], "blend": {"mode": "long_short"}},
        {"name": "momo", "weight": 2.0, "models": [{"name": "buffett"}], "blend": {"mode": "long_short"}},
    ],
    "risk": {"max_position_pct": 1, "max_gross_exposure": 1},
    "allocation": {},
})
TICKERS = ["AAA", "BBB", "CCC", "DDD"]
GROWTH = {"AAA": 1.04, "BBB": 1.03, "CCC": 1.02, "DDD": 1.01}   # the same order every day
EXACT = {"AAA": 0.9, "BBB": 0.5, "CCC": 0.2, "DDD": -0.5}        # ranks the names as they go on to return
SWAPPED = {"AAA": 0.9, "BBB": 0.2, "CCC": 0.5, "DDD": -0.5}      # one adjacent swap: Spearman 0.8


def _ledger(n_sessions: int):
    """Every session decides and executes. Buffett's IC alternates 1 and 0.8,
    Munger's the mirror; the value sleeve's period return alternates 2% and
    1% (half, then a quarter, of equity in AAA). Momo never executes."""
    records = []
    prices = {t: 100.0 for t in TICKERS}
    for i in range(n_sessions):
        day = (_date(2024, 6, 3) + timedelta(days=i)).isoformat()
        views = EXACT if i % 2 == 0 else SWAPPED
        decision = _decision(day, dict(prices), {
            "value": _signals("buffett", views) + _signals("munger", {t: -v for t, v in views.items()}),
            "momo": _signals("buffett", views),
        }, spec=SPEC)
        executed = _cycle(day, dict(prices), {"value": {"AAA": 0.5 if i % 2 == 0 else 0.25}},
                          100_000.0, {}, 100_000.0, spec=SPEC)
        records.append(_session(day, decision=decision, executed=executed))
        prices = {t: p * GROWTH[t] for t, p in prices.items()}
    return records


def test_enough_evidence_moves_every_weight_the_scorecard_grades():
    records = _ledger(21)   # 20 graded dates, 20 periods
    card = score(records)
    assert {a.name: a.n_dates for a in card.analysts} == {"buffett": 20, "munger": 20}
    assert {s.name: s.n_periods for s in card.strategies} == {"value": 20}
    allocation = allocate(SPEC, records, "2024-06-24")
    assert allocation.as_of == "2024-06-24"
    value, momo = allocation.strategies["value"], allocation.strategies["momo"]
    assert (value.mandate, value.n, value.weight) == (1.0, 20, 2.0)          # t far above +4: the cap
    assert value.t_stat == pytest.approx(card.strategies[0].t_stat)
    assert momo == Allocated(mandate=2.0, t_stat=None, n=0, weight=2.0)      # never executed: as written
    buffett = allocation.models["value"]["buffett"]
    assert (buffett.n, buffett.weight) == (20, 2.0)                            # IC t far above +4: the cap
    assert allocation.models["momo"]["buffett"] == buffett                      # graded fund-wide, moved the same way
    munger = allocation.models["value"]["munger"]
    assert (munger.n, munger.weight) == (20, 0.25)                             # the mirror: the floor
    assert munger.t_stat == pytest.approx(-buffett.t_stat)


def test_one_short_of_the_evidence_keeps_the_mandate():
    allocation = allocate(SPEC, _ledger(20), "2024-06-23")   # 19 dates, 19 periods
    assert allocation.strategies["value"].n == 19
    assert allocation.strategies["value"].weight == 1.0
    assert all(a.weight == a.mandate for a in allocation.strategies.values())
    assert all(a.weight == a.mandate for pod in allocation.models.values() for a in pod.values())


def test_an_empty_ledger_is_the_mandate_as_written():
    allocation = allocate(SPEC, [], "2024-06-03")
    assert allocation.strategies == {
        "value": Allocated(mandate=1.0, t_stat=None, n=0, weight=1.0),
        "momo": Allocated(mandate=2.0, t_stat=None, n=0, weight=2.0),
    }
    assert allocation.models["value"]["munger"] == Allocated(mandate=1.0, t_stat=None, n=0, weight=1.0)
    with pytest.raises(ValueError, match="no allocation policy"):
        allocate(SPEC.model_copy(update={"allocation": None}), [], "2024-06-03")


def test_current_allocation_scores_once_a_day():
    untouched = Mock(side_effect=AssertionError("the ledger must not be read"))
    assert current_allocation(SPEC.model_copy(update={"allocation": None}), FundState(cash=1.0), "2024-06-04", untouched) is None
    scored = AllocationRecord(as_of="2024-06-04T13:00:00", strategies={}, models={})
    state = FundState(cash=1.0, allocation=scored)
    assert current_allocation(SPEC, state, "2024-06-04T13:05:00", untouched) is scored   # same day: reused
    fresh = current_allocation(SPEC, state, "2024-06-05T13:00:00", lambda: _ledger(3))   # new day: rescored
    assert fresh.as_of == "2024-06-05T13:00:00" and fresh.strategies["value"].n == 2
    first = current_allocation(SPEC, FundState(cash=1.0), "2024-06-03", list)             # nothing yet: as written
    assert first.strategies["momo"].weight == 2.0
