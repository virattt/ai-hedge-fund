"""CLI paper path — live clock, PaperBroker, ledger read-back. No live APIs."""

from __future__ import annotations

import sys

import pytest

from hedge_fund.backtesting.fund import backtest_fund
from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.models import Signal
from hedge_fund.ledger import latest_run_receipt
from hedge_fund.pipeline.models import CycleRecord


class FakeDataClient:
    def __init__(self, closes):
        self._closes = closes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        close = self._closes.get(ticker)
        if close is None:
            return []
        return [Price(open=close, close=close, high=close, low=close,
                      volume=1000, time=f"{end_date}T00:00:00Z")]


class FakeAnalyst:
    def __init__(self, name, views=None):
        self._name = name
        self._views = views or {}

    @property
    def name(self):
        return self._name

    def predict(self, ticker, date, data_client):
        return Signal(model_name=self._name, ticker=ticker, date=date,
                      value=self._views.get(ticker, 0.0))


def _mandate(path, name="paper-desk"):
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
"""
    )
    return path


def _fake_fund(spec):
    return Fund(spec, models={"solo": [FakeAnalyst("pead", views={"AAPL": 1.0})]})


def _patch_cli(monkeypatch, tmp_path, closes):
    from hedge_fund import run
    from hedge_fund.tui import keys

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(keys, "ENV_PATH", tmp_path / "saved.env")
    monkeypatch.setattr(run, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(run, "FDClient", lambda: FakeDataClient(closes))
    monkeypatch.setattr(run, "CachedDataClient", lambda raw: raw)
    monkeypatch.setattr(run, "Fund", _fake_fund)
    return run


def test_paper_flag_writes_receipt_and_next_run_seeds(tmp_path, monkeypatch, capsys):
    """Acceptance: --paper writes a CycleRecord; the next process seeds from it."""
    run = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0})
    mandate = _mandate(tmp_path / "fund.yaml")
    output = tmp_path / "record.json"
    argv = [
        "aihf", str(mandate), "--tickers", "AAPL", "--paper",
        "--date", "2024-06-03", "--out", str(output),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    run.main()
    first = CycleRecord.model_validate_json(output.read_text())
    printed = CycleRecord.model_validate_json(capsys.readouterr().out)
    assert printed == first
    assert first.positions == {"AAPL": 500}
    assert first.cash == pytest.approx(0.0)
    assert first.nav == pytest.approx(100_000.0)
    receipts = list(tmp_path.glob("paper-desk-run-*.json"))
    assert len(receipts) == 1

    run.main()
    second = CycleRecord.model_validate_json(output.read_text())
    err = capsys.readouterr().err
    assert "carrying book from 2024-06-03" in err
    assert "paper venue" in err
    assert second.cash_before == pytest.approx(first.cash)
    assert second.equity_before == pytest.approx(first.nav)
    assert second.positions == first.positions
    assert second.orders == []
    # Same-second reruns may overwrite the stamp; the newest receipt is the book.
    assert latest_run_receipt("paper-desk", tmp_path) is not None


def test_default_live_clock_path_is_paper(tmp_path, monkeypatch, capsys):
    """One cycle without --backtest is the paper path (live clock + PaperBroker)."""
    run = _patch_cli(monkeypatch, tmp_path, {"AAPL": 200.0})
    seen: list[object] = []
    real = run.broker_for_run

    def wrapped(*args, **kwargs):
        broker, prior = real(*args, **kwargs)
        seen.append(broker)
        return broker, prior

    monkeypatch.setattr(run, "broker_for_run", wrapped)
    mandate = _mandate(tmp_path / "fund.yaml")
    monkeypatch.setattr(
        sys, "argv",
        ["aihf", str(mandate), "--tickers", "AAPL", "--date", "2024-06-03"],
    )
    run.main()
    assert len(seen) == 1
    assert isinstance(seen[0], PaperBroker)
    assert seen[0].venue == "paper"
    assert "paper venue" in capsys.readouterr().err


def test_paper_and_backtest_are_exclusive(tmp_path, monkeypatch):
    from hedge_fund import run

    mandate = _mandate(tmp_path / "fund.yaml")
    monkeypatch.setattr(
        sys, "argv",
        ["aihf", str(mandate), "--tickers", "AAPL", "--paper", "--backtest"],
    )
    with pytest.raises(SystemExit):
        run.main()


def test_backtest_still_constructs_sim_broker(monkeypatch):
    constructed: list[object] = []
    real = SimBroker

    def wrap(cash, positions=None):
        broker = real(cash=cash, positions=positions)
        constructed.append(broker)
        return broker

    monkeypatch.setattr("hedge_fund.backtesting.fund.SimBroker", wrap)
    spec = FundSpec(
        name="bt",
        strategies=[{"name": "solo", "models": [{"name": "a"}]}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0,
        rebalance="weekly",
        benchmark="SPY",
    )
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    series = {
        "SPY": {"2024-06-07": 100.0, "2024-06-14": 102.0},
        "AAPL": {"2024-06-07": 200.0, "2024-06-14": 210.0},
    }

    class SeriesClient:
        def get_prices(self, ticker, start_date, end_date, **kwargs):
            return [
                Price(open=c, close=c, high=c, low=c, volume=1000,
                      time=f"{day}T00:00:00Z")
                for day, c in sorted(series.get(ticker, {}).items())
                if start_date <= day <= end_date
            ]

    result = backtest_fund(fund, "2024-06-03", "2024-06-14",
                           SeriesClient(), ["AAPL"])
    assert constructed
    assert all(isinstance(b, SimBroker) for b in constructed)
    assert all(getattr(b, "venue", "sim") == "sim" for b in constructed)
    assert result.records[0].cash_before == pytest.approx(100_000.0)
