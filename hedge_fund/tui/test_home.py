"""The landing screen: model picker, key prompt, the key gate, and navigation."""

import asyncio
import os
import stat
from unittest.mock import Mock

import pytest
from textual.widgets import Input, OptionList, Static

from hedge_fund.tui import builder, funds, home, keys, paper
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import render


@pytest.mark.parametrize("save", [True, False])
def test_picker_and_masked_key_save_or_cancel(save, isolated_configuration):
    saved = isolated_configuration
    saved.write_text("# keep this comment\nUNRELATED_KEY=untouched\n")
    original = saved.read_text()

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.press("m")
            picker = app.screen.query_one("#picker-list", OptionList)
            index = picker.get_option_index("jev-1.13.0")
            assert not picker.get_option_at_index(index).disabled
            # Provider names are group headers; model rows show label and id.
            assert "Jev" in render(picker.get_option_at_index(index).prompt)
            assert "jev-1.13.0" in render(picker.get_option_at_index(index).prompt)
            picker.highlighted = index
            await pilot.press("enter")
            assert os.environ["HEDGE_FUND_LLM_MODEL"] == "jev-1.13.0"
            await pilot.press("k")
            entry = app.screen.query_one("#key-input", Input)
            assert entry.password is True
            assert entry.placeholder == "TYPESAFE_API_KEY"
            entry.value = "fixture-typesafe-secret-value"
            await pilot.press("enter" if save else "escape")
            assert isinstance(app.screen, home.HomeScreen)
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
        app = HedgeFundApp()
        resumed = Mock()
        async with app.run_test(size=(100, 35)) as pilot:
            assert home.demand_run_keys(app, resumed) is False
            await pilot.pause()
            assert isinstance(app.screen, home.KeyPromptScreen)
            await pilot.press("escape")
            resumed.assert_not_called()
            assert not isolated_configuration.exists()
            assert home.demand_run_keys(app, resumed) is False
            await pilot.pause()
            app.screen.query_one("#key-input", Input).value = "fixture-typesafe-key"
            await pilot.press("enter")
            resumed.assert_called_once()
            assert home.demand_run_keys(app, resumed) is True

    asyncio.run(scenario())


def test_ollama_is_pickable_and_needs_no_key(monkeypatch, isolated_configuration):
    """A local model runs with only the data key; no LLM key prompt appears."""
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "fixture-fd-key")

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.press("m")
            picker = app.screen.query_one("#picker-list", OptionList)
            index = picker.get_option_index("qwen3:8b")
            assert not picker.get_option_at_index(index).disabled
            picker.highlighted = index
            await pilot.press("enter")
            assert os.environ["HEDGE_FUND_LLM_MODEL"] == "qwen3:8b"
            assert home.demand_run_keys(app, Mock()) is True
            await pilot.press("k")
            await pilot.pause()
            assert isinstance(app.screen, home.HomeScreen)
            assert not isolated_configuration.exists()

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


def test_home_offers_paper_trading_first_and_an_empty_paper_screen_builds():
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(100, 35)) as pilot:
            menu = app.screen.query_one("#home-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["paper", "backtest"]
            assert menu.highlighted == 0
            await pilot.press("enter")
            assert isinstance(app.screen, paper.PaperScreen)
            rail = app.screen.query_one("#paper-menu", OptionList)
            assert [rail.get_option_at_index(i).id for i in range(rail.option_count)] == ["build"]
            assert "No funds yet" in render(app.screen.query_one("#detail-body", Static).content)
            # h/r/s have nothing to act on; enter still opens the builder.
            assert not app.screen.check_action("halt", ()) and not app.screen.check_action("sessions", ())
            await pilot.press("enter")
            assert isinstance(app.screen, builder.BuilderScreen) and app.screen.mode == "paper"
            assert "BUILD A FUND" in render(app.screen.query_one(".rail-title", Static).content)
            assert app.screen.STEP_IDS[-1] == "step-tickers"
            await pilot.press("escape")
            assert isinstance(app.screen, paper.PaperScreen)
            await pilot.press("escape")
            assert isinstance(app.screen, home.HomeScreen)
            menu.highlighted = menu.get_option_index("backtest")
            await pilot.press("enter")
            assert isinstance(app.screen, funds.FundSelectScreen)
    asyncio.run(scenario())
