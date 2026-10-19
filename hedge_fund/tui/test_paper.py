"""The paper screens: approval step, kill switch, history, live prints, runner start/stop."""

import asyncio
import os
from datetime import datetime
from unittest.mock import Mock

import pytest
import yaml
from textual.widgets import ContentSwitcher, Input, OptionList, Static

from hedge_fund import paths
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.paper import deploy, Ledger, load_deployed, PID_FILE
from hedge_fund.tui import backtest, funds, paper, paper_view, report
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import (
    executed_and_decided,
    make_minute_spec,
    make_quote,
    make_session,
    make_spec,
    render,
)


@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_all_modes_can_be_backtested_and_paper_traded(mode, size):
    spec = make_spec()
    spec.strategies[0].blend.mode = mode
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(backtest.BacktestScreen(spec))
            assert app.screen.query_one("#bt-panes", ContentSwitcher).current == "bt-dates"
            assert not app.screen.query_one("#bt-tickers", Input).disabled
            await pilot.press("escape")
            directory = deploy("test", spec, ["TEST"], root=paths.PAPER_DIR)
            await app.push_screen(paper.PaperScreen())
            menu = app.screen.query_one("#paper-menu", OptionList)
            assert menu.highlighted == menu.get_option_index("paper:0")
            assert app.screen.check_action("halt", ()) and app.screen.check_action("sessions", ())
            detail = render(app.screen.query_one("#detail-body", Static).content)
            assert "● new" in detail and "NEXT RUN" in detail
            assert load_deployed(directory).spec == spec
    asyncio.run(scenario())


def test_paper_screen_shows_live_prints_when_they_arrive(monkeypatch):
    spec = make_spec(["pead"], "alpha")
    directory = deploy("alpha", spec, ["TEST"], root=paths.PAPER_DIR)
    record, _ = executed_and_decided()
    Ledger(directory).append(make_session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10}, marks={"TEST": 100}))
    asked: list = []

    def fetch(tickers):
        asked.append(tickers)
        return {"TEST": make_quote("TEST", 120, datetime.now(NEW_YORK).isoformat())}
    monkeypatch.setattr(paper, "fetch_snapshots", fetch)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(paper.PaperScreen())
            for _ in range(50):  # the prints arrive off-thread
                await pilot.pause(0.05)
                detail = render(app.screen.query_one("#detail-body", Static).content)
                if "Live" in detail:
                    break
            assert asked and asked[-1] == ["TEST"] and "$101,200" in detail
    asyncio.run(scenario())


def test_paper_screen_runs_through_the_approval_step(monkeypatch):
    spec = make_spec(["pead"], "alpha")
    directory = deploy("alpha", spec, ["TEST"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)
    record, decided = executed_and_decided()
    ledger.append(make_session("2025-01-17", decision=decided, nav=100000))
    due = {"value": "2025-01-21"}
    monkeypatch.setattr(paper, "FDClient", lambda: Mock(__enter__=lambda s: s, __exit__=lambda s, *a: None))
    monkeypatch.setattr(paper, "next_session", lambda data, benchmark, last: due["value"])
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "x")
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    started: list = []
    monkeypatch.setattr(paper.RunSessionScreen, "_run", lambda self: started.append(self._directory))

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(paper.PaperScreen())
            screen = app.screen
            detail = render(screen.query_one("#detail-body", Static).content)
            assert "NEXT RUN" in detail and "execute the 2025-01-20 decision" in detail
            assert "TEST +25%" in detail and "SESSIONS" in detail and "2025-01-17" in detail
            await pilot.press("enter")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, paper.RunConfirmScreen)
            body = render(modal.query_one("#run-body", Static).content)
            assert "Execute the 2025-01-20 decision at the 2025-01-21 close" in body
            assert "TEST +25%" in body and "first session of the week" in body
            assert modal.check_action("confirm", ())
            await pilot.press("escape")  # say no: nothing runs
            assert app.screen is screen and started == []
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # say yes
            await pilot.pause()
            assert isinstance(app.screen, paper.RunSessionScreen) and started == [directory]
            app.screen._phase = "done"
            await pilot.press("escape")
            assert app.screen is screen
            # Nothing due: the modal says when the next close is and offers
            # to run the last session again; enter does that, esc does nothing.
            due["value"] = None
            await pilot.press("enter")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, paper.RunConfirmScreen) and modal.check_action("confirm", ())
            body = render(modal.query_one("#run-body", Static).content)
            assert "Up to date through 2025-01-17" in body and "Run 2025-01-17 again?" in body
            assert "run again" in render(modal.query_one("#run-keys", Static).content)
            await pilot.press("escape")
            assert app.screen is screen and started == [directory]
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, paper.RunSessionScreen) and app.screen._redo
            assert started == [directory, directory]
    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
@pytest.mark.parametrize("what", ["executed", "decided", "both", "neither"])
def test_session_report_separates_the_executed_cycle_from_the_new_decision(size, what):
    record, decided = executed_and_decided()
    session = make_session("2025-01-20",
                       executed=record if what in ("executed", "both") else None,
                       decision=decided if what in ("decided", "both") else None)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(paper.SessionReportScreen("alpha", session))
            screen = app.screen
            await pilot.pause()
            head = render(screen.query_one("#report-head", Static).content)
            footer = render(screen.query_one("#report-foot", Static).content)
            menu = screen.query_one("#report-nav", OptionList)
            ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
            assert "alpha" in head and "session 2025-01-20" in head
            assert "NAV $100,000.00" in footer
            if what in ("executed", "both"):
                assert "executed the 2025-01-15 decision (refreshed 2025-01-19)" in head
                assert "x:sec:orders" in ids and "x:sec:portfolio" in ids
                menu.highlighted = menu.get_option_index("x:sec:portfolio")
                await pilot.pause()
                assert "Target net" in render(screen.query_one("#detail-pane", Static).content)
            if what in ("decided", "both"):
                assert "executes next session" in head
                assert "d:sec:portfolio" in ids and "d:sec:orders" not in ids
                menu.highlighted = menu.get_option_index("d:sec:portfolio")
                await pilot.pause()
                detail = render(screen.query_one("#detail-pane", Static).content)
                assert "PROPOSED ALLOCATIONS" in detail and "TEST: +25.00%" in detail
            if what == "neither":
                assert "valuation only" in head
                assert ids == [None, "book"]
                menu.highlighted = menu.get_option_index("book")
                await pilot.pause()
                assert "flat — no positions" in render(screen.query_one("#detail-pane", Static).content)
    asyncio.run(scenario())


def test_paper_screen_works_the_kill_switch_and_sessions_reads_the_ledger(tmp_path):
    spec = make_spec(["pead"], "alpha")
    directory = deploy("alpha", spec, ["TEST"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(paper.PaperScreen())
            screen = app.screen
            menu = screen.query_one("#paper-menu", OptionList)
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["paper:0", "build"]
            assert "alpha" in render(menu.get_option("paper:0").prompt)
            detail = render(screen.query_one("#detail-body", Static).content)
            assert "● new" in detail and "mark the book at the latest completed close" in detail
            assert screen.check_action("halt", ()) and not screen.check_action("resume", ())

            await pilot.press("h")  # no prompt: halts at once
            await pilot.pause()
            assert app.screen is screen
            assert ledger.halted() == paper_view.APP_HALT
            assert menu.highlighted == menu.get_option_index("paper:0")  # re-highlighted after the reload
            detail = render(screen.query_one("#detail-body", Static).content)
            assert "■ halted" in detail and "r to resume" in detail and paper_view.APP_HALT not in detail
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
            record, decided = executed_and_decided()
            first = make_session("2025-01-17", decision=decided, nav=100000)
            second = make_session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10},
                              marks={"TEST": 100}, prev_hash=first.hash)
            ledger.append(first)
            ledger.append(second)
            await app.push_screen(paper.SessionReportScreen("alpha", first))
            await pilot.press("escape")
            await pilot.pause()
            detail = render(screen.query_one("#detail-body", Static).content)
            assert "● live" in detail and "mark the book" in detail and "2025-01-17 · 2 sessions" in detail
            assert "SESSIONS" in detail and "2025-01-20" in detail and "1 fill" in detail
            assert "+1.0%" in render(menu.get_option("paper:0").prompt)

            await pilot.press("s")
            sessions_screen = app.screen
            assert isinstance(sessions_screen, paper.SessionsScreen)
            assert "last session 2025-01-20" in render(sessions_screen.query_one("#pf-status", Static).content)
            assert "+1.00%" in render(sessions_screen.query_one("#stat-return", Static).content)
            sessions = sessions_screen.query_one("#pf-sessions", OptionList)
            rows = [render(sessions.get_option_at_index(i).prompt) for i in range(sessions.option_count)]
            assert rows[0].startswith(" 2025-01-20") and "1 fill" in rows[0]
            assert rows[1].startswith(" 2025-01-17") and "decided" in rows[1]
            overview = render(sessions_screen.query_one("#detail-pane", Static).content)
            assert "EXECUTED" in overview and "decision from 2025-01-15" in overview
            await pilot.press("enter")
            assert isinstance(app.screen, paper.SessionReportScreen)
            assert "executed the 2025-01-15 decision" in render(app.screen.query_one("#report-head", Static).content)
            await pilot.press("escape")
            await pilot.press("escape")
            assert app.screen is screen

            # d deletes the fund — ledger, book, definition and backtests — after a yes.
            (paths.MANDATES_DIR / "alpha.yaml").write_text(yaml.safe_dump(spec.model_dump()))
            await pilot.press("d")
            modal = app.screen
            assert isinstance(modal, funds.ConfirmWipeScreen)
            manifest = render(modal.query_one("#confirm-files", Static).content)
            assert "2 sessions of ledger" in manifest and "alpha.yaml" in manifest and "name is free again" in manifest
            await pilot.press("escape")  # no
            assert app.screen is screen and directory.exists()
            await pilot.press("d")
            await pilot.press("enter")  # yes
            await pilot.pause()
            assert app.screen is screen
            assert not directory.exists() and not (paths.MANDATES_DIR / "alpha.yaml").exists()
            assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ["build"]
            assert not screen.check_action("delete", ()) and not screen.check_action("halt", ())
    asyncio.run(scenario())


def test_paper_screen_enter_starts_and_stops_a_minute_fund(monkeypatch):
    directory = deploy("fast", make_minute_spec(), ["TEST"], root=paths.PAPER_DIR)
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
    monkeypatch.setattr(paper, "spawn_runner", spawn)
    monkeypatch.setattr(paper, "stop_runner", stop)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(paper.PaperScreen())
            screen = app.screen
            menu = screen.query_one("#paper-menu", OptionList)
            assert "○ idle" in render(menu.get_option("paper:0").prompt)
            await pilot.press("enter")
            await pilot.pause()
            assert spawned == [directory] and app.screen is screen  # no approval modal for a runner
            assert "● running" in render(menu.get_option("paper:0").prompt)
            assert "● running" in render(screen.query_one("#detail-body", Static).content)
            await pilot.press("enter")
            await pilot.pause()
            assert stopped == [directory] and "○ idle" in render(menu.get_option("paper:0").prompt)
            # A halted minute fund neither starts nor stops.
            await pilot.press("h")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert spawned == [directory]
    asyncio.run(scenario())


def test_sessions_screen_groups_a_minute_funds_bars_by_day():
    directory = deploy("fast", make_minute_spec(), ["TEST"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)
    record, decided = executed_and_decided()
    chain = [make_session("2025-01-21T13:00:00", decision=decided, nav=100000)]
    chain.append(make_session("2025-01-21T13:05:00", executed=record, nav=101000, positions={"TEST": 10},
                          marks={"TEST": 100}, prev_hash=chain[-1].hash))
    chain.append(make_session("2025-01-22T13:00:00", nav=102000, positions={"TEST": 10}, marks={"TEST": 200},
                          prev_hash=chain[-1].hash))
    for r in chain:
        ledger.append(r)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(paper.SessionsScreen(directory))
            screen = app.screen
            await pilot.pause()
            assert "every 5m · 13:00–13:10 ET" in render(screen.query_one("#pf-head", Static).content)
            sessions = screen.query_one("#pf-sessions", OptionList)
            rows = [(sessions.get_option_at_index(i).id, render(sessions.get_option_at_index(i).prompt).strip())
                    for i in range(sessions.option_count)]
            assert rows[0][0] is None and rows[0][1].startswith("2025-01-22  +0.99%  1 bar")
            assert rows[1] == ("s:0", "13:00:00  +0.99%")
            assert rows[2][0] is None and rows[2][1].startswith("2025-01-21  +1.00%  2 bars")
            assert rows[3][0] == "s:1" and rows[3][1].startswith("13:05:00  +1.00%  1 fill")
            assert rows[4][0] == "s:2" and rows[4][1].startswith("13:00:00  +0.00%  decided")
            assert sessions.highlighted == 1  # the newest bar, not its heading
            assert "next bar's close" in render(report.session_overview(chain[0]))
    asyncio.run(scenario())
