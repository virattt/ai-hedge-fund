"""The backtest board's running numbers against the engine's final metrics."""

import asyncio

import pytest
from textual.widgets import ContentSwitcher, Static

from hedge_fund.backtesting import (
    DailyValuation,
    FundBacktestResult,
    performance_metrics,
)
from hedge_fund.brokers.models import Fill
from hedge_fund.tui import backtest
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import make_cycle, make_session, make_signal, render


@pytest.mark.parametrize("size", [(120, 45), (80, 24)])
def test_backtest_daily_board_matches_final_metrics_and_uses_fill_dates(size, tmp_path):
    record = make_cycle(make_signal())
    record.execution_as_of = "2025-01-16"
    record.fills = [Fill(ticker="TEST", side="buy", quantity=1, price=100)]
    dates = ["2025-01-15", "2025-01-16", "2025-01-17"]
    nav = [100000, 100000, 90000]
    benchmark_nav = [100000, 101000, 102000]
    metrics = performance_metrics(100000, dates, nav, benchmark_nav, [record])
    sessions = [make_session(dates[0]), make_session(dates[1], executed=record), make_session(dates[2], nav=90000)]
    result = FundBacktestResult(fund=record.fund, start=dates[0], end=dates[-1], rebalance="weekly",
                                benchmark="SPY", universe=["TEST"], capital=100000, dates=dates,
                                nav=nav, benchmark_nav=benchmark_nav, records=sessions, metrics=metrics)
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=size) as pilot:
            await app.push_screen(backtest.BacktestScreen(record.spec))
            screen = app.screen
            screen.query_one("#bt-panes", ContentSwitcher).current = "bt-run"
            screen._begin_replay(record.spec, dict(zip(dates, [100, 101, 102])), 3)
            screen._board_valuation(DailyValuation(as_of=dates[0], nav=nav[0], benchmark_nav=benchmark_nav[0]))
            screen._board_tick(record)
            for i in (1, 2):
                screen._board_valuation(DailyValuation(as_of=dates[i], nav=nav[i], benchmark_nav=benchmark_nav[i]))
            await pilot.pause()
            before = {name: render(screen.query_one(f"#stat-{name}", Static).content)
                      for name in ("nav", "return", "sharpe", "dd")}
            assert screen._tape[0][0] == "2025-01-16"
            assert "session 3/3" in render(screen.query_one("#cycle-line", Static).content)
            screen._finish(result, tmp_path / "backtest.json")
            after = {name: render(screen.query_one(f"#stat-{name}", Static).content) for name in before}
            assert before == after
            phase = render(screen.query_one("#phase-line", Static).content)
            assert "1 executed cycles" in phase and "pending" not in phase
            tape = render(screen.query_one("#tape", Static).content)
            # Reopening the saved file lands on the same view, pixel for pixel
            # where it matters: the tiles, the header, the tape.
            path = tmp_path / "saved.json"
            path.write_text(result.model_dump_json())
            await app.push_screen(backtest.BacktestScreen(record.spec, saved=path))
            await pilot.pause()
            reopened = app.screen
            assert reopened is not screen and reopened._phase == "done"
            assert reopened.query_one("#bt-panes", ContentSwitcher).current == "bt-run"
            assert {name: render(reopened.query_one(f"#stat-{name}", Static).content)
                    for name in after} == after
            assert render(reopened.query_one("#phase-line", Static).content) == phase
            assert render(reopened.query_one("#tape", Static).content) == tape
            assert reopened._tape[0][0] == "2025-01-16"
            assert str(path) in render(reopened.query_one("#result-summary", Static).content)
            assert "hidden" not in reopened.query_one("#curve-box").classes
            await pilot.press("escape")
            assert app.screen is screen
    asyncio.run(scenario())


def test_tape_rows_use_the_execution_date_and_the_position_after_the_fill():
    record = make_cycle(make_signal())
    record.fills = [Fill(ticker="TEST", side="buy", quantity=3, price=100)]
    record.positions = {"TEST": 3}
    assert backtest.tape_rows([record]) == [(record.as_of, record.fills[0], 3)]
    record.execution_as_of = "2025-01-16"
    assert backtest.tape_rows([record]) == [("2025-01-16", record.fills[0], 3)]
    assert backtest.tape_rows([]) == []


def test_reopening_an_unreadable_result_fails_loud(tmp_path):
    record = make_cycle(make_signal())
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test() as pilot:
            await app.push_screen(backtest.BacktestScreen(record.spec, saved=path))
            await pilot.pause()
            assert app.screen._phase == "failed"
            assert "✗" in render(app.screen.query_one("#phase-line", Static).content)
    asyncio.run(scenario())


def test_browse_decisions_lists_only_sessions_that_acted_and_opens_the_report(tmp_path):
    from hedge_fund.tui.session_report import SessionReportScreen
    from hedge_fund.tui.test_report import make_halved_decision
    from textual.widgets import OptionList
    record = make_cycle(make_signal())
    record.fills = [Fill(ticker="TEST", side="buy", quantity=1, price=100)]
    dates = ["2025-01-15", "2025-01-16", "2025-01-17"]
    decision = make_halved_decision(dates[1])
    nav, benchmark_nav = [100000, 89700, 90000], [100000, 101000, 102000]
    sessions = [make_session(dates[0]),
                make_session(dates[1], decision=decision, nav=nav[1]),
                make_session(dates[2], executed=record, nav=nav[2])]
    result = FundBacktestResult(fund=record.fund, start=dates[0], end=dates[-1], rebalance="weekly",
                                benchmark="SPY", universe=["TEST"], capital=100000, dates=dates,
                                nav=nav, benchmark_nav=benchmark_nav, records=sessions,
                                metrics=performance_metrics(100000, dates, nav, benchmark_nav, [record]))
    path = tmp_path / "saved.json"
    path.write_text(result.model_dump_json())

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(backtest.BacktestScreen(record.spec, saved=path))
            await pilot.pause()
            results = app.screen
            menu = results.query_one("#bt-done-menu", OptionList)
            assert app.focused is menu and menu.highlighted == 0
            await pilot.press("enter")
            await pilot.pause()
            browser = app.screen
            assert isinstance(browser, backtest.BacktestDecisionsScreen)
            rail = browser.query_one("#pf-sessions", OptionList)
            rows = [render(rail.get_option_at_index(i).prompt) for i in range(rail.option_count)]
            assert len(rows) == 2 and dates[0] not in "".join(rows)   # the valuation day is left out
            assert dates[2] in rows[0] and "1 fill" in rows[0]           # newest first
            assert dates[1] in rows[1] and "halved" in rows[1]
            assert "2 of 3 sessions" in render(browser.query_one("#pf-head", Static).content)
            overview = render(browser.query_one("#detail-pane", Static).content)
            assert "EXECUTED" in overview and "execution session" in overview
            await pilot.press("down")
            await pilot.pause()
            assert "HALVED" in render(browser.query_one("#detail-pane", Static).content)
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, SessionReportScreen)
            nav_rail = app.screen.query_one("#report-nav", OptionList)
            prompts = [render(nav_rail.get_option_at_index(i).prompt) for i in range(nav_rail.option_count)]
            assert any("Risk limits (1)" in p for p in prompts)
            await pilot.press("escape")
            assert app.screen is browser
            await pilot.press("escape")
            assert app.screen is results
    asyncio.run(scenario())
