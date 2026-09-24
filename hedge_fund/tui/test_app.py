"""Jev selection, isolated credentials, and rendering in the existing TUI."""

import asyncio
import io
import json
import os
import stat
from unittest.mock import Mock

import pytest
import requests
import yaml
from rich.console import Console
from textual.widgets import ContentSwitcher, Input, OptionList, SelectionList, Static

from hedge_fund.fund import custom_strategy, FundSpec, load_spec
from hedge_fund.llm import PROVIDER_ENV_VARS
from hedge_fund.llm.contract import normalize_jev_response
from hedge_fund.llm.test_contract import _response
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.tui import app as ui
from hedge_fund.tui import keys


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = tmp_path / "user" / ".env"
    saved.parent.mkdir()
    mandates = tmp_path / "mandates"
    mandates.mkdir()
    monkeypatch.setattr(ui, "FUNDS_DIR", mandates)
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
        spec={"schema_version": 2, "name": "test", "strategies": [{"name": "value", "models": [{"name": "buffett"}], "blend": {"mode": "long_only"}}], "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1}},
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
            # Provider names are group headers; model rows show label and id.
            assert "Jev" in _render(picker.get_option_at_index(index).prompt)
            assert "jev-1.13.0" in _render(picker.get_option_at_index(index).prompt)
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
    assert "No written thesis generated." in detail
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


def test_abstention_overrides_stored_direction():
    signal = Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=0, reasoning="abstained: TypeSafe returned HTTP 401", metadata={"abstained": True, "signal": "bullish"})
    text = _render(ui._signal_detail(_record(signal), 0, 0))
    assert "ABSTAIN" in text and "HTTP 401" in text
    assert "Jev native answer confidence" not in text


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


def _spec(names=("buffett", "druckenmiller"), name="test"):
    return FundSpec(schema_version=2, name=name, strategies=[custom_strategy(list(names))],
                       risk={"max_position_pct": 0.25, "max_gross_exposure": 1})


def test_mixed_description_identifies_short_analysts():
    description = ui.strategy_description(_spec().strategies[0])
    assert "Short ideas must be supported by Druckenmiller." in description
    assert "Long-only analysts contribute ownership views." in description
    assert "Long-only" in ui.BuilderScreen._agent_prompt("buffett", ui.ALPHA_MODEL_REGISTRY["buffett"]).plain


@pytest.mark.parametrize("names,mode", [
    (["buffett"], "long_only"),
    (["buffett", "druckenmiller"], "long_short"),
    (["druckenmiller"], "long_short"),
])
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_builder_derives_rules_and_back_navigation_does_not_duplicate(names, mode, size):
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(ui.BuilderScreen())
            screen = app.screen
            screen.query_one("#name-input", Input).value = "new-fund"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            agents = screen.query_one("#agent-list", SelectionList)
            for name in names:
                agents.select(name)
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-capital"
            await pilot.press("escape")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-agents"
            assert set(agents.selected) == set(names)
            await pilot.press("enter")
            await pilot.press("enter", "enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            saved = load_spec(ui.FUNDS_DIR / "new-fund.yaml")
            assert saved.schema_version == 2
            assert len(saved.strategies) == 1
            assert saved.strategies[0].blend.mode == mode
            assert not screen.query_one("#done-menu", OptionList).get_option("go-run").disabled
            await pilot.wait_for_scheduled_animations()
            await pilot.pause()
            assert screen.query_one("#done-menu", OptionList).region.intersection(screen.region).height > 0
            text = _render(screen.query_one("#done-summary", Static).content)
            assert ui.MODE_LABELS[mode] in text
    asyncio.run(scenario())


def test_builder_existing_name_and_save_race_never_overwrite():
    original = "name: old-user-fund\n"
    path = ui.FUNDS_DIR / "existing.yaml"
    path.write_text(original)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.BuilderScreen())
            screen = app.screen
            screen.query_one("#name-input", Input).value = "existing"
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            assert path.read_text() == original
            screen.query_one("#name-input", Input).value = "save-race"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-cadence"
            # Simulate another process saving the chosen name after validation.
            competing_path = ui.FUNDS_DIR / "save-race.yaml"
            competing_path.write_text(original)
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            assert competing_path.read_text() == original
    asyncio.run(scenario())


def test_both_pickers_disable_only_invalid_configurations():
    files = {"old.yaml": "name: old\n", "broken.yaml": "[oops",
             "mixed.yaml": yaml.safe_dump(_spec().model_dump()),
             "valid.yaml": yaml.safe_dump(_spec(["pead"], "ready").model_dump())}
    for name, content in files.items():
        (ui.FUNDS_DIR / name).write_text(content)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.FundSelectScreen())
            menu = app.screen.query_one("#select-menu", OptionList)
            assert menu.option_count == 4
            prompts = [_render(menu.get_option_at_index(i).prompt) for i in range(4)]
            assert any("old.yaml" in p and "older format" in p for p in prompts)
            assert sum(menu.get_option_at_index(i).disabled for i in range(4)) == 2
            await pilot.press("enter")
            assert isinstance(app.screen, ui.RunScreen)
            assert not app.screen.query_one("#run-tickers", Input).disabled
            await pilot.press("escape")
            await app.push_screen(ui.BacktestScreen())
            menu = app.screen.query_one("#fund-list", OptionList)
            assert menu.option_count == 4
            assert sum(menu.get_option_at_index(i).disabled for i in range(4)) == 2
    asyncio.run(scenario())
    assert {p.name: p.read_text() for p in ui.FUNDS_DIR.glob("*.yaml")} == files


def test_all_invalid_funds_do_not_crash_home_picker():
    (ui.FUNDS_DIR / "old.yaml").write_text("name: old\n")
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test() as pilot:
            await app.push_screen(ui.FundSelectScreen())
            assert "Saved funds are unavailable" in _render(app.screen.query_one("#detail-body", Static).content)
    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_all_modes_enable_run_and_backtest(mode, size):
    spec = _spec()
    spec.strategies[0].blend.mode = mode
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(ui.RunScreen(spec))
            assert not app.screen.query_one("#run-tickers", Input).disabled
            assert app.screen.check_action("backtest", ())
            await pilot.press("ctrl+b")
            assert isinstance(app.screen, ui.BacktestScreen)
            assert app.screen.query_one("#bt-panes", ContentSwitcher).current == "bt-dates"
            assert not app.screen.query_one("#bt-tickers", Input).disabled
    asyncio.run(scenario())


@pytest.mark.parametrize("newest_version", [None, 2])
def test_latest_backtest_sets_headline_regardless_of_version(newest_version):
    spec = _spec(["pead"])
    receipt = {"start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5,
                           "sharpe_ratio": 2, "max_drawdown_pct": .1,
                           "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    if newest_version is None:
        receipt["schema_version"] = 2
    older = ui.FUNDS_DIR / "test-backtest-older.json"
    older.write_text(json.dumps(receipt))
    os.utime(older, (1000, 1000))
    original = older.read_bytes()
    older_summary = ui._summarize(older, 1000)
    assert ui._last_score("test") == (.5, .4, "SPY")
    assert "LATEST BACKTEST" in _render(ui._fund_detail(spec, [older_summary]))

    receipt.pop("schema_version", None)
    if newest_version is not None:
        receipt["schema_version"] = newest_version
    receipt["metrics"].update(total_return_pct=.3, excess_return_pct=.2)
    newer = ui.FUNDS_DIR / "test-backtest-newer.json"
    newer.write_text(json.dumps(receipt))
    os.utime(newer, (2000, 2000))
    newer_summary = ui._summarize(newer, 2000)
    assert ui._last_score("test") == (.3, .2, "SPY")
    detail = _render(ui._fund_detail(spec, [newer_summary, older_summary]))
    headline = detail.split("RUNS & BACKTESTS")[0]
    assert "LATEST BACKTEST" in headline and "30.0%" in headline
    assert older.read_bytes() == original



def test_portfolio_report_explains_rounding_scaling_and_flat_strategies():
    record = _record(_signal())
    record.spec.strategies[0].blend.mode = "dollar_neutral"
    record.equity_before = record.nav = 10_000
    record.final_weights = {"A": .5, "B": -.5}
    record.positions = {"A": 16, "B": -7}
    record.marks = {"A": 300, "B": 700}
    record.risk_scale_factor = .5
    text = _render(ui._portfolio_detail(record))
    assert "Target net $+0.00" in text
    assert "Actual net $-100.00" in text
    assert "Difference $-100.00" in text
    assert "scaled all strategy targets to 50.0%" in text
    assert "Whole-share holdings can differ" in text
    record.positions = {}
    record.final_weights = {"A": 0, "B": 0}
    record.strategies[0].flat_reason = "missing_short_side"
    text = _render(ui._portfolio_detail(record))
    assert "no eligible shorts to balance the longs" in text
    assert "Allocated capital remains unused" in text
    assert "flat — no positions" in text
