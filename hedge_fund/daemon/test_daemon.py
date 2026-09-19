"""Scheduler daemon — idempotent ticks and kill-switch, no wall-clock sleep."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.daemon import (
    KILL_SWITCH_ENV,
    FileTickStore,
    KillSwitch,
    ScheduleConfig,
    TickResult,
    already_completed,
    broker_for_venue,
    evaluate_tick,
    period_closed,
    rebalance_due,
    run_loop,
    session_date,
    tick_key,
)
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.ledger import save_cycle_record
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.pipeline.run_cycle import run_cycle


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDataClient:
    """Canned closes. `series` is ticker -> {day: close}; `closes` is a
    single close reused on *end_date* (enough for run_cycle marks).
    """

    def __init__(self, closes=None, series=None):
        self._closes = closes or {}
        self._series = series or {}
        self.price_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        self.price_calls.append((ticker, start_date, end_date))
        if ticker in self._series:
            return [
                Price(open=c, close=c, high=c, low=c, volume=1000,
                      time=f"{day}T00:00:00Z")
                for day, c in sorted(self._series[ticker].items())
                if start_date <= day <= end_date
            ]
        close = self._closes.get(ticker)
        if close is None:
            return []
        return [Price(open=close, close=close, high=close, low=close,
                      volume=1000, time=f"{end_date}T00:00:00Z")]


class FakeAnalyst:
    def __init__(self, name, views=None):
        self._name = name
        self._views = views or {}
        self.predict_calls = []

    @property
    def name(self):
        return self._name

    def predict(self, ticker, date, data_client):
        self.predict_calls.append((ticker, date))
        return Signal(model_name=self._name, ticker=ticker, date=date,
                      value=self._views.get(ticker, 0.0))


def _fund(name="desk", rebalance="daily", analyst=None):
    spec = FundSpec(
        name=name,
        strategies=[{"name": "solo", "models": [{"name": "pead"}]}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0,
        rebalance=rebalance,
        benchmark="SPY",
    )
    staff = analyst or FakeAnalyst("pead", views={"AAPL": 1.0})
    return Fund(spec, models={"solo": [staff]}), staff


def _store(tmp_path: Path) -> FileTickStore:
    return FileTickStore(tmp_path / "ticks")


def _days(*dates: str) -> list[str]:
    return list(dates)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def test_session_date_weekend_snaps_to_friday():
    days = _days("2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07")
    assert session_date(days, "2024-06-08") == "2024-06-07"
    assert session_date(days, "2024-06-07") == "2024-06-07"
    assert session_date(days, "2024-06-02") is None


def test_weekly_not_due_before_friday():
    days = _days("2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07")
    assert rebalance_due(days, "2024-06-07", "weekly")
    assert not period_closed("2024-06-06", "2024-06-06", "weekly")
    assert period_closed("2024-06-07", "2024-06-07", "weekly")
    assert period_closed("2024-06-06", "2024-06-07", "weekly")


def test_monthly_waits_until_month_end():
    assert not period_closed("2024-06-14", "2024-06-14", "monthly")
    assert period_closed("2024-06-28", "2024-06-30", "monthly")


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_duplicate_tick_is_a_noop(tmp_path):
    fund, analyst = _fund()
    store = _store(tmp_path)
    kill = KillSwitch(tmp_path / "KILL", environ={})
    data = FakeDataClient(closes={"AAPL": 200.0, "SPY": 100.0})
    days = _days("2024-06-03")
    kwargs = dict(
        fund=fund, universe=["AAPL"], as_of="2024-06-03", data_client=data,
        receipts=tmp_path, store=store, kill_switch=kill, venue="paper",
        trading_days=days,
    )

    first = evaluate_tick(**kwargs)
    assert first.status == "ran"
    assert first.key == "desk:2024-06-03"
    assert first.record is not None
    assert first.record.positions == {"AAPL": 500}
    assert len(analyst.predict_calls) == 1
    receipts = list(tmp_path.glob("desk-run-*.json"))
    assert len(receipts) == 1
    assert store.seen("desk:2024-06-03")

    second = evaluate_tick(**kwargs)
    assert second.status == "skipped"
    assert second.reason == "duplicate tick"
    assert second.record is None
    assert len(analyst.predict_calls) == 1
    assert len(list(tmp_path.glob("desk-run-*.json"))) == 1


def test_receipt_for_the_same_session_is_also_a_duplicate(tmp_path):
    """A one-shot paper CLI run for this session is the same tick."""
    fund, analyst = _fund()
    store = _store(tmp_path)
    data = FakeDataClient(closes={"AAPL": 200.0})
    record = run_cycle(fund, "2024-06-03", PaperBroker(cash=100_000.0),
                       data, ["AAPL"])
    save_cycle_record(record, tmp_path)
    calls_after_seed = len(analyst.predict_calls)

    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-03", data_client=data,
        receipts=tmp_path, store=store,
        kill_switch=KillSwitch(tmp_path / "KILL", environ={}),
        venue="paper", trading_days=_days("2024-06-03"),
    )
    assert result.status == "skipped"
    assert result.reason == "duplicate tick"
    assert len(analyst.predict_calls) == calls_after_seed
    assert store.seen("desk:2024-06-03")


def test_tick_key_is_mandate_plus_session():
    assert tick_key("example-fund", "2024-06-07") == "example-fund:2024-06-07"


def test_already_completed_reads_the_store(tmp_path):
    store = _store(tmp_path)
    store.remember("desk:2024-06-03")
    assert already_completed("desk", "2024-06-03", tmp_path, store)


# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------

def test_kill_switch_file_halts_without_running(tmp_path):
    fund, analyst = _fund()
    kill_path = tmp_path / "KILL"
    kill_path.write_text("")
    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-03",
        data_client=FakeDataClient(closes={"AAPL": 200.0}),
        receipts=tmp_path, store=_store(tmp_path),
        kill_switch=KillSwitch(kill_path, environ={}),
        venue="paper", trading_days=_days("2024-06-03"),
    )
    assert result.status == "halted"
    assert result.reason == "kill-switch is on"
    assert analyst.predict_calls == []
    assert list(tmp_path.glob("desk-run-*.json")) == []
    assert not _store(tmp_path).seen("desk:2024-06-03")


def test_kill_switch_env_halts_without_running(tmp_path):
    fund, analyst = _fund()
    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-03",
        data_client=FakeDataClient(closes={"AAPL": 200.0}),
        receipts=tmp_path, store=_store(tmp_path),
        kill_switch=KillSwitch(tmp_path / "KILL", environ={KILL_SWITCH_ENV: "1"}),
        venue="paper", trading_days=_days("2024-06-03"),
    )
    assert result.status == "halted"
    assert analyst.predict_calls == []


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "FALSE"])
def test_kill_switch_env_off_values_do_not_halt(tmp_path, value):
    kill = KillSwitch(tmp_path / "KILL", environ={KILL_SWITCH_ENV: value})
    assert not kill.active()


def test_kill_switch_re_reads_the_file(tmp_path):
    path = tmp_path / "KILL"
    kill = KillSwitch(path, environ={})
    assert not kill.active()
    path.write_text("stop")
    assert kill.active()


# ---------------------------------------------------------------------------
# Loop — injectable sleep, no wall-clock wait
# ---------------------------------------------------------------------------

def test_loop_halts_on_kill_without_sleeping(tmp_path):
    slept: list[float] = []
    results = run_loop(
        lambda: TickResult(status="halted", reason="kill-switch is on"),
        interval_seconds=10_000,
        sleep=slept.append,
    )
    assert [r.status for r in results] == ["halted"]
    assert slept == []


def test_loop_once_does_not_sleep():
    slept: list[float] = []
    results = run_loop(
        lambda: TickResult(status="ran", reason="cycle completed"),
        interval_seconds=10_000,
        sleep=slept.append,
        once=True,
    )
    assert len(results) == 1
    assert slept == []


def test_loop_sleeps_only_between_live_polls():
    slept: list[float] = []
    states = ["ran", "skipped"]

    def tick():
        return TickResult(status=states.pop(0), reason="x")

    n = {"left": 2}

    def more():
        n["left"] -= 1
        return n["left"] > 0

    results = run_loop(
        tick, interval_seconds=10_000, sleep=slept.append, should_continue=more,
    )
    assert [r.status for r in results] == ["ran", "skipped"]
    assert slept == [10_000]


def test_loop_does_not_call_time_sleep(monkeypatch):
    def forbidden(_seconds):
        raise AssertionError("wall-clock sleep")

    monkeypatch.setattr(time, "sleep", forbidden)
    run_loop(
        lambda: TickResult(status="halted", reason="kill-switch is on"),
        interval_seconds=10_000,
        sleep=lambda _s: None,
    )


def test_evaluate_then_halt_in_loop_never_sleeps_the_interval(tmp_path):
    """Acceptance: halt-on-kill in the poll loop without a long sleep."""
    fund, analyst = _fund()
    store = _store(tmp_path)
    kill_path = tmp_path / "KILL"
    kill = KillSwitch(kill_path, environ={})
    data = FakeDataClient(closes={"AAPL": 200.0})
    days = _days("2024-06-03")
    slept: list[float] = []
    n = {"i": 0}

    def tick():
        n["i"] += 1
        if n["i"] == 2:
            kill_path.write_text("")
        return evaluate_tick(
            fund, ["AAPL"], as_of="2024-06-03", data_client=data,
            receipts=tmp_path, store=store, kill_switch=kill, venue="paper",
            trading_days=days,
        )

    results = run_loop(tick, interval_seconds=10_000, sleep=slept.append)
    assert [r.status for r in results] == ["ran", "halted"]
    assert slept == [10_000]
    assert len(analyst.predict_calls) == 1


# ---------------------------------------------------------------------------
# Venue
# ---------------------------------------------------------------------------

def test_paper_venue_opens_paper_broker(tmp_path):
    broker, prior = broker_for_venue("paper", "desk", 50_000.0, tmp_path)
    assert isinstance(broker, PaperBroker)
    assert broker.venue == "paper"
    assert prior is None
    assert broker.cash() == pytest.approx(50_000.0)


def test_sim_venue_opens_sim_broker(tmp_path):
    broker, prior = broker_for_venue("sim", "desk", 75_000.0, tmp_path)
    assert isinstance(broker, SimBroker)
    assert broker.venue == "sim"
    assert prior is None
    assert broker.cash() == pytest.approx(75_000.0)


def test_live_venue_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="paper or sim"):
        broker_for_venue("live", "desk", 100_000.0, tmp_path)
    with pytest.raises(ValueError, match="paper or sim"):
        ScheduleConfig(venue="ibkr")
    fund, _ = _fund()
    with pytest.raises(ValueError, match="paper or sim"):
        evaluate_tick(
            fund, ["AAPL"], as_of="2024-06-03",
            data_client=FakeDataClient(closes={"AAPL": 200.0}),
            receipts=tmp_path, store=_store(tmp_path),
            kill_switch=KillSwitch(tmp_path / "KILL", environ={}),
            venue="live", trading_days=_days("2024-06-03"),
        )


def test_weekly_midweek_is_not_due(tmp_path):
    fund, analyst = _fund(rebalance="weekly")
    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-06",
        data_client=FakeDataClient(closes={"AAPL": 200.0}),
        receipts=tmp_path, store=_store(tmp_path),
        kill_switch=KillSwitch(tmp_path / "KILL", environ={}),
        venue="paper",
        trading_days=_days("2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"),
    )
    assert result.status == "not_due"
    assert analyst.predict_calls == []


def test_weekly_friday_runs(tmp_path):
    fund, analyst = _fund(rebalance="weekly")
    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-07",
        data_client=FakeDataClient(closes={"AAPL": 200.0}),
        receipts=tmp_path, store=_store(tmp_path),
        kill_switch=KillSwitch(tmp_path / "KILL", environ={}),
        venue="paper",
        trading_days=_days(
            "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07",
        ),
    )
    assert result.status == "ran"
    assert result.session_date == "2024-06-07"
    assert len(analyst.predict_calls) == 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _mandate(path: Path, name="desk", rebalance="daily") -> Path:
    path.write_text(
        f"""name: {name}
strategies:
  - name: solo
    models:
      - name: pead
risk:
  max_position_pct: 1.0
  max_gross_exposure: 1.0
capital: 100000
rebalance: {rebalance}
benchmark: SPY
"""
    )
    return path


def _patch_cli(monkeypatch, tmp_path, closes):
    from hedge_fund.daemon import __main__ as cli
    from hedge_fund.tui import keys

    monkeypatch.setattr(keys, "ENV_PATH", tmp_path / "saved.env")
    monkeypatch.setattr(cli, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "FDClient", lambda: FakeDataClient(closes))
    monkeypatch.setattr(cli, "CachedDataClient", lambda raw: raw)
    monkeypatch.setattr(cli, "TICKS_DIR", tmp_path / "ticks")
    monkeypatch.setattr(cli, "KILL_SWITCH_PATH", tmp_path / "KILL")
    monkeypatch.setattr(cli, "USER_DIR", tmp_path)

    real_fund = Fund

    def fake_fund(spec):
        return Fund(spec, models={"solo": [FakeAnalyst("pead", views={"AAPL": 1.0})]})

    monkeypatch.setattr(cli, "Fund", fake_fund)
    return cli, real_fund


def test_cli_once_skips_on_duplicate(tmp_path, monkeypatch, capsys):
    cli, _ = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0, "SPY": 100.0})
    mandate = _mandate(tmp_path / "fund.yaml")
    argv = [
        str(mandate), "--tickers", "AAPL", "--once",
        "--date", "2024-06-03", "--ticks-dir", str(tmp_path / "ticks"),
        "--kill-switch", str(tmp_path / "KILL"), "--receipts", str(tmp_path),
    ]
    cli.main(argv)
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "ran"
    assert first["key"] == "desk:2024-06-03"
    assert first["record"]["nav"] == pytest.approx(100_000.0)

    cli.main(argv)
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "skipped"
    assert second["reason"] == "duplicate tick"
    assert "record" not in second


def test_cli_once_halts_on_kill_file(tmp_path, monkeypatch, capsys):
    cli, _ = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0, "SPY": 100.0})
    mandate = _mandate(tmp_path / "fund.yaml")
    kill = tmp_path / "KILL"
    kill.write_text("")
    cli.main([
        str(mandate), "--tickers", "AAPL", "--once",
        "--date", "2024-06-03", "--kill-switch", str(kill),
        "--ticks-dir", str(tmp_path / "ticks"), "--receipts", str(tmp_path),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "halted"
    assert payload["reason"] == "kill-switch is on"
    assert list(tmp_path.glob("desk-run-*.json")) == []


def test_cli_once_halts_on_kill_env(tmp_path, monkeypatch, capsys):
    cli, _ = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0, "SPY": 100.0})
    monkeypatch.setenv(KILL_SWITCH_ENV, "true")
    mandate = _mandate(tmp_path / "fund.yaml")
    cli.main([
        str(mandate), "--tickers", "AAPL", "--once",
        "--date", "2024-06-03", "--kill-switch", str(tmp_path / "absent"),
        "--ticks-dir", str(tmp_path / "ticks"), "--receipts", str(tmp_path),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "halted"


def test_cli_rejects_live_venue(tmp_path, monkeypatch):
    from hedge_fund.daemon import __main__ as cli

    mandate = _mandate(tmp_path / "fund.yaml")
    with pytest.raises(SystemExit):
        cli.main([str(mandate), "--tickers", "AAPL", "--venue", "live", "--once"])


def test_cli_schedule_file_and_once(tmp_path, monkeypatch, capsys):
    cli, _ = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0, "SPY": 100.0})
    mandate = _mandate(tmp_path / "fund.yaml")
    config = tmp_path / "schedule.yaml"
    config.write_text(
        "interval_seconds: 10000\n"
        "venue: sim\n"
        f"kill_switch: {tmp_path / 'KILL'}\n"
        f"ticks_dir: {tmp_path / 'ticks'}\n"
    )
    cli.main([
        str(mandate), "--tickers", "AAPL", "--once",
        "--date", "2024-06-03", "--config", str(config),
        "--receipts", str(tmp_path),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ran"
    assert payload["venue"] == "sim"


def test_cli_unknown_schedule_key_fails(tmp_path):
    from hedge_fund.daemon import __main__ as cli

    mandate = _mandate(tmp_path / "fund.yaml")
    config = tmp_path / "schedule.yaml"
    config.write_text("live_venue: ibkr\n")
    with pytest.raises(SystemExit):
        cli.main([
            str(mandate), "--tickers", "AAPL", "--once", "--config", str(config),
        ])


# ---------------------------------------------------------------------------
# Record type stays a CycleRecord
# ---------------------------------------------------------------------------

def test_ran_tick_writes_a_cycle_record(tmp_path):
    fund, _ = _fund()
    result = evaluate_tick(
        fund, ["AAPL"], as_of="2024-06-03",
        data_client=FakeDataClient(closes={"AAPL": 200.0}),
        receipts=tmp_path, store=_store(tmp_path),
        kill_switch=KillSwitch(tmp_path / "KILL", environ={}),
        venue="sim", trading_days=_days("2024-06-03"),
    )
    assert result.status == "ran"
    assert isinstance(result.record, CycleRecord)
    loaded = CycleRecord.model_validate_json(
        next(tmp_path.glob("desk-run-*.json")).read_text()
    )
    assert loaded == result.record
