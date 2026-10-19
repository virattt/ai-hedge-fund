"""The mandate library: both pickers, unavailable files, and backtest history."""

import asyncio
import json
import os

import pytest
import yaml
from textual.widgets import ContentSwitcher, Input, OptionList, Static

from hedge_fund import paths
from hedge_fund.backtesting import research
from hedge_fund.tui import backtest, funds
from hedge_fund.tui.app import HedgeFundApp
from hedge_fund.tui.fixtures import make_spec, render


def test_both_pickers_disable_only_invalid_configurations():
    files = {"old.yaml": "name: old\n", "broken.yaml": "[oops",
             "mixed.yaml": yaml.safe_dump(make_spec().model_dump()),
             "valid.yaml": yaml.safe_dump(make_spec(["pead"], "ready").model_dump())}
    for name, content in files.items():
        (paths.MANDATES_DIR / name).write_text(content)

    async def scenario():
        app = HedgeFundApp()
        async with app.run_test(size=(140, 50)) as pilot:
            await app.push_screen(funds.FundSelectScreen())
            menu = app.screen.query_one("#select-menu", OptionList)
            assert menu.option_count == 4
            prompts = [render(menu.get_option_at_index(i).prompt) for i in range(4)]
            assert any("old.yaml" in p and "older format" in p for p in prompts)
            assert sum(menu.get_option_at_index(i).disabled for i in range(4)) == 2
            await pilot.press("enter")
            assert isinstance(app.screen, backtest.BacktestScreen)
            assert app.screen.query_one("#bt-panes", ContentSwitcher).current == "bt-dates"
            assert not app.screen.query_one("#bt-tickers", Input).disabled
            await pilot.press("escape")
            assert isinstance(app.screen, funds.FundSelectScreen)
            await app.push_screen(backtest.BacktestScreen())
            menu = app.screen.query_one("#fund-list", OptionList)
            assert menu.option_count == 4
            assert sum(menu.get_option_at_index(i).disabled for i in range(4)) == 2
    asyncio.run(scenario())
    assert {p.name: p.read_text() for p in paths.MANDATES_DIR.glob("*.yaml")} == files


def test_all_invalid_funds_do_not_crash_home_picker():
    (paths.MANDATES_DIR / "old.yaml").write_text("name: old\n")
    async def scenario():
        app = HedgeFundApp()
        async with app.run_test() as pilot:
            await app.push_screen(funds.FundSelectScreen())
            assert "Saved mandates are unavailable" in render(app.screen.query_one("#detail-body", Static).content)
    asyncio.run(scenario())


@pytest.mark.parametrize("newest_version", [None, 2])
def test_latest_backtest_sets_headline_regardless_of_version(newest_version):
    spec = make_spec(["pead"])
    receipt = {"fund": "test", "start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5,
                           "sharpe_ratio": 2, "max_drawdown_pct": .1,
                           "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    if newest_version is None:
        receipt["schema_version"] = 2
    older = paths.RESEARCH_DIR / "test-2025-01-01-2025-02-01-older.json"
    older.write_text(json.dumps(receipt))
    os.utime(older, (1000, 1000))
    original = older.read_bytes()
    older_summary = research.summarize(older, 1000)
    assert research.last_score("test") == (.5, .4, "SPY")
    assert "LATEST BACKTEST" in render(funds._fund_detail(spec, [older_summary]))

    receipt.pop("schema_version", None)
    if newest_version is not None:
        receipt["schema_version"] = newest_version
    receipt["metrics"].update(total_return_pct=.3, excess_return_pct=.2)
    newer = paths.RESEARCH_DIR / "test-2025-01-01-2025-02-01-newer.json"
    newer.write_text(json.dumps(receipt))
    os.utime(newer, (2000, 2000))
    newer_summary = research.summarize(newer, 2000)
    assert research.last_score("test") == (.3, .2, "SPY")
    detail = render(funds._fund_detail(spec, [newer_summary, older_summary]))
    headline = detail.split("\nBACKTESTS")[0]
    assert "LATEST BACKTEST" in headline and "30.0%" in headline
    assert older.read_bytes() == original
