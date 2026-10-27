"""The fund wizard in both modes, including the minute cadence sub-steps."""

import asyncio
import json
from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import yaml
from textual.widgets import ContentSwitcher, Input, OptionList, SelectionList, Static

from hedge_fund import paths
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import FundSpec, load_spec, TradingWindow
from hedge_fund.paper import deploy, Ledger, load_deployed
from hedge_fund.signals import ALPHA_MODEL_REGISTRY
from hedge_fund.tui import builder, funds, paper
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import make_session, make_spec, render
from hedge_fund.tui.shared import cadence_identity, MODE_LABELS, strategy_description


def test_mixed_description_identifies_short_analysts():
    description = strategy_description(make_spec().strategies[0])
    assert "Short ideas must be supported by Druckenmiller." in description
    assert "Long-only analysts contribute ownership views." in description
    assert "Long-only" in builder.BuilderScreen._agent_prompt("buffett", ALPHA_MODEL_REGISTRY["buffett"]).plain


@pytest.mark.parametrize("names,mode", [
    (["buffett"], "long_only"),
    (["buffett", "druckenmiller"], "long_short"),
    (["druckenmiller"], "long_short"),
])
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_builder_derives_rules_and_back_navigation_does_not_duplicate(names, mode, size):
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(builder.BuilderScreen())
            screen = app.screen
            screen.query_one("#name-input", Input).value = "new-fund"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
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
            saved = load_spec(paths.MANDATES_DIR / "new-fund.yaml")
            assert saved.schema_version == 2
            assert len(saved.strategies) == 1
            assert saved.strategies[0].blend.mode == mode
            menu = screen.query_one("#done-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["go-backtest", "go-back"]
            await pilot.wait_for_scheduled_animations()
            await pilot.pause()
            assert screen.query_one("#done-menu", OptionList).region.intersection(screen.region).height > 0
            text = render(screen.query_one("#done-summary", Static).content)
            assert MODE_LABELS[mode] in text
    asyncio.run(scenario())


def test_builder_existing_name_and_save_race_never_overwrite():
    original = "name: old-user-fund\n"
    path = paths.MANDATES_DIR / "existing.yaml"
    path.write_text(original)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(builder.BuilderScreen())
            screen = app.screen
            screen.query_one("#name-input", Input).value = "existing"
            await pilot.press("enter")
            assert isinstance(app.screen, funds.ConfirmWipeScreen)  # taken: offered a replace
            await pilot.press("escape")  # declined
            assert app.screen is screen
            assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            assert path.read_text() == original
            screen.query_one("#name-input", Input).value = "save-race"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-cadence"
            # Simulate another process saving the chosen name after validation.
            competing_path = paths.MANDATES_DIR / "save-race.yaml"
            competing_path.write_text(original)
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            assert competing_path.read_text() == original
    asyncio.run(scenario())


def test_builder_paper_mode_builds_a_live_fund_and_refuses_taken_names():
    deploy("taken", make_spec(["pead"], "taken"), ["NVDA", "AMD"], root=paths.PAPER_DIR)
    (paths.MANDATES_DIR / "saved.yaml").write_text(yaml.safe_dump(make_spec(["pead"], "saved").model_dump()))

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(paper.PaperScreen())
            fund_list = app.screen
            await pilot.press("end", "enter")  # the + row
            screen = app.screen
            assert isinstance(screen, builder.BuilderScreen) and screen.mode == "paper"
            assert screen.STEP_TITLES == ["Name", "Strategies", "Capital", "Cadence", "Tickers"]
            for taken in ("taken", "saved"):  # paper funds and saved definitions both count
                screen.query_one("#name-input", Input).value = taken
                await pilot.press("enter")
                assert isinstance(app.screen, funds.ConfirmWipeScreen)
                await pilot.press("escape")
                assert screen.query_one("#panes", ContentSwitcher).current == "step-name"
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter", "enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-tickers"
            tickers = screen.query_one("#tickers-input", Input)
            assert tickers.value == "NVDA, AMD"  # prefilled from the newest paper fund
            assert not (paths.PAPER_DIR / "alpha").exists()  # nothing written before the last step
            tickers.value = "test, msft"
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            assert "alpha is live." in render(screen.query_one("#done-summary", Static).content)
            menu = screen.query_one("#done-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["go-run", "go-back"]
            deployed = load_deployed(paths.PAPER_DIR / "alpha")
            saved = load_spec(paths.MANDATES_DIR / "alpha.yaml")
            assert deployed.universe == ["TEST", "MSFT"] and deployed.spec == saved
            assert saved.rebalance == "weekly" and saved.strategies[0].models[0].name == "pead"
            # Back lands on the fund list with the new fund highlighted.
            menu.highlighted = menu.get_option_index("go-back")
            await pilot.press("enter")
            assert app.screen is fund_list
            rail = fund_list.query_one("#paper-menu", OptionList)
            assert rail.get_option_at_index(rail.highlighted).id == "paper:0"
            assert "alpha" in render(rail.get_option("paper:0").prompt)
    asyncio.run(scenario())


def test_builder_minute_path_sets_interval_and_window_and_offers_start_running():
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(builder.BuilderScreen(mode="paper"))
            screen = app.screen
            screen.query_one("#name-input", Input).value = "fast"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter")
            cadences = screen.query_one("#cadence-list", OptionList)
            assert cadences.highlighted == builder.BuilderScreen.CADENCES.index("weekly")  # the default, still
            prompts = [render(cadences.get_option_at_index(i).prompt) for i in range(cadences.option_count)]
            assert prompts[0].startswith("minute") and "set the interval and trading window" in prompts[0]
            assert "one decision at each close" in prompts[1] and "news-speed" not in "".join(prompts)
            cadences.highlighted = 0
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-interval"
            assert "every 1m · 09:30–16:00 ET · 391 sessions a day" in render(
                screen.query_one("#interval-line", Static).content)

            interval = screen.query_one("#interval-input", Input)
            interval.value = "0.005"
            await pilot.pause()
            line = render(screen.query_one("#interval-line", Static).content)
            assert "shortest interval is 1s" in line and "stamped to the second" in line
            await pilot.press("enter")  # refused; still here
            assert screen.query_one("#panes", ContentSwitcher).current == "step-interval"
            interval.value = "0.0167"  # every second: allowed, with a caveat about keeping up
            await pilot.pause()
            line = render(screen.query_one("#interval-line", Static).content)
            assert "every 1s · 09:30–16:00 ET · 23,401 sessions a day" in line and "logged as gaps" in line
            interval.value = "0.5"
            await pilot.pause()
            line = render(screen.query_one("#interval-line", Static).content)
            assert "every 30s · 09:30–16:00 ET · 781 sessions a day" in line and "gaps" not in line
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-window"
            assert "Cadence" in render(screen.query_one("#rail-3", Static).content)

            start, end = screen.query_one("#window-start-input", Input), screen.query_one("#window-end-input", Input)
            end.value = "21:00"
            await pilot.pause()
            assert "outside US extended hours" in render(screen.query_one("#window-line", Static).content)
            await pilot.press("enter")  # start's enter moves to end
            await pilot.press("enter")  # end's enter: refused
            assert screen.query_one("#panes", ContentSwitcher).current == "step-window"
            start.value, end.value = "09:00", "12:00"
            await pilot.pause()
            assert "every 30s · 09:00–12:00 ET · 361 sessions a day" in render(
                screen.query_one("#window-line", Static).content)
            end.focus()
            await pilot.press("enter")
            assert screen.query_one("#panes", ContentSwitcher).current == "step-tickers"
            rail = render(screen.query_one("#rail-3", Static).content)
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
            assert render(menu.get_option_at_index(0).prompt).strip() == "▶  Run its first session"  # same as daily
            summary = render(screen.query_one("#done-summary", Static).content)
            assert "every 30s · 09:00–12:00 ET" in summary
            assert "marks the book at the current bar" in summary and "leave a runner on it" in summary
            saved = load_spec(paths.MANDATES_DIR / "fast.yaml")
            assert saved.rebalance == "minute" and saved.interval == 0.5
            assert saved.window.start == "09:00" and saved.window.end == "12:00"
            assert load_deployed(paths.PAPER_DIR / "fast").spec == saved
    asyncio.run(scenario())


def test_builder_minute_helpers_are_pure():
    window = TradingWindow(start="09:30", end="16:00")
    assert builder.interval_line(1, window) == "every 1m · 09:30–16:00 ET · 391 sessions a day"
    assert builder.interval_line(90, window) == "every 1h30m · 09:30–16:00 ET · 6 sessions a day"
    with pytest.raises(ValueError, match="in minutes"):
        builder.parse_interval("soon")
    with pytest.raises(ValueError, match="1s"):
        builder.parse_interval("0.005")
    assert builder.parse_interval("0.01") == 0.01  # 0.6s rounds to the 1s floor, as the spec counts it
    assert builder.fast_caveat(0.1) and builder.fast_caveat(1 / 6) is None  # 6s warns, 10s does not

    today = datetime(2025, 7, 1, tzinfo=NEW_YORK)  # summer: ET is UTC-4
    assert builder.window_lines(window, 1, today=today, local_zone=NEW_YORK) == [
        "every 1m · 09:30–16:00 ET · 391 sessions a day"]
    assert builder.window_lines(window, 1, today=today, local_zone=ZoneInfo("America/Los_Angeles"))[1] == \
        "that is 06:30–13:00 PDT where you are"
    assert builder.window_lines(window, 1, today=today, local_zone=ZoneInfo("Asia/Tokyo"))[1] == \
        "that is 22:30–05:00 JST where you are (the next day)"
    assert cadence_identity(FundSpec(**{**make_spec().model_dump(), "rebalance": "minute", "interval": 5})) == \
        "every 5m · 09:30–16:00 ET"
    assert cadence_identity(make_spec()) == "weekly"


def test_builder_replaces_a_taken_name_only_after_yes_and_only_at_the_end():
    old = make_spec(["buffett"], "alpha")
    old.rebalance = "monthly"
    (paths.MANDATES_DIR / "alpha.yaml").write_text(yaml.safe_dump(old.model_dump()))
    receipt = paths.RESEARCH_DIR / "alpha-backtest-2025-01-01.json"
    receipt.write_text(json.dumps({"fund": "alpha", "universe": ["NVDA"], "metrics": {
        "total_return_pct": .1, "annualized_return_pct": .1, "sharpe_ratio": 1, "max_drawdown_pct": -.1,
        "benchmark_return_pct": 0, "excess_return_pct": .1, "n_cycles": 1}}))
    directory = deploy("alpha", old, ["NVDA"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)
    ledger.append(make_session("2025-01-17", nav=100000))
    untouched = deploy("beta", old, ["AMD"], root=paths.PAPER_DIR)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(builder.BuilderScreen(mode="paper"))
            screen = app.screen
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            modal = app.screen
            assert isinstance(modal, funds.ConfirmWipeScreen)
            manifest = render(modal.query_one("#confirm-files", Static).content)
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
            assert isinstance(app.screen, funds.ConfirmWipeScreen)
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
            await pilot.press("enter")
            screen.query_one("#agent-list", SelectionList).select("pead")
            await pilot.press("enter", "enter", "enter")
            screen.query_one("#tickers-input", Input).value = "TEST"
            await pilot.press("enter")
            await pilot.pause()
            assert screen.query_one("#panes", ContentSwitcher).current == "step-done"
            fresh = load_deployed(paths.PAPER_DIR / "alpha")
            assert fresh.universe == ["TEST"] and fresh.spec.rebalance == "weekly"
            assert fresh.spec.strategies[0].models[0].name == "pead"
            assert Ledger(paths.PAPER_DIR / "alpha").records() == []  # a new track record
            assert load_spec(paths.MANDATES_DIR / "alpha.yaml") == fresh.spec
            assert not receipt.exists()
            assert load_deployed(untouched).universe == ["AMD"]  # neighbours untouched
    asyncio.run(scenario())


def test_builder_paper_mode_run_its_first_session_opens_the_approval_step(monkeypatch):
    monkeypatch.setattr(paper, "FDClient", lambda: Mock(__enter__=lambda s: s, __exit__=lambda s, *a: None))
    monkeypatch.setattr(paper, "next_session", lambda data, benchmark, last: "2025-01-21")
    for variable in ("FINANCIAL_DATASETS_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.setenv(variable, "x")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await app.push_screen(paper.PaperScreen())
            await pilot.press("enter")
            screen = app.screen
            screen.query_one("#name-input", Input).value = "alpha"
            await pilot.press("enter")
            screen.query_one("#strategy-list", SelectionList).select(builder.CUSTOM)
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
            assert isinstance(modal, paper.RunConfirmScreen)
            body = render(modal.query_one("#run-body", Static).content)
            assert "Mark the book at the 2025-01-21 close.  No trades." in body and "first decision" in body
            await pilot.press("escape")
            fund_list = app.screen
            assert isinstance(fund_list, paper.PaperScreen)
            rail = fund_list.query_one("#paper-menu", OptionList)
            assert rail.get_option_at_index(rail.highlighted).id == "paper:0"
            assert not isinstance(app.screen_stack[-2], builder.BuilderScreen)  # the builder was switched out
    asyncio.run(scenario())
