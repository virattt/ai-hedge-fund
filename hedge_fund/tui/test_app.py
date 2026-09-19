"""Jev selection, isolated credentials, and rendering in the existing TUI."""

import asyncio
import io
import os
import stat
from unittest.mock import Mock

import pytest
import requests
from rich.console import Console
from textual.widgets import Input, OptionList

from hedge_fund.llm import PROVIDER_ENV_VARS
from hedge_fund.llm.contract import normalize_jev_response
from hedge_fund.llm.test_contract import _response
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import CycleRecord, DroppedOutput
from hedge_fund.tui import app as ui
from hedge_fund.tui import keys


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = tmp_path / "user" / ".env"
    saved.parent.mkdir()
    mandates = tmp_path / "mandates"
    mandates.mkdir()
    monkeypatch.setattr(keys, "ENV_PATH", saved)
    monkeypatch.setattr(ui, "ENV_PATH", saved)
    monkeypatch.setattr(ui, "ensure_mandates_dir", lambda: mandates)
    for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY", "FINANCIAL_DATASETS_API_KEY", "HEDGE_FUND_LLM_MODEL", "UNRELATED_KEY"):
        # Track even initially absent keys, since dotenv and the UI set them
        # directly rather than through monkeypatch.
        monkeypatch.setenv(variable, "")
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(requests.sessions.Session, "request", Mock(side_effect=AssertionError("No live HTTP in TUI tests")))
    return saved


def _render(renderable):
    output = io.StringIO()
    Console(file=output, width=140, color_system=None).print(renderable)
    return output.getvalue()


def _signal(direction="bullish", strength=3.2, cached=False):
    payload, metadata = normalize_jev_response(_response(direction, bullish=strength, bearish=strength))
    sign = {"bullish": 1, "bearish": -1, "neutral": 0}[direction]
    return Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=sign * payload["confidence"] / 100, reasoning=payload["reasoning"], metadata={"signal": direction, "confidence": payload["confidence"], "abstained": False, "cached": cached, "provider_metadata": {"jev": metadata}})


def _record(signal):
    return CycleRecord(
        fund="test",
        as_of=signal.date,
        spec={"name": "test", "strategies": [{"name": "value", "models": [{"name": "buffett"}]}], "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1}},
        universe=[signal.ticker],
        marks={signal.ticker: 100},
        skipped=[],
        strategies=[{"name": "value", "slice": 1, "signals": [signal], "convictions": {}, "weights": {}}],
        target_weights={},
        clamps=[],
        final_weights={},
        equity_before=100000,
        cash_before=100000,
        orders=[],
        fills=[],
        positions={},
        cash=100000,
        nav=100000,
    )


@pytest.mark.parametrize("save", [True, False])
def test_picker_and_masked_key_save_or_cancel(save, isolated_configuration):
    saved = isolated_configuration
    saved.write_text("# keep this comment\nUNRELATED_KEY=untouched\n")
    original = saved.read_text()

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.press("m")
            picker = app.screen.query_one("#picker-list", OptionList)
            index = picker.get_option_index("jev-1.13.0")
            assert not picker.get_option_at_index(index).disabled
            assert "Jev" in _render(picker.get_option_at_index(index).prompt)
            picker.highlighted = index
            await pilot.press("enter")
            assert os.environ["HEDGE_FUND_LLM_MODEL"] == "jev-1.13.0"
            await pilot.press("k")
            entry = app.screen.query_one("#key-input", Input)
            assert entry.password is True
            assert entry.placeholder == "TYPESAFE_API_KEY"
            entry.value = "fixture-typesafe-secret-value"
            await pilot.press("enter" if save else "escape")
            assert isinstance(app.screen, ui.HomeScreen)
            if save:
                assert os.environ["TYPESAFE_API_KEY"] == entry.value
                assert saved.read_text() == original + f"TYPESAFE_API_KEY={entry.value}\n"
                assert stat.S_IMODE(saved.stat().st_mode) == 0o600
            else:
                assert "TYPESAFE_API_KEY" not in os.environ
                assert saved.read_text() == original

    asyncio.run(scenario())


def test_missing_key_gate_save_resumes_and_cancel_does_not(monkeypatch, isolated_configuration):
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "fixture-fd-key")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")

    async def scenario():
        app = ui.HedgeFundApp()
        resumed = Mock()
        async with app.run_test(size=(100, 35)) as pilot:
            assert ui._demand_run_keys(app, resumed) is False
            await pilot.pause()
            assert isinstance(app.screen, ui.KeyPromptScreen)
            await pilot.press("escape")
            resumed.assert_not_called()
            assert not isolated_configuration.exists()
            assert ui._demand_run_keys(app, resumed) is False
            await pilot.pause()
            app.screen.query_one("#key-input", Input).value = "fixture-typesafe-key"
            await pilot.press("enter")
            resumed.assert_called_once()
            assert ui._demand_run_keys(app, resumed) is True

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "exported,local,expected",
    [
        ("shell-key", "local-key", "shell-key"),
        (None, "local-key", "local-key"),
        (None, None, "saved-key"),
    ],
)
def test_credential_precedence(exported, local, expected, isolated_configuration, tmp_path, monkeypatch):
    isolated_configuration.write_text("TYPESAFE_API_KEY=saved-key\n")
    if local:
        (tmp_path / ".env").write_text(f"TYPESAFE_API_KEY={local}\n")
    if exported:
        monkeypatch.setenv("TYPESAFE_API_KEY", exported)
    keys.apply_credentials()
    assert os.environ["TYPESAFE_API_KEY"] == expected


@pytest.mark.parametrize("direction,strength", [("bullish", 3.2), ("bearish", 1.6), ("neutral", 4), ("bullish", 0), ("bearish", 0)])
def test_jev_results_show_stored_direction_and_separate_confidence(direction, strength):
    signal = _signal(direction, strength)
    detail = _render(ui._signal_detail(_record(signal), 0, 0))
    assert direction.upper() in detail
    assert "investment conviction" in detail
    assert "No written thesis" in detail.replace("\n", " ")
    assert "Jev answer-option probabilities" in detail
    assert "not investment returns" in detail
    assert "Jev native answer confidence" in detail
    assert "Direction: 60.0%" in detail
    assert "Bullish strength: 40.0%" in detail
    assert "Bearish strength: 40.0%" in detail
    assert f"{direction.capitalize()} 80.0%" in detail
    cached = signal.model_copy(deep=True)
    cached.metadata["cached"] = True
    assert _render(ui._signal_detail(_record(cached), 0, 0)) == detail
    desk = ui._Desk("Buffett")
    desk.begin("TEST")
    assert ui._live_verdict(desk).plain == "thinking"
    assert ui._live_thesis(desk).plain == ""
    desk.settle(signal)
    assert direction.upper() in ui._live_verdict(desk).plain
    assert ui._live_thesis(desk).plain == signal.reasoning
    verdict = ui._verdict(signal)
    nav = ui._report_nav(_record(signal))
    option = next(option for option in nav if option.id == "sig:0:0")
    assert verdict[0] in _render(option.prompt)


def test_home_menu_labels_the_paper_path(isolated_configuration):
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            picker = app.screen.query_one("#home-menu", OptionList)
            text = _render(picker.get_option_at_index(0).prompt)
            assert "paper-trade" in text
            assert picker.get_option_at_index(0).id == "run"
            _ = pilot

    asyncio.run(scenario())


def test_last_run_book_reads_newest_cycle_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "FUNDS_DIR", tmp_path)
    assert ui._last_run_book("alpha-one") is None
    receipt = tmp_path / "alpha-one-run-2024-06-03-120000.json"
    receipt.write_text(_record(_signal()).model_dump_json())
    # A backtest sitting next to it must not win — only CycleRecords seed.
    backtest = tmp_path / "alpha-one-backtest-2024-06-04-120000.json"
    backtest.write_text('{"metrics": {"total_return_pct": 0.1, '
                        '"annualized_return_pct": 0.1, "sharpe_ratio": 0, '
                        '"max_drawdown_pct": 0, "benchmark_return_pct": 0, '
                        '"excess_return_pct": 0, "n_cycles": 1}, '
                        '"universe": ["AAPL"], "start": "2024-01-01", '
                        '"end": "2024-06-04"}')
    os.utime(receipt, (1_000_000, 1_000_000))
    os.utime(backtest, (2_000_000, 2_000_000))
    assert ui._last_run_book("alpha-one") == ("2025-01-15", 100000)


def test_abstention_overrides_stored_direction():
    signal = Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=0, reasoning="abstained: TypeSafe returned HTTP 401", metadata={"abstained": True, "signal": "bullish"})
    text = _render(ui._signal_detail(_record(signal), 0, 0))
    assert "ABSTAIN" in text and "HTTP 401" in text
    assert "Jev native answer confidence" not in text


def test_dropped_views_appear_in_the_report():
    record = _record(_signal()).model_copy(update={"dropped": [
        DroppedOutput(ticker="TEST", model="buffett", strategy="value",
                      reason="insufficient data: only 2 filed periods"),
    ]})
    nav = ui._report_nav(record)
    assert any(option.id == "sec:dropped" for option in nav)
    text = _render(ui._dropped_detail(record))
    assert "DROPPED VIEWS" in text
    assert "TEST" in text
    assert "buffett" in text
    assert "insufficient data" in text


def test_chat_rendering_and_quantitative_fallback_are_preserved():
    chat = Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=0.8, reasoning="A durable business.", metadata={"signal": "bullish", "confidence": 80.0})
    text = _render(ui._signal_detail(_record(chat), 0, 0))
    assert "80% confidence" in text and "conviction +0.80" in text
    assert "A durable business." in text and "Jev" not in text
    desk = ui._Desk("Buffett")
    desk.begin("TEST")
    desk.feed('{"signal":"bullish","confidence":80,"reasoning":"A durable business."}')
    assert "BULLISH" in ui._live_verdict(desk).plain
    assert "A durable business." in ui._live_thesis(desk).plain
    for value, direction in [(0.5, "BULLISH"), (-0.5, "BEARISH"), (0, "NEUTRAL")]:
        quant = Signal(model_name="pead", ticker="TEST", date="2025-01-15", value=value)
        assert ui._verdict(quant)[1] == direction
        desk.settle(quant)
        assert ui._live_thesis(desk).plain == ""
