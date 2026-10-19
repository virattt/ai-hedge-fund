"""Clocks — what "complete", "previous" and "the price at a session" mean per
cadence — and `advance` on bars with live prints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.models import Price, PriceSnapshot
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import Fund, FundSpec, TradingWindow
from hedge_fund.pipeline.clock import bar_key, BarClock, clock_for, DailyClock, LiveClock
from hedge_fund.pipeline.session import advance, FundState, is_rebalance_session, next_state, SessionRecord
from hedge_fund.pipeline.test_stages import FakeAnalyst

FIXTURE = Path(__file__).parent / "fixtures" / "record_before_intraday.json"


def _spec(**overrides):
    base = dict(
        schema_version=2, name="bar-fund",
        strategies=[{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0, rebalance="minute", interval=5,
    )
    merged = {**base, **overrides}
    if merged["rebalance"] != "minute":
        merged.pop("interval")
    return FundSpec(**merged)


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "a", FakeAnalyst)


class Tape:
    """Fake data: a price path per ticker, served as prints (now) and as
    1-minute bars (history). Daily closes for the analysts' lookback marks."""

    def __init__(self, path, *, now):
        self.path = path            # ticker -> {session key -> price}
        self.now = now              # aware datetime, advanced by the test
        self.snapshot_calls = []

    def get_snapshot(self, ticker):
        self.snapshot_calls.append(ticker)
        key = max(k for k in self.path[ticker] if datetime.strptime(k, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=NEW_YORK) <= self.now)
        stamp = datetime.strptime(key, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=NEW_YORK)
        return PriceSnapshot(ticker=ticker, price=self.path[ticker][key],
                             time=stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        if interval == "minute":
            return [Price(open=p, close=p, high=p, low=p, volume=1,
                          time=datetime.strptime(k, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=NEW_YORK).isoformat())
                    for k, p in sorted(self.path.get(ticker, {}).items()) if start_date <= k[:10] <= end_date]
        last = self.path[ticker][max(self.path[ticker])]
        return [Price(open=last, close=last, high=last, low=last, volume=1, time=f"{end_date}T00:00:00Z")]


def _at(h, m, s=0, day="2024-06-04"):
    return datetime.fromisoformat(f"{day}T{h:02d}:{m:02d}:{s:02d}").replace(tzinfo=NEW_YORK)


def test_minute_is_a_rebalance_every_bar_and_periods_read_the_date_of_a_bar():
    assert is_rebalance_session("2024-06-04T09:35:00", "2024-06-04T09:30:00", "minute")
    assert not is_rebalance_session("2024-06-04T09:35:00", "2024-06-04T09:30:00", "weekly")
    assert is_rebalance_session("2024-06-10T09:30:00", "2024-06-07T16:00:00", "weekly")


def test_records_written_before_print_times_existed_still_verify():
    record = SessionRecord.model_validate_json(FIXTURE.read_text())
    assert record.snapshot_times is None and record.decision is not None
    assert record.hash == record.compute_hash()
    # The field counts the moment it is set; a bar's record is not a day's.
    stamped = record.model_copy(update={"snapshot_times": {"TEST": "2025-01-17T21:00:00Z"}})
    assert stamped.compute_hash() != record.hash


def test_clock_for_picks_by_mandate():
    data = object()
    assert isinstance(clock_for(_spec(rebalance="weekly"), data), DailyClock)
    assert isinstance(clock_for(_spec(), data), BarClock)
    assert isinstance(clock_for(_spec(), data, live=True), LiveClock)


def test_bar_key_normalizes_any_zone_to_new_york():
    assert bar_key("2024-06-04T13:35:00Z") == "2024-06-04T09:35:00"
    assert bar_key("2024-06-04T09:35:00-04:00") == "2024-06-04T09:35:00"
    assert bar_key("2024-06-04T09:35:00") == "2024-06-04T09:35:00"


def test_bar_clock_marks_at_the_close_of_the_bar_that_ended_by_then(monkeypatch):
    monkeypatch.setattr("hedge_fund.pipeline.clock.completed_through", lambda: "2024-06-04")
    path = {"AAPL": {"2024-06-04T09:30:00": 100.0, "2024-06-04T09:31:00": 101.0,
                     "2024-06-04T09:34:00": 104.0, "2024-06-04T09:35:00": 105.0}}
    clock = BarClock(Tape(path, now=_at(16, 0)), 300, TradingWindow())
    assert clock.marks(["AAPL"], "2024-06-04T09:35:00").prices == {"AAPL": 104.0}  # 09:34 bar ends at 09:35
    assert clock.marks(["AAPL"], "2024-06-04T09:30:00").prices == {"AAPL": 100.0}  # nothing before: the open
    assert clock.marks(["AAPL"], "2024-06-04T09:35:00").times is None
    assert clock.previous("2024-06-04T09:35:00") == "2024-06-04T09:30:00"
    assert clock.session_date("2024-06-04T09:35:00") == "2024-06-04"
    with pytest.raises(ValueError, match="not yet complete"):
        clock.marks(["AAPL"], "2024-06-05T09:30:00")
    with pytest.raises(ValueError, match="MSFT: no minute bar"):
        clock.marks(["MSFT"], "2024-06-04T09:35:00")


def test_live_clock_takes_every_print_once_per_bar_and_records_when_each_was():
    path = {"AAPL": {"2024-06-04T09:30:00": 100.0, "2024-06-04T09:35:00": 105.0},
            "SPY": {"2024-06-04T09:30:00": 500.0, "2024-06-04T09:33:00": 501.0}}
    tape = Tape(path, now=_at(9, 34))
    clock = LiveClock(tape, 300, TradingWindow(), now=lambda: tape.now)
    assert clock.current() == "2024-06-04T09:30:00"
    with pytest.raises(ValueError, match="not closed yet"):
        clock.marks(["AAPL"], "2024-06-04T09:35:00")
    tape.now = _at(9, 35)
    marked = clock.marks(["AAPL", "SPY"], "2024-06-04T09:35:00")
    assert marked.prices == {"AAPL": 105.0, "SPY": 501.0}
    assert marked.times["SPY"] == "2024-06-04T13:33:00Z"  # SPY last printed two minutes ago
    # Asking again for the same bar serves the same prints; a new name is fetched.
    clock.marks(["AAPL"], "2024-06-04T09:35:00")
    assert tape.snapshot_calls == ["AAPL", "SPY"]
    clock.observe(["SPY", "AAPL"], "2024-06-04T09:35:00")
    assert tape.snapshot_calls == ["AAPL", "SPY"]


def test_advance_on_bars_decides_at_one_bar_and_fills_at_the_next_with_prints():
    """Two bars, five minutes apart, one afternoon. The first bar decides;
    the second fills at the second bar's prints and stamps their times."""
    path = {"AAPL": {"2024-06-04T13:00:00": 100.0, "2024-06-04T13:05:00": 102.0},
            "SPY": {"2024-06-04T13:00:00": 500.0, "2024-06-04T13:05:00": 500.0}}
    tape = Tape(path, now=_at(13, 1))
    spec = _spec()
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    clock = LiveClock(tape, 300, TradingWindow(), now=lambda: tape.now)
    broker = SimBroker(cash=spec.capital)
    state = FundState.initial(spec.capital)

    first = advance(fund, state, "2024-06-04T13:00:00", broker, tape, ["AAPL"], clock)
    assert first.rebalance and first.decision is not None and first.executed is None
    assert first.decision.final_weights == {"AAPL": 1.0}
    assert first.snapshot_times == {"SPY": "2024-06-04T17:00:00Z"}  # nothing held yet
    state = next_state(state, first)
    with pytest.raises(ValueError, match="not complete yet"):
        advance(fund, state, "2024-06-04T13:05:00", broker, tape, ["AAPL"], clock)

    tape.now = _at(13, 5)
    second = advance(fund, state, "2024-06-04T13:05:00", broker, tape, ["AAPL"], clock)
    assert second.executed is not None and second.executed.execution_policy == "next_bar"
    assert second.executed.fills[0].price == 102.0 and second.positions == {"AAPL": 980}
    assert second.executed.refreshed_assessment.as_of == "2024-06-04T13:00:00"  # not stale: no re-ask
    assert second.snapshot_times == {"AAPL": "2024-06-04T17:05:00Z", "SPY": "2024-06-04T17:05:00Z"}
    assert second.hash == second.compute_hash() and second.prev_hash == first.hash
    assert second.rebalance and second.decision is not None  # every bar decides


def test_a_stale_pending_is_refreshed_at_the_bar_before_execution():
    """Skip-to-now: a decision from yesterday executes at today's 10:05 bar.
    The cutoff is 10:00 today, not yesterday, so the analysts are re-asked."""
    yesterday = "2024-06-03"
    path = {"AAPL": {f"{yesterday}T16:00:00": 100.0, "2024-06-04T10:00:00": 90.0, "2024-06-04T10:05:00": 91.0},
            "SPY": {f"{yesterday}T16:00:00": 500.0, "2024-06-04T10:05:00": 500.0}}
    tape = Tape(path, now=_at(16, 0, day=yesterday))
    spec = _spec()
    analyst = FakeAnalyst("a", views={"AAPL": 1.0})
    fund = Fund(spec, models={"solo": [analyst]})
    clock = LiveClock(tape, 300, TradingWindow(), now=lambda: tape.now)
    broker = SimBroker(cash=spec.capital)
    state = next_state(FundState.initial(spec.capital),
                       advance(fund, FundState.initial(spec.capital), f"{yesterday}T16:00:00", broker, tape, ["AAPL"], clock))
    asked_before = len(analyst.predict_calls)

    tape.now = _at(10, 5) + timedelta(seconds=1)
    record = advance(fund, state, "2024-06-04T10:05:00", broker, tape, ["AAPL"], clock)
    assert record.executed.refreshed_assessment.as_of == "2024-06-04T10:00:00"
    assert record.executed.original_assessment.as_of == f"{yesterday}T16:00:00"
    assert len(analyst.predict_calls) > asked_before  # refreshed, then decided again at 10:05
    assert record.executed.fills[0].price == 91.0
