"""Jev selection, isolated credentials, and rendering in the existing TUI."""

import asyncio
import io
import json
import os
import stat
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
import requests
import yaml
from rich.console import Console
from textual.widgets import ContentSwitcher, Input, OptionList, SelectionList, Static

from hedge_fund.brokers.models import Fill
from hedge_fund.fund import custom_strategy, FundSpec, load_spec
from hedge_fund.llm import PROVIDER_ENV_VARS
from hedge_fund.llm.contract import normalize_jev_response
from hedge_fund.llm.test_contract import _response
from hedge_fund.models import Signal
from hedge_fund.paper import Ledger, PID_FILE
from hedge_fund.pipeline.models import CycleRecord, DecisionRecord
from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.tui import app as ui
from hedge_fund.tui import keys


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = tmp_path / "user" / ".env"
    saved.parent.mkdir()
    mandates = tmp_path / "mandates"
    mandates.mkdir()
    monkeypatch.setattr(ui, "MANDATES_DIR", mandates)
    monkeypatch.setattr(ui, "PAPER_DIR", tmp_path / "paper")
    monkeypatch.setattr(ui, "RESEARCH_DIR", tmp_path / "research")
    (tmp_path / "research").mkdir()
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
    # soft_wrap: long header lines stay on one line, so assertions can match
    # phrases without guessing where a wrap would land.
    Console(file=output, width=140, color_system=None).print(renderable, soft_wrap=True)
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


def _session(session, *, executed=None, decision=None, nav=100000, positions=None, marks=None, prev_hash=None):
    record = SessionRecord(
        fund="test", session=session, universe=["TEST"], nav=nav, cash=nav - sum((positions or {}).get(t, 0) * (marks or {}).get(t, 0) for t in (positions or {})),
        positions=positions or {}, marks=marks or {}, benchmark="SPY", benchmark_close=100.0,
        rebalance=decision is not None, executed=executed, decision=decision,
        prev_hash=prev_hash, code_version="test", mandate_hash="m",
    )
    record.hash = record.compute_hash()
    return record


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
            saved = load_spec(ui.MANDATES_DIR / "new-fund.yaml")
            assert saved.schema_version == 2
            assert len(saved.strategies) == 1
            assert saved.strategies[0].blend.mode == mode
            menu = screen.query_one("#done-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["go-backtest", "go-back"]
            await pilot.wait_for_scheduled_animations()
            await pilot.pause()
            assert screen.query_one("#done-menu", OptionList).region.intersection(screen.region).height > 0
            text = _render(screen.query_one("#done-summary", Static).content)
            assert ui.MODE_LABELS[mode] in text
    asyncio.run(scenario())


def test_builder_existing_name_and_save_race_never_overwrite():
    original = "name: old-user-fund\n"
    path = ui.MANDATES_DIR / "existing.yaml"
    path.write_text(original)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.BuilderScreen())
            screen = app.screen
            screen.query_one("#name-input", Input).value = "existing"
            await pilot.press("enter")
            assert isinstance(app.screen, ui.ConfirmWipeScreen)  # taken: offered a replace
            await pilot.press("escape")  # declined
            assert app.screen is screen
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
            competing_path = ui.MANDATES_DIR / "save-race.yaml"
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
        (ui.MANDATES_DIR / name).write_text(content)

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
            assert isinstance(app.screen, ui.BacktestScreen)
            assert app.screen.query_one("#bt-panes", ContentSwitcher).current == "bt-dates"
            assert not app.screen.query_one("#bt-tickers", Input).disabled
            await pilot.press("escape")
            assert isinstance(app.screen, ui.FundSelectScreen)
            await app.push_screen(ui.BacktestScreen())
            menu = app.screen.query_one("#fund-list", OptionList)
            assert menu.option_count == 4
            assert sum(menu.get_option_at_index(i).disabled for i in range(4)) == 2
    asyncio.run(scenario())
    assert {p.name: p.read_text() for p in ui.MANDATES_DIR.glob("*.yaml")} == files


def test_all_invalid_funds_do_not_crash_home_picker():
    (ui.MANDATES_DIR / "old.yaml").write_text("name: old\n")
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test() as pilot:
            await app.push_screen(ui.FundSelectScreen())
            assert "Saved mandates are unavailable" in _render(app.screen.query_one("#detail-body", Static).content)
    asyncio.run(scenario())


def test_home_offers_paper_trading_first_and_an_empty_paper_screen_builds():
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            menu = app.screen.query_one("#home-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["paper", "backtest"]
            assert menu.highlighted == 0
            await pilot.press("enter")
            assert isinstance(app.screen, ui.PaperScreen)
            paper = app.screen.query_one("#paper-menu", OptionList)
            assert [paper.get_option_at_index(i).id for i in range(paper.option_count)] == ["build"]
            assert "No funds yet" in _render(app.screen.query_one("#detail-body", Static).content)
            # h/r/s have nothing to act on; enter still opens the builder.
            assert not app.screen.check_action("halt", ()) and not app.screen.check_action("sessions", ())
            await pilot.press("enter")
            assert isinstance(app.screen, ui.BuilderScreen) and app.screen.mode == "paper"
            assert "BUILD A FUND" in _render(app.screen.query_one(".rail-title", Static).content)
            assert app.screen.STEP_IDS[-1] == "step-tickers"
            await pilot.press("escape")
            assert isinstance(app.screen, ui.PaperScreen)
            await pilot.press("escape")
            assert isinstance(app.screen, ui.HomeScreen)
            menu.highlighted = menu.get_option_index("backtest")
            await pilot.press("enter")
            assert isinstance(app.screen, ui.FundSelectScreen)
    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_all_modes_can_be_backtested_and_paper_traded(mode, size):
    spec = _spec()
    spec.strategies[0].blend.mode = mode
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(ui.BacktestScreen(spec))
            assert app.screen.query_one("#bt-panes", ContentSwitcher).current == "bt-dates"
            assert not app.screen.query_one("#bt-tickers", Input).disabled
            await pilot.press("escape")
            directory = ui.deploy("test", spec, ["TEST"], root=ui.PAPER_DIR)
            await app.push_screen(ui.PaperScreen())
            menu = app.screen.query_one("#paper-menu", OptionList)
            assert menu.highlighted == menu.get_option_index("paper:0")
            assert app.screen.check_action("halt", ()) and app.screen.check_action("sessions", ())
            detail = _render(app.screen.query_one("#detail-body", Static).content)
            assert "● new" in detail and "NEXT RUN" in detail
            assert ui.load_deployed(directory).spec == spec
    asyncio.run(scenario())


def _state(**kwargs):
    return ui.FundState(cash=100000, **kwargs)


def _pending(as_of="2025-01-17", weights=None):
    record, _ = _executed_and_decided()
    decision = DecisionRecord.model_validate(record.model_dump())
    decision.as_of = as_of
    decision.final_weights = {"AAPL": .25, "MSFT": .25, "XOM": 0.0} if weights is None else weights
    return decision


def test_run_plan_says_exactly_what_the_run_will_do():
    spec = _spec(["pead"], "alpha")  # weekly by default
    # Pending decision, and the due session opens a new week: execute, then decide.
    plan = ui._run_plan("alpha", _state(last_session="2025-01-17", pending=_pending()), "2025-01-21", spec).plain
    assert "Execute the 2025-01-17 decision at the 2025-01-21 close" in plan
    assert "AAPL +25%  ·  MSFT +25%" in plan and "XOM" not in plan
    assert "views refreshed before sizing" in plan
    assert "make a new decision" in plan and "first session of the week" in plan
    # Pending decision mid-week: execute, then only mark the book.
    plan = ui._run_plan("alpha", _state(last_session="2025-01-20", pending=_pending("2025-01-20")), "2025-01-21", spec).plain
    assert "Execute the 2025-01-20 decision" in plan and "Then mark the book." in plan
    assert "new decision" not in plan
    # Nothing pending, mid-week: a mark only.
    plan = ui._run_plan("alpha", _state(last_session="2025-01-20"), "2025-01-21", spec).plain
    assert plan.startswith("Mark the book at the 2025-01-21 close.  No trades.")
    assert "decision" not in plan
    # A brand-new fund: mark, then its first decision.
    plan = ui._run_plan("alpha", _state(), "2025-01-21", spec).plain
    assert "Mark the book at the 2025-01-21 close" in plan and "first decision" in plan
    # A pending decision that went flat says so rather than listing nothing,
    # and says why when the blender recorded a reason: a dollar-neutral desk
    # with conviction but no short to balance it is not "no conviction".
    flat = _pending("2025-01-20", {})
    plan = ui._run_plan("alpha", _state(last_session="2025-01-20", pending=flat), "2025-01-21", spec).plain
    assert "flat — no conviction cleared the bar" in plan
    flat.strategies[0].flat_reason = "missing_short_side"
    plan = ui._run_plan("alpha", _state(last_session="2025-01-20", pending=flat), "2025-01-21", spec).plain
    assert "flat — no eligible shorts to balance the longs" in plan
    overview = _render(ui._session_overview(_session("2025-01-20", decision=flat)))
    assert "flat — no eligible shorts to balance the longs" in overview
    # Nothing due: when the next close is, Friday rolling to Monday.
    plan = ui._run_plan("alpha", _state(last_session="2025-01-17"), None, spec).plain
    assert plan.startswith("Up to date through 2025-01-17.  Next session closes 2025-01-20 at 4pm ET.")
    assert "Run 2025-01-17 again?" in plan and "recorded session is replaced" in plan
    assert ui._run_plan("alpha", _state(), None, spec).plain == "No completed SPY session to run yet."


def _quote(ticker, price, time="2025-01-21T15:05:00Z"):
    return ui.PriceSnapshot(ticker=ticker, price=price, time=time)


def test_live_rows_value_the_book_at_the_latest_prints():
    spec = _spec(["pead"], "alpha")
    directory = ui.deploy("alpha", spec, ["TEST"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)
    record, _ = _executed_and_decided()
    ledger.append(_session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10}, marks={"TEST": 100}))
    snap = ui._PaperSnapshot(directory)
    # Every held name needs a print; cash alone has nothing live to say.
    assert ui._live_rows(snap, {}, today="2025-01-21") == []
    label, line = ui._live_rows(snap, {"TEST": _quote("TEST", 110)}, today="2025-01-21")[0]
    text = _render(line)
    assert label == "Live" and "$101,100" in text and "+0.10%" in text and "as of 10:05 ET" in text
    # A print from before today is shown, but muted and dated: not a live gain.
    _, line = ui._live_rows(snap, {"TEST": _quote("TEST", 110, "2025-01-20T21:00:00Z")}, today="2025-01-21")[0]
    assert "as of Jan 20 16:00 ET" in _render(line)
    assert all(span.style == ui.MUTED for span in line.spans)
    assert "Live" in _render(ui._paper_detail(snap, quotes={"TEST": _quote("TEST", 110)}))
    assert "Live" not in _render(ui._paper_detail(snap))


def test_paper_screen_shows_live_prints_when_they_arrive(monkeypatch):
    spec = _spec(["pead"], "alpha")
    directory = ui.deploy("alpha", spec, ["TEST"], root=ui.PAPER_DIR)
    record, _ = _executed_and_decided()
    Ledger(directory).append(_session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10}, marks={"TEST": 100}))
    asked: list = []

    def fetch(tickers):
        asked.append(tickers)
        return {"TEST": _quote("TEST", 120, datetime.now(ui.NEW_YORK).isoformat())}
    monkeypatch.setattr(ui, "_fetch_snapshots", fetch)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.PaperScreen())
            for _ in range(50):  # the prints arrive off-thread
                await pilot.pause(0.05)
                detail = _render(app.screen.query_one("#detail-body", Static).content)
                if "Live" in detail:
                    break
            assert asked and asked[-1] == ["TEST"] and "$101,200" in detail
    asyncio.run(scenario())


def test_paper_screen_runs_through_the_approval_step(monkeypatch):
    spec = _spec(["pead"], "alpha")
    directory = ui.deploy("alpha", spec, ["TEST"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)
    record, decided = _executed_and_decided()
    ledger.append(_session("2025-01-17", decision=decided, nav=100000))
    due = {"value": "2025-01-21"}
    monkeypatch.setattr(ui, "FDClient", lambda: Mock(__enter__=lambda s: s, __exit__=lambda s, *a: None))
    monkeypatch.setattr(ui, "next_session", lambda data, benchmark, last: due["value"])
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "x")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    started: list = []
    monkeypatch.setattr(ui.RunSessionScreen, "_run", lambda self: started.append(self._directory))

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.PaperScreen())
            screen = app.screen
            detail = _render(screen.query_one("#detail-body", Static).content)
            assert "NEXT RUN" in detail and "execute the 2025-01-20 decision" in detail
            assert "TEST +25%" in detail and "SESSIONS" in detail and "2025-01-17" in detail
            await pilot.press("enter")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ui.RunConfirmScreen)
            body = _render(modal.query_one("#run-body", Static).content)
            assert "Execute the 2025-01-20 decision at the 2025-01-21 close" in body
            assert "TEST +25%" in body and "first session of the week" in body
            assert modal.check_action("confirm", ())
            await pilot.press("escape")  # say no: nothing runs
            assert app.screen is screen and started == []
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # say yes
            await pilot.pause()
            assert isinstance(app.screen, ui.RunSessionScreen) and started == [directory]
            app.screen._phase = "done"
            await pilot.press("escape")
            assert app.screen is screen
            # Nothing due: the modal says when the next close is and offers
            # to run the last session again; enter does that, esc does nothing.
            due["value"] = None
            await pilot.press("enter")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ui.RunConfirmScreen) and modal.check_action("confirm", ())
            body = _render(modal.query_one("#run-body", Static).content)
            assert "Up to date through 2025-01-17" in body and "Run 2025-01-17 again?" in body
            assert "run again" in _render(modal.query_one("#run-keys", Static).content)
            await pilot.press("escape")
            assert app.screen is screen and started == [directory]
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ui.RunSessionScreen) and app.screen._redo
            assert started == [directory, directory]
    asyncio.run(scenario())


@pytest.mark.parametrize("newest_version", [None, 2])
def test_latest_backtest_sets_headline_regardless_of_version(newest_version):
    spec = _spec(["pead"])
    receipt = {"fund": "test", "start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5,
                           "sharpe_ratio": 2, "max_drawdown_pct": .1,
                           "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    if newest_version is None:
        receipt["schema_version"] = 2
    older = ui.RESEARCH_DIR / "test-2025-01-01-2025-02-01-older.json"
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
    newer = ui.RESEARCH_DIR / "test-2025-01-01-2025-02-01-newer.json"
    newer.write_text(json.dumps(receipt))
    os.utime(newer, (2000, 2000))
    newer_summary = ui._summarize(newer, 2000)
    assert ui._last_score("test") == (.3, .2, "SPY")
    detail = _render(ui._fund_detail(spec, [newer_summary, older_summary]))
    headline = detail.split("\nBACKTESTS")[0]
    assert "LATEST BACKTEST" in headline and "30.0%" in headline
    assert older.read_bytes() == original


def test_research_history_is_matched_on_the_fund_field_not_the_filename_prefix():
    """`alpha` must not pick up `alpha-2`'s backtests: names can be prefixes."""
    receipt = {"fund": "alpha-2", "start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5, "sharpe_ratio": 2,
                           "max_drawdown_pct": .1, "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    (ui.RESEARCH_DIR / "alpha-2-2025-01-01-2025-02-01-x.json").write_text(json.dumps(receipt))
    assert ui._receipts("alpha") == []
    assert len(ui._receipts("alpha-2")) == 1
    assert ui._last_score("alpha") is None



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


def _executed_and_decided():
    """A session that executed the 2025-01-15 decision (refreshed on the 19th,
    filled at the 20th's close) and made the next decision at that close."""
    record = _record(_signal())
    decision = DecisionRecord.model_validate(record.model_dump())
    decision.final_weights = {"TEST": .25}
    record.original_assessment = decision.model_copy(deep=True)
    record.refreshed_assessment = decision.model_copy(deep=True)
    record.refreshed_assessment.as_of = "2025-01-19"
    record.execution_as_of = "2025-01-20"
    record.execution_policy = "next_close"
    record.fills = [Fill(ticker="TEST", side="buy", quantity=10, price=100)]
    decided = decision.model_copy(deep=True)
    decided.as_of = "2025-01-20"
    return record, decided


@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
@pytest.mark.parametrize("what", ["executed", "decided", "both", "neither"])
def test_session_report_separates_the_executed_cycle_from_the_new_decision(size, what):
    record, decided = _executed_and_decided()
    session = _session("2025-01-20",
                       executed=record if what in ("executed", "both") else None,
                       decision=decided if what in ("decided", "both") else None)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(ui.SessionReportScreen("alpha", session))
            screen = app.screen
            await pilot.pause()
            head = _render(screen.query_one("#report-head", Static).content)
            footer = _render(screen.query_one("#report-foot", Static).content)
            menu = screen.query_one("#report-nav", OptionList)
            ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
            assert "alpha" in head and "session 2025-01-20" in head
            assert "NAV $100,000.00" in footer
            if what in ("executed", "both"):
                assert "executed the 2025-01-15 decision (refreshed 2025-01-19)" in head
                assert "x:sec:orders" in ids and "x:sec:portfolio" in ids
                menu.highlighted = menu.get_option_index("x:sec:portfolio")
                await pilot.pause()
                assert "Target net" in _render(screen.query_one("#detail-pane", Static).content)
            if what in ("decided", "both"):
                assert "executes next session" in head
                assert "d:sec:portfolio" in ids and "d:sec:orders" not in ids
                menu.highlighted = menu.get_option_index("d:sec:portfolio")
                await pilot.pause()
                detail = _render(screen.query_one("#detail-pane", Static).content)
                assert "PROPOSED ALLOCATIONS" in detail and "TEST: +25.00%" in detail
            if what == "neither":
                assert "valuation only" in head
                assert ids == [None, "book"]
                menu.highlighted = menu.get_option_index("book")
                await pilot.pause()
                assert "flat — no positions" in _render(screen.query_one("#detail-pane", Static).content)
    asyncio.run(scenario())


def test_paper_screen_works_the_kill_switch_and_sessions_reads_the_ledger(tmp_path):
    spec = _spec(["pead"], "alpha")
    directory = ui.deploy("alpha", spec, ["TEST"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.PaperScreen())
            screen = app.screen
            menu = screen.query_one("#paper-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["paper:0", "build"]
            assert "alpha" in _render(menu.get_option("paper:0").prompt)
            detail = _render(screen.query_one("#detail-body", Static).content)
            assert "● new" in detail and "mark the book at the latest completed close" in detail
            assert screen.check_action("halt", ()) and not screen.check_action("resume", ())

            await pilot.press("h")  # no prompt: halts at once
            await pilot.pause()
            assert app.screen is screen
            assert ledger.halted() == ui._APP_HALT
            assert menu.highlighted == menu.get_option_index("paper:0")  # re-highlighted after the reload
            detail = _render(screen.query_one("#detail-body", Static).content)
            assert "■ halted" in detail and "r to resume" in detail and ui._APP_HALT not in detail
            assert not screen.check_action("halt", ()) and screen.check_action("resume", ())
            await pilot.press("enter")  # halted funds do not run
            await pilot.pause()
            assert app.screen is screen
            await pilot.press("r")
            await pilot.pause()
            assert ledger.halted() is None
            assert [e["kind"] for e in ledger.events()] == ["halt", "resume"]

            # Two sessions land in the ledger behind the screen's back; coming
            # back to the screen re-reads them.
            record, decided = _executed_and_decided()
            first = _session("2025-01-17", decision=decided, nav=100000)
            second = _session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10},
                              marks={"TEST": 100}, prev_hash=first.hash)
            ledger.append(first)
            ledger.append(second)
            await app.push_screen(ui.SessionReportScreen("alpha", first))
            await pilot.press("escape")
            await pilot.pause()
            detail = _render(screen.query_one("#detail-body", Static).content)
            assert "● live" in detail and "mark the book" in detail and "2025-01-17 · 2 sessions" in detail
            assert "SESSIONS" in detail and "2025-01-20" in detail and "1 fill" in detail
            assert "+1.0%" in _render(menu.get_option("paper:0").prompt)

            await pilot.press("s")
            sessions_screen = app.screen
            assert isinstance(sessions_screen, ui.SessionsScreen)
            assert "last session 2025-01-20" in _render(sessions_screen.query_one("#pf-status", Static).content)
            assert "+1.00%" in _render(sessions_screen.query_one("#stat-return", Static).content)
            sessions = sessions_screen.query_one("#pf-sessions", OptionList)
            rows = [_render(sessions.get_option_at_index(i).prompt) for i in range(sessions.option_count)]
            assert rows[0].startswith(" 2025-01-20") and "1 fill" in rows[0]
            assert rows[1].startswith(" 2025-01-17") and "decided" in rows[1]
            overview = _render(sessions_screen.query_one("#detail-pane", Static).content)
            assert "EXECUTED" in overview and "decision from 2025-01-15" in overview
            await pilot.press("enter")
            assert isinstance(app.screen, ui.SessionReportScreen)
            assert "executed the 2025-01-15 decision" in _render(app.screen.query_one("#report-head", Static).content)
            await pilot.press("escape")
            await pilot.press("escape")
            assert app.screen is screen

            # d deletes the fund — ledger, book, definition and backtests — after a yes.
            (ui.MANDATES_DIR / "alpha.yaml").write_text(yaml.safe_dump(spec.model_dump()))
            await pilot.press("d")
            modal = app.screen
            assert isinstance(modal, ui.ConfirmWipeScreen)
            manifest = _render(modal.query_one("#confirm-files", Static).content)
            assert "2 sessions of ledger" in manifest and "alpha.yaml" in manifest and "name is free again" in manifest
            await pilot.press("escape")  # no
            assert app.screen is screen and directory.exists()
            await pilot.press("d")
            await pilot.press("enter")  # yes
            await pilot.pause()
            assert app.screen is screen
            assert not directory.exists() and not (ui.MANDATES_DIR / "alpha.yaml").exists()
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["build"]
            assert not screen.check_action("delete", ()) and not screen.check_action("halt", ())
    asyncio.run(scenario())


def _minute_spec(name="fast", interval=5, start="13:00", end="13:10"):
    return FundSpec(**{**_spec(["pead"], name).model_dump(), "rebalance": "minute", "interval": interval,
                       "window": {"start": start, "end": end}})


def test_minute_fund_rows_are_pure(monkeypatch):
    directory = ui.deploy("fast", _minute_spec(), ["TEST"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)
    noon = datetime(2025, 1, 21, 12, 0, tzinfo=ui.NEW_YORK)
    snap = ui._PaperSnapshot(directory)
    assert not snap.running and snap.intraday
    rows = dict(ui._next_run_rows(snap, now=noon))
    assert _render(rows["Next bar"]).strip() == "13:00:00 ET   ○ idle · enter to start"
    assert rows["First"] == "mark the book at the first bar's prints" and rows["Then"] == "make the first decision"
    assert ui._today_rows(snap, now=noon) == []
    assert "○ idle" in _render(ui._paper_slot(0, snap)) and "○ idle" in _render(snap.badge())
    assert _render(snap.status()).startswith("○ IDLE  no sessions yet")

    record, decided = _executed_and_decided()
    first = _session("2025-01-21T13:00:00", decision=decided, nav=100000)
    second = _session("2025-01-21T13:05:00", executed=record, nav=101000, positions={"TEST": 10},
                      marks={"TEST": 100}, prev_hash=first.hash)
    ledger.append(first)
    ledger.append(second)
    (directory / PID_FILE).write_text(str(os.getpid()))
    snap = ui._PaperSnapshot(directory)
    assert snap.running
    rows = dict(ui._next_run_rows(snap, now=noon.replace(hour=13, minute=6)))
    assert _render(rows["Next bar"]).strip() == "13:10:00 ET   ● running" and rows["Then"] == "make a new decision"
    # After the day's last bar the next one is tomorrow's open, named by weekday.
    assert _render(dict(ui._next_run_rows(snap, now=noon.replace(hour=15)))["Next bar"]).startswith("Wed 13:00:00 ET")
    today = dict(ui._today_rows(snap, now=noon.replace(hour=13, minute=6)))
    assert _render(today["Bars"]).strip() == "2 / 3   last 13:05:00 ET"
    assert _render(today["Since open"]).strip() == "+1.00%   1 fill"
    assert ui._today_rows(snap, now=noon + timedelta(days=1)) == []  # yesterday's bars are not today's
    detail = _render(ui._paper_detail(snap, now=noon.replace(hour=13, minute=6)))
    assert "every 5m · 13:00–13:10 ET" in detail and "TODAY" in detail and "● running" in detail
    assert "SESSIONS" in detail and "2025-01-21T13:05:00" in detail
    assert "+1.0%  ● running" in _render(ui._paper_slot(0, snap))
    assert snap.metrics().n_cycles == 1  # bar keys do not trip the metrics' date math


def test_paper_screen_enter_starts_and_stops_a_minute_fund(monkeypatch):
    directory = ui.deploy("fast", _minute_spec(), ["TEST"], root=ui.PAPER_DIR)
    for variable in ("FINANCIAL_DATASETS_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.setenv(variable, "x")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")
    spawned, stopped = [], []

    def spawn(path):
        spawned.append(path)
        (path / PID_FILE).write_text(str(os.getpid()))  # what the real runner does on start
        return os.getpid()

    def stop(path):
        stopped.append(path)
        (path / PID_FILE).unlink()
        return True
    monkeypatch.setattr(ui, "_spawn_runner", spawn)
    monkeypatch.setattr(ui, "stop_runner", stop)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.PaperScreen())
            screen = app.screen
            menu = screen.query_one("#paper-menu", OptionList)
            assert "○ idle" in _render(menu.get_option("paper:0").prompt)
            await pilot.press("enter")
            await pilot.pause()
            assert spawned == [directory] and app.screen is screen  # no approval modal for a runner
            assert "● running" in _render(menu.get_option("paper:0").prompt)
            assert "● running" in _render(screen.query_one("#detail-body", Static).content)
            await pilot.press("enter")
            await pilot.pause()
            assert stopped == [directory] and "○ idle" in _render(menu.get_option("paper:0").prompt)
            # A halted minute fund neither starts nor stops.
            await pilot.press("h")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert spawned == [directory]
    asyncio.run(scenario())


def test_sessions_screen_groups_a_minute_funds_bars_by_day():
    directory = ui.deploy("fast", _minute_spec(), ["TEST"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)
    record, decided = _executed_and_decided()
    chain = [_session("2025-01-21T13:00:00", decision=decided, nav=100000)]
    chain.append(_session("2025-01-21T13:05:00", executed=record, nav=101000, positions={"TEST": 10},
                          marks={"TEST": 100}, prev_hash=chain[-1].hash))
    chain.append(_session("2025-01-22T13:00:00", nav=102000, positions={"TEST": 10}, marks={"TEST": 200},
                          prev_hash=chain[-1].hash))
    for r in chain:
        ledger.append(r)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(ui.SessionsScreen(directory))
            screen = app.screen
            await pilot.pause()
            assert "every 5m · 13:00–13:10 ET" in _render(screen.query_one("#pf-head", Static).content)
            sessions = screen.query_one("#pf-sessions", OptionList)
            rows = [(sessions.get_option_at_index(i).id, _render(sessions.get_option_at_index(i).prompt).strip())
                    for i in range(sessions.option_count)]
            assert rows[0][0] is None and rows[0][1].startswith("2025-01-22  +0.99%  1 bar")
            assert rows[1] == ("s:0", "13:00:00  +0.99%")
            assert rows[2][0] is None and rows[2][1].startswith("2025-01-21  +1.00%  2 bars")
            assert rows[3][0] == "s:1" and rows[3][1].startswith("13:05:00  +1.00%  1 fill")
            assert rows[4][0] == "s:2" and rows[4][1].startswith("13:00:00  +0.00%  decided")
            assert sessions.highlighted == 1  # the newest bar, not its heading
            assert "next bar's close" in _render(ui._session_overview(chain[0]))
    asyncio.run(scenario())


def test_builder_paper_mode_builds_a_live_fund_and_refuses_taken_names():
    ui.deploy("taken", _spec(["pead"], "taken"), ["NVDA", "AMD"], root=ui.PAPER_DIR)
    (ui.MANDATES_DIR / "saved.yaml").write_text(yaml.safe_dump(_spec(["pead"], "saved").model_dump()))

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.PaperScreen())
            paper = app.screen
            await pilot.press("end", "enter")  # the + row
            screen = app.screen
            assert isinstance(screen, ui.BuilderScreen) and screen.mode == "paper"
            assert screen.STEP_TITLES == ["Name", "Strategies", "Capital", "Cadence", "Tickers"]
            for taken in ("taken", "saved"):  # paper funds and saved definitions both count
                screen.query_one("#name-input", Input).value = taken
                await pilot.press("enter")
                assert isinstance(app.screen, ui.ConfirmWipeScreen)
                await pilot.press("escape")
                assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter", "enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-tickers"
            tickers = screen.query_one("#tickers-input", Input)
            assert tickers.value == "NVDA, AMD"  # prefilled from the newest paper fund
            assert not (ui.PAPER_DIR / "alpha").exists()  # nothing written before the last step
            tickers.value = "test, msft"
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            assert "alpha is live." in _render(screen.query_one("#done-summary", Static).content)
            menu = screen.query_one("#done-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["go-run", "go-back"]
            deployed = ui.load_deployed(ui.PAPER_DIR / "alpha")
            saved = load_spec(ui.MANDATES_DIR / "alpha.yaml")
            assert deployed.universe == ["TEST", "MSFT"] and deployed.spec == saved
            assert saved.rebalance == "weekly" and saved.strategies[0].models[0].name == "pead"
            # Back lands on the fund list with the new fund highlighted.
            menu.highlighted = menu.get_option_index("go-back")
            await pilot.press("enter")
            assert app.screen is paper
            rail = paper.query_one("#paper-menu", OptionList)
            assert rail.get_option_at_index(rail.highlighted).id == "paper:0"
            assert "alpha" in _render(rail.get_option("paper:0").prompt)
    asyncio.run(scenario())


def test_builder_minute_path_sets_interval_and_window_and_offers_start_running():
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.BuilderScreen(mode="paper"))
            screen = app.screen
            screen.query_one("#name-input", Input).value = "fast"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter")
            cadences = screen.query_one("#cadence-list", OptionList)
            assert cadences.highlighted == ui.BuilderScreen.CADENCES.index("weekly")  # the default, still
            prompts = [_render(cadences.get_option_at_index(i).prompt) for i in range(cadences.option_count)]
            assert prompts[0].startswith("minute") and "set the interval and trading window" in prompts[0]
            assert "one decision at each close" in prompts[1] and "news-speed" not in "".join(prompts)
            cadences.highlighted = 0
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-interval"
            assert "every 1m · 09:30–16:00 ET · 391 sessions a day" in _render(
                screen.query_one("#interval-line", Static).content)

            interval = screen.query_one("#interval-input", Input)
            interval.value = "0.005"
            await pilot.pause()
            line = _render(screen.query_one("#interval-line", Static).content)
            assert "shortest interval is 1s" in line and "stamped to the second" in line
            await pilot.press("enter")  # refused; still here
            assert screen.query_one("#panes", ContentSwitcher).current == "step-interval"
            interval.value = "0.0167"  # every second: allowed, with a caveat about keeping up
            await pilot.pause()
            line = _render(screen.query_one("#interval-line", Static).content)
            assert "every 1s · 09:30–16:00 ET · 23,401 sessions a day" in line and "logged as gaps" in line
            interval.value = "0.5"
            await pilot.pause()
            line = _render(screen.query_one("#interval-line", Static).content)
            assert "every 30s · 09:30–16:00 ET · 781 sessions a day" in line and "gaps" not in line
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-window"
            assert "Cadence" in _render(screen.query_one("#rail-3", Static).content)

            start, end = screen.query_one("#window-start-input", Input), screen.query_one("#window-end-input", Input)
            end.value = "21:00"
            await pilot.pause()
            assert "outside US extended hours" in _render(screen.query_one("#window-line", Static).content)
            await pilot.press("enter")  # start's enter moves to end
            await pilot.press("enter")  # end's enter: refused
            assert screen.query_one("#panes", ContentSwitcher).current == "step-window"
            start.value, end.value = "09:00", "12:00"
            await pilot.pause()
            assert "every 30s · 09:00–12:00 ET · 361 sessions a day" in _render(
                screen.query_one("#window-line", Static).content)
            end.focus()
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-tickers"
            rail = _render(screen.query_one("#rail-3", Static).content)
            assert "every 30s" in rail and "09:00–12:00 ET" in rail
            await pilot.press("escape")  # back from tickers lands on the window, not the cadence list
            assert screen.query_one("#panes", ContentSwitcher).current == "step-window"
            await pilot.press("escape", "escape")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-cadence"
            assert cadences.highlighted == 0
            await pilot.press("enter", "enter")  # interval and window remembered
            end.focus()
            await pilot.press("enter")
            screen.query_one("#tickers-input", Input).value = "TEST"
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            menu = screen.query_one("#done-menu", OptionList)
            assert _render(menu.get_option_at_index(0).prompt).strip() == "▶  Start running"
            summary = _render(screen.query_one("#done-summary", Static).content)
            assert "every 30s · 09:00–12:00 ET" in summary and "Start it and it runs every 30s" in summary
            saved = load_spec(ui.MANDATES_DIR / "fast.yaml")
            assert saved.rebalance == "minute" and saved.interval == 0.5
            assert saved.window.start == "09:00" and saved.window.end == "12:00"
            assert ui.load_deployed(ui.PAPER_DIR / "fast").spec == saved
    asyncio.run(scenario())


def test_builder_minute_helpers_are_pure():
    from zoneinfo import ZoneInfo
    window = ui.TradingWindow(start="09:30", end="16:00")
    assert ui._interval_line(1, window) == "every 1m · 09:30–16:00 ET · 391 sessions a day"
    assert ui._interval_line(90, window) == "every 1h30m · 09:30–16:00 ET · 6 sessions a day"
    with pytest.raises(ValueError, match="in minutes"):
        ui._parse_interval("soon")
    with pytest.raises(ValueError, match="1s"):
        ui._parse_interval("0.005")
    assert ui._parse_interval("0.01") == 0.01  # 0.6s rounds to the 1s floor, as the spec counts it
    assert ui._fast_caveat(0.1) and ui._fast_caveat(1 / 6) is None  # 6s warns, 10s does not

    today = datetime(2025, 7, 1, tzinfo=ui.NEW_YORK)  # summer: ET is UTC-4
    assert ui._window_lines(window, 1, today=today, local_zone=ui.NEW_YORK) == [
        "every 1m · 09:30–16:00 ET · 391 sessions a day"]
    assert ui._window_lines(window, 1, today=today, local_zone=ZoneInfo("America/Los_Angeles"))[1] == \
        "that is 06:30–13:00 PDT where you are"
    assert ui._window_lines(window, 1, today=today, local_zone=ZoneInfo("Asia/Tokyo"))[1] == \
        "that is 22:30–05:00 JST where you are (the next day)"
    assert ui._cadence_identity(FundSpec(**{**_spec().model_dump(), "rebalance": "minute", "interval": 5})) == \
        "every 5m · 09:30–16:00 ET"
    assert ui._cadence_identity(_spec()) == "weekly"


def test_builder_replaces_a_taken_name_only_after_yes_and_only_at_the_end():
    old = _spec(["buffett"], "alpha")
    old.rebalance = "monthly"
    (ui.MANDATES_DIR / "alpha.yaml").write_text(yaml.safe_dump(old.model_dump()))
    receipt = ui.RESEARCH_DIR / "alpha-backtest-2025-01-01.json"
    receipt.write_text(json.dumps({"fund": "alpha", "universe": ["NVDA"], "metrics": {
        "total_return_pct": .1, "annualized_return_pct": .1, "sharpe_ratio": 1, "max_drawdown_pct": -.1,
        "benchmark_return_pct": 0, "excess_return_pct": .1, "n_cycles": 1}}))
    directory = ui.deploy("alpha", old, ["NVDA"], root=ui.PAPER_DIR)
    ledger = Ledger(directory)
    ledger.append(_session("2025-01-17", nav=100000))
    untouched = ui.deploy("beta", old, ["AMD"], root=ui.PAPER_DIR)

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.BuilderScreen(mode="paper"))
            screen = app.screen
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            modal = app.screen
            assert isinstance(modal, ui.ConfirmWipeScreen)
            manifest = _render(modal.query_one("#confirm-files", Static).content)
            assert "alpha.yaml" in manifest and "1 backtest" in manifest and "1 session of ledger" in manifest
            await pilot.press("enter")  # yes, replace
            assert screen.query_one("#panes", ContentSwitcher).current == "step-strategies"
            # Nothing has gone yet: an abandoned wizard costs nothing.
            assert receipt.exists() and len(ledger.records()) == 1
            await pilot.press("escape")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            # Re-submitting the same name does not ask twice; a different name forgets the yes.
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-strategies"
            await pilot.press("escape")
            screen.query_one("#name-input", Input).value = "gamma"
            await pilot.press("enter")
            assert screen._state["replace"] is None
            await pilot.press("escape")
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            assert isinstance(app.screen, ui.ConfirmWipeScreen)
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter", "enter")
            screen.query_one("#tickers-input", Input).value = "TEST"
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            fresh = ui.load_deployed(ui.PAPER_DIR / "alpha")
            assert fresh.universe == ["TEST"] and fresh.spec.rebalance == "weekly"
            assert fresh.spec.strategies[0].models[0].name == "pead"
            assert Ledger(ui.PAPER_DIR / "alpha").records() == []  # a new track record
            assert load_spec(ui.MANDATES_DIR / "alpha.yaml") == fresh.spec
            assert not receipt.exists()
            assert ui.load_deployed(untouched).universe == ["AMD"]  # neighbours untouched
    asyncio.run(scenario())


def test_builder_paper_mode_run_its_first_session_opens_the_approval_step(monkeypatch):
    monkeypatch.setattr(ui, "FDClient", lambda: Mock(__enter__=lambda s: s, __exit__=lambda s, *a: None))
    monkeypatch.setattr(ui, "next_session", lambda data, benchmark, last: "2025-01-21")
    for variable in ("FINANCIAL_DATASETS_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.setenv(variable, "x")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")

    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(ui.PaperScreen())
            await pilot.press("enter")
            screen = app.screen
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(ui._CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter", "enter")
            screen.query_one("#tickers-input", Input).value = "TEST"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # "Run its first session"
            await pilot.pause()
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ui.RunConfirmScreen)
            body = _render(modal.query_one("#run-body", Static).content)
            assert "Mark the book at the 2025-01-21 close.  No trades." in body and "first decision" in body
            await pilot.press("escape")
            paper = app.screen
            assert isinstance(paper, ui.PaperScreen)
            rail = paper.query_one("#paper-menu", OptionList)
            assert rail.get_option_at_index(rail.highlighted).id == "paper:0"
            assert not isinstance(app.screen_stack[-2], ui.BuilderScreen)  # the builder was switched out
    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_backtest_daily_board_matches_final_metrics_and_uses_fill_dates(size, tmp_path):
    from hedge_fund.backtesting.fund import DailyValuation, performance_metrics, FundBacktestResult
    from hedge_fund.brokers.models import Fill
    record = _record(_signal())
    record.execution_as_of = "2025-01-16"
    record.fills = [Fill(ticker="TEST", side="buy", quantity=1, price=100)]
    dates = ["2025-01-15", "2025-01-16", "2025-01-17"]
    nav = [100000, 100000, 90000]
    benchmark_nav = [100000, 101000, 102000]
    metrics = performance_metrics(100000, dates, nav, benchmark_nav, [record])
    sessions = [_session(dates[0]), _session(dates[1], executed=record), _session(dates[2], nav=90000)]
    result = FundBacktestResult(fund=record.fund, start=dates[0], end=dates[-1], rebalance="weekly",
                                benchmark="SPY", universe=["TEST"], capital=100000, dates=dates,
                                nav=nav, benchmark_nav=benchmark_nav, records=sessions, metrics=metrics)
    async def scenario():
        app = ui.HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(ui.BacktestScreen(record.spec))
            screen = app.screen
            screen.query_one("#bt-panes", ContentSwitcher).current = "bt-run"
            screen._begin_replay(record.spec, dict(zip(dates, [100, 101, 102])), 3)
            screen._board_valuation(DailyValuation(as_of=dates[0], nav=nav[0], benchmark_nav=benchmark_nav[0]))
            screen._board_tick(record)
            for i in (1, 2):
                screen._board_valuation(DailyValuation(as_of=dates[i], nav=nav[i], benchmark_nav=benchmark_nav[i]))
            await pilot.pause()
            before = {name: _render(screen.query_one(f"#stat-{name}", Static).content)
                      for name in ("nav", "return", "sharpe", "dd")}
            assert screen._tape[0][0] == "2025-01-16"
            assert "session 3/3" in _render(screen.query_one("#cycle-line", Static).content)
            screen._finish(result, tmp_path / "backtest.json")
            after = {name: _render(screen.query_one(f"#stat-{name}", Static).content) for name in before}
            assert before == after
            phase = _render(screen.query_one("#phase-line", Static).content)
            assert "1 executed cycles" in phase and "pending" not in phase
    asyncio.run(scenario())
