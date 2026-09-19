"""Observability — events, heartbeat, webhook. Temp dirs + mocked HTTP."""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import Mock

import pytest

from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.client import FDClientError
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.models import Signal
from hedge_fund.observability import (
    CYCLE_END,
    CYCLE_ERROR,
    CYCLE_START,
    CycleObserver,
    observe_cycle,
)
from hedge_fund.observability.observe import (
    DEFAULT_WEBHOOK_TIMEOUT,
    HEARTBEAT_ENV,
    HEARTBEAT_PATH_ENV,
    WEBHOOK_TIMEOUT_ENV,
    WEBHOOK_URL_ENV,
    safe_error_message,
    universe_summary,
)
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.pipeline.run_cycle import run_cycle


class FakeDataClient:
    def __init__(self, closes, price_error=None):
        self._closes = closes
        self._price_error = price_error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        if self._price_error is not None:
            raise self._price_error
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


def _fund(name="obs-desk"):
    spec = FundSpec(
        name=name,
        strategies=[{"name": "solo", "models": [{"name": "pead"}]}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0,
    )
    return Fund(spec, models={"solo": [FakeAnalyst("pead", views={"AAPL": 1.0})]})


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _clear_obs_env(monkeypatch):
    for name in (
        "HEDGE_FUND_EVENTS_PATH",
        HEARTBEAT_PATH_ENV,
        HEARTBEAT_ENV,
        WEBHOOK_URL_ENV,
        WEBHOOK_TIMEOUT_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def test_universe_summary_caps_long_lists():
    names = [f"T{i:03d}" for i in range(40)]
    summary = universe_summary(names)
    assert summary["n"] == 40
    assert len(summary["tickers"]) == 32
    assert summary["truncated"] is True


def test_safe_error_message_redacts_secret_shaped_values():
    text = safe_error_message(ValueError("api_key=sk-live-not-a-real-key token=abc"))
    assert "sk-live-not-a-real-key" not in text
    assert "abc" not in text
    assert "[redacted]" in text


def test_successful_cycle_writes_jsonl_and_heartbeat(tmp_path, caplog):
    events = tmp_path / "events.jsonl"
    heartbeat = tmp_path / "heartbeat.json"
    observer = CycleObserver(events_path=events, heartbeat_path=heartbeat)
    caplog.set_level(logging.INFO)

    record = observe_cycle(
        _fund(), "2024-06-03", SimBroker(cash=100_000.0),
        FakeDataClient({"AAPL": 200.0}), ["AAPL"], observer=observer,
    )

    assert isinstance(record, CycleRecord)
    lines = _read_jsonl(events)
    assert [row["event"] for row in lines] == [CYCLE_START, CYCLE_END]
    assert lines[0]["status"] == "running"
    assert lines[0]["fund"] == "obs-desk"
    assert lines[0]["as_of"] == "2024-06-03"
    assert lines[0]["universe"] == {"n": 1, "tickers": ["AAPL"], "truncated": False}
    assert lines[1]["status"] == "ok"
    assert lines[1]["nav"] == pytest.approx(record.nav)
    assert "cycle_start" in caplog.text
    assert "cycle_end" in caplog.text

    beat = json.loads(heartbeat.read_text())
    assert beat["status"] == "ok"
    assert beat["fund"] == "obs-desk"
    assert beat["as_of"] == "2024-06-03"
    assert beat["last_as_of"] == "2024-06-03"
    assert beat["last_success_at"]
    assert beat["last_failure_at"] is None
    assert beat["nav"] == pytest.approx(record.nav)


def test_failed_cycle_posts_webhook_and_keeps_raising(tmp_path, monkeypatch):
    events = tmp_path / "events.jsonl"
    heartbeat = tmp_path / "heartbeat.json"
    posts = []

    def fake_post(url, **kwargs):
        posts.append({"url": url, **kwargs})
        response = Mock()
        response.raise_for_status = Mock()
        return response

    monkeypatch.setattr("hedge_fund.observability.observe.requests.post", fake_post)
    observer = CycleObserver(
        events_path=events,
        heartbeat_path=heartbeat,
        webhook_url="https://example.invalid/hook",
        webhook_timeout=2.5,
    )
    error = FDClientError("unauthorized", status_code=401, path="/prices/")

    with pytest.raises(FDClientError) as exc_info:
        observe_cycle(
            _fund(), "2024-06-03", SimBroker(cash=100_000.0),
            FakeDataClient({}, price_error=error), ["AAPL"], observer=observer,
        )

    assert exc_info.value is error
    lines = _read_jsonl(events)
    assert [row["event"] for row in lines] == [CYCLE_START, CYCLE_ERROR]
    assert lines[1]["error_type"] == "FDClientError"
    assert "unauthorized" in lines[1]["error_message"]
    dumped = json.dumps(lines[1]).lower()
    assert "sk-" not in dumped

    beat = json.loads(heartbeat.read_text())
    assert beat["status"] == "error"
    assert beat["error_type"] == "FDClientError"
    assert beat["last_failure_at"]
    assert beat["last_success_at"] is None

    assert len(posts) == 1
    assert posts[0]["url"] == "https://example.invalid/hook"
    assert posts[0]["timeout"] == 2.5
    body = posts[0]["json"]
    assert body["event"] == CYCLE_ERROR
    assert body["fund"] == "obs-desk"
    assert body["as_of"] == "2024-06-03"
    assert body["status"] == "error"
    assert body["error_type"] == "FDClientError"
    assert body["universe"]["tickers"] == ["AAPL"]


def test_webhook_failure_does_not_mask_cycle_error(tmp_path, monkeypatch, caplog):
    def fake_post(url, **kwargs):
        raise ConnectionError("webhook host down")

    monkeypatch.setattr("hedge_fund.observability.observe.requests.post", fake_post)
    observer = CycleObserver(
        events_path=tmp_path / "events.jsonl",
        heartbeat_path=tmp_path / "heartbeat.json",
        webhook_url="https://example.invalid/hook",
    )
    caplog.set_level(logging.ERROR)
    original = FDClientError("quota exhausted", status_code=429, path="/prices/")

    with pytest.raises(FDClientError) as exc_info:
        observe_cycle(
            _fund(), "2024-06-03", SimBroker(cash=100_000.0),
            FakeDataClient({}, price_error=original), ["AAPL"], observer=observer,
        )

    assert exc_info.value is original
    assert "cycle failure webhook failed" in caplog.text


def test_no_webhook_on_success(tmp_path, monkeypatch):
    posts = []
    monkeypatch.setattr(
        "hedge_fund.observability.observe.requests.post",
        lambda url, **kwargs: posts.append(url),
    )
    observer = CycleObserver(
        heartbeat_path=tmp_path / "heartbeat.json",
        webhook_url="https://example.invalid/hook",
    )
    observe_cycle(
        _fund(), "2024-06-03", SimBroker(cash=100_000.0),
        FakeDataClient({"AAPL": 200.0}), ["AAPL"], observer=observer,
    )
    assert posts == []


def test_heartbeat_survives_success_then_failure(tmp_path):
    heartbeat = tmp_path / "heartbeat.json"
    observer = CycleObserver(heartbeat_path=heartbeat)
    observe_cycle(
        _fund(), "2024-06-03", SimBroker(cash=100_000.0),
        FakeDataClient({"AAPL": 200.0}), ["AAPL"], observer=observer,
    )
    with pytest.raises(FDClientError):
        observe_cycle(
            _fund(), "2024-06-04", SimBroker(cash=100_000.0),
            FakeDataClient({}, price_error=FDClientError("down", status_code=500)),
            ["AAPL"], observer=observer,
        )
    beat = json.loads(heartbeat.read_text())
    assert beat["status"] == "error"
    assert beat["last_success_at"]
    assert beat["last_failure_at"]
    assert beat["as_of"] == "2024-06-04"


def test_from_env_honors_paths_and_webhook(tmp_path, monkeypatch):
    _clear_obs_env(monkeypatch)
    events = tmp_path / "e.jsonl"
    heartbeat = tmp_path / "h.json"
    monkeypatch.setenv("HEDGE_FUND_EVENTS_PATH", str(events))
    monkeypatch.setenv(HEARTBEAT_PATH_ENV, str(heartbeat))
    monkeypatch.setenv(WEBHOOK_URL_ENV, "https://example.invalid/hook")
    monkeypatch.setenv(WEBHOOK_TIMEOUT_ENV, "3")
    observer = CycleObserver.from_env()
    assert observer.events_path == events
    assert observer.heartbeat_path == heartbeat
    assert observer.webhook_url == "https://example.invalid/hook"
    assert observer.webhook_timeout == 3.0


def test_heartbeat_env_flag_uses_default_path(tmp_path, monkeypatch):
    _clear_obs_env(monkeypatch)
    monkeypatch.setenv(HEARTBEAT_ENV, "1")
    monkeypatch.setattr(
        "hedge_fund.observability.observe.default_heartbeat_path",
        lambda: tmp_path / "default-heartbeat.json",
    )
    observer = CycleObserver.from_env()
    assert observer.heartbeat_path == tmp_path / "default-heartbeat.json"


def test_cli_overrides_env_paths(tmp_path, monkeypatch):
    _clear_obs_env(monkeypatch)
    monkeypatch.setenv("HEDGE_FUND_EVENTS_PATH", str(tmp_path / "env.jsonl"))
    monkeypatch.setenv(HEARTBEAT_PATH_ENV, str(tmp_path / "env-hb.json"))
    observer = CycleObserver.from_env(
        events_path=str(tmp_path / "cli.jsonl"),
        heartbeat_path="default",
    )
    assert observer.events_path == tmp_path / "cli.jsonl"
    from hedge_fund.paths import default_heartbeat_path
    assert observer.heartbeat_path == default_heartbeat_path()


def test_invalid_webhook_timeout_fails_loud(monkeypatch):
    _clear_obs_env(monkeypatch)
    monkeypatch.setenv(WEBHOOK_TIMEOUT_ENV, "nope")
    with pytest.raises(ValueError, match=WEBHOOK_TIMEOUT_ENV):
        CycleObserver.from_env()


def test_observe_cycle_from_env_without_files_still_logs(tmp_path, monkeypatch, caplog):
    _clear_obs_env(monkeypatch)
    caplog.set_level(logging.INFO)
    record = observe_cycle(
        _fund(), "2024-06-03", SimBroker(cash=100_000.0),
        FakeDataClient({"AAPL": 200.0}), ["AAPL"],
    )
    assert record.fund == "obs-desk"
    assert "cycle_start" in caplog.text


def test_injected_run_cycle_fn_is_used(tmp_path):
    seen = []

    def fake_cycle(fund, as_of, broker, data_client, universe):
        seen.append((as_of, list(universe)))
        return run_cycle(fund, as_of, broker, data_client, universe)

    observer = CycleObserver(events_path=tmp_path / "e.jsonl")
    observe_cycle(
        _fund(), "2024-06-03", SimBroker(cash=100_000.0),
        FakeDataClient({"AAPL": 200.0}), ["AAPL"],
        observer=observer, run_cycle_fn=fake_cycle,
    )
    assert seen == [("2024-06-03", ["AAPL"])]


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


def _patch_cli(monkeypatch, tmp_path, client):
    from hedge_fund import run
    from hedge_fund.tui import keys

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(keys, "ENV_PATH", tmp_path / "saved.env")
    monkeypatch.setattr(run, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(run, "FDClient", lambda: client)
    monkeypatch.setattr(run, "CachedDataClient", lambda raw: raw)
    monkeypatch.setattr(run, "Fund", _fake_fund)
    return run


def test_cli_heartbeat_flag_without_live_apis(tmp_path, monkeypatch, capsys):
    """Acceptance: CLI can enable a heartbeat with mocked data, no live APIs."""
    _clear_obs_env(monkeypatch)
    run = _patch_cli(monkeypatch, tmp_path, FakeDataClient({"AAPL": 200.0}))
    heartbeat = tmp_path / "hb.json"
    events = tmp_path / "events.jsonl"
    monkeypatch.setattr(
        sys, "argv",
        [
            "aihf", str(_mandate(tmp_path / "fund.yaml")),
            "--tickers", "AAPL", "--paper", "--date", "2024-06-03",
            "--heartbeat", str(heartbeat), "--events", str(events),
        ],
    )
    run.main()
    printed = CycleRecord.model_validate_json(capsys.readouterr().out)
    beat = json.loads(heartbeat.read_text())
    assert beat["status"] == "ok"
    assert beat["as_of"] == "2024-06-03"
    assert beat["nav"] == pytest.approx(printed.nav)
    assert [row["event"] for row in _read_jsonl(events)] == [CYCLE_START, CYCLE_END]


def test_cli_env_heartbeat_without_flag(tmp_path, monkeypatch, capsys):
    _clear_obs_env(monkeypatch)
    heartbeat = tmp_path / "from-env.json"
    monkeypatch.setenv(HEARTBEAT_PATH_ENV, str(heartbeat))
    run = _patch_cli(monkeypatch, tmp_path, FakeDataClient({"AAPL": 200.0}))
    monkeypatch.setattr(
        sys, "argv",
        [
            "aihf", str(_mandate(tmp_path / "fund.yaml")),
            "--tickers", "AAPL", "--date", "2024-06-03",
        ],
    )
    run.main()
    capsys.readouterr()
    beat = json.loads(heartbeat.read_text())
    assert beat["status"] == "ok"
    assert beat["fund"] == "paper-desk"


def test_cli_failed_cycle_posts_webhook(tmp_path, monkeypatch, capsys):
    """Acceptance: a failed paper cycle POSTs a webhook payload (mocked HTTP)."""
    _clear_obs_env(monkeypatch)
    posts = []

    def fake_post(url, **kwargs):
        posts.append({"url": url, **kwargs})
        response = Mock()
        response.raise_for_status = Mock()
        return response

    monkeypatch.setattr("hedge_fund.observability.observe.requests.post", fake_post)
    monkeypatch.setenv(WEBHOOK_URL_ENV, "https://example.invalid/hook")
    client = FakeDataClient(
        {},
        price_error=FDClientError("unauthorized", status_code=401, path="/prices/"),
    )
    run = _patch_cli(monkeypatch, tmp_path, client)
    heartbeat = tmp_path / "hb.json"
    monkeypatch.setattr(
        sys, "argv",
        [
            "aihf", str(_mandate(tmp_path / "fund.yaml")),
            "--tickers", "AAPL", "--date", "2024-06-03",
            "--heartbeat", str(heartbeat),
        ],
    )
    with pytest.raises(FDClientError):
        run.main()
    capsys.readouterr()
    assert len(posts) == 1
    assert posts[0]["url"] == "https://example.invalid/hook"
    assert posts[0]["timeout"] == DEFAULT_WEBHOOK_TIMEOUT
    body = posts[0]["json"]
    assert body["event"] == CYCLE_ERROR
    assert body["error_type"] == "FDClientError"
    assert json.loads(heartbeat.read_text())["status"] == "error"
