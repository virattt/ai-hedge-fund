import asyncio
from threading import Event
from unittest.mock import Mock

from textual.widgets import Input, OptionList, Static

from hedge_fund.research import Company, CurrentBrief
from hedge_fund.test_research import BRIEF
from hedge_fund.tui import home, paper_research
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import render


def test_home_research_searches_freely_then_loads_one_explicit_ticker():
    client = Mock()
    client.search.return_value = [
        Company(ticker="NBIS", name="Example Company", direct_research=True),
        Company(ticker="OTHER", name="Another Company", direct_research=False),
    ]
    client.read.side_effect = [CurrentBrief.model_validate(BRIEF), None]

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(100, 30)) as pilot:
            app.research_client = client
            menu = app.screen.query_one("#home-menu", OptionList)
            menu.highlighted = menu.get_option_index("research")
            await pilot.press("enter")
            screen = app.screen
            assert isinstance(screen, paper_research.PaperResearchScreen)
            client.search.assert_not_called()
            client.read.assert_not_called()
            search = screen.query_one("#research-search", Input)
            assert search.has_focus
            search.value = "Example"
            await pilot.press("enter")
            await screen.workers.wait_for_complete()
            client.search.assert_called_once_with("Example")
            client.read.assert_not_called()
            menu = screen.query_one("#report-nav", OptionList)
            assert menu.has_focus
            assert "Research available" in render(menu.get_option_at_index(0).prompt)
            assert "No direct research" in render(menu.get_option_at_index(1).prompt)
            await pilot.press("enter")
            await screen.workers.wait_for_complete()
            client.read.assert_called_once()
            assert client.read.call_args.args == ("NBIS",)
            detail = render(screen.query_one("#detail-pane", Static).content)
            assert any(span.style.link == "https://example.com/research" for span in screen.query_one("#detail-pane", Static).content.spans)
            for text in ("Example Investor · neutral", "source coverage: partial", "Published: unknown",
                         "Risk · unknown", "Catalyst · pending", "Not assessed.", "The source is partial.",
                         "4", "2 risks, 1 catalysts", "reviewed compact case missing", "get_beliefs"):
                assert text in detail
            await pilot.press("down")
            assert "Example Investor" not in render(screen.query_one("#detail-pane", Static).content)
            assert client.read.call_count == 1
            await pilot.press("enter")
            await screen.workers.wait_for_complete()
            assert "No released direct company research" in render(screen.query_one("#detail-pane", Static).content)
            await pilot.press("escape")
            assert isinstance(app.screen, home.HomeScreen)
    asyncio.run(scenario())


def test_research_key_uses_existing_masked_credential_prompt(monkeypatch, isolated_configuration):
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test() as pilot:
            screen = paper_research.PaperResearchScreen()
            await app.push_screen(screen)
            await pilot.press("ctrl+k")
            assert isinstance(app.screen, home.KeyPromptScreen)
            entry = app.screen.query_one("#key-input", Input)
            assert entry.password
            entry.value = "fixture-beliefstate-secret"
            await pilot.press("enter")
            assert app.screen is screen
            assert isolated_configuration.read_text() == "BELIEFSTATE_API_KEY=fixture-beliefstate-secret\n"
            assert "fixture-beliefstate-secret" not in render(screen.query_one("#detail-pane", Static).content)
    asyncio.run(scenario())


def test_leaving_live_research_cancels_its_preflight_without_stale_ui():
    started, release, finished = Event(), Event(), Event()
    client = Mock()
    def read(ticker, *, cancelled):
        started.set()
        assert release.wait(5)
        try:
            assert cancelled()
            return None
        finally:
            finished.set()
    client.read.side_effect = read

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(80, 24)) as pilot:
            app.research_client = client
            screen = paper_research.PaperResearchScreen(tickers=["NBIS"])
            await app.push_screen(screen)
            await pilot.press("enter", "enter")
            try:
                assert await asyncio.to_thread(started.wait, 5)
                client.read.assert_called_once()
                await pilot.press("escape")
                assert isinstance(app.screen, home.HomeScreen)
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 5)
    asyncio.run(scenario())
