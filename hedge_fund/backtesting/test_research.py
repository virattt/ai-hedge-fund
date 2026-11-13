"""The saved-results index under research/."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import UUID

import pytest

from hedge_fund import paths
from hedge_fund.backtesting import research
from hedge_fund.backtesting.fund import FundBacktestMetrics, FundBacktestResult


@pytest.fixture
def research_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESEARCH_DIR", tmp_path)
    return tmp_path


def test_research_history_is_matched_on_the_fund_field_not_the_filename_prefix(research_dir):
    """`alpha` must not pick up `alpha-2`'s backtests: names can be prefixes."""
    receipt = {"fund": "alpha-2", "start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5, "sharpe_ratio": 2,
                           "max_drawdown_pct": .1, "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    (research_dir / "alpha-2-2025-01-01-2025-02-01-x.json").write_text(json.dumps(receipt))
    assert research.receipts("alpha") == []
    assert len(research.receipts("alpha-2")) == 1
    assert research.last_score("alpha") is None

@pytest.fixture
def fixed_clock(monkeypatch):
    class Clock:
        @classmethod
        def now(cls):
            return datetime(2026, 11, 13, 12, 0, 0)

    monkeypatch.setattr(research, "datetime", Clock)


def result_for(ticker):
    return FundBacktestResult(
        fund="alpha",
        start="2025-01-01",
        end="2025-02-01",
        rebalance="weekly",
        benchmark="SPY",
        universe=[ticker],
        capital=1000.0,
        dates=[],
        nav=[],
        benchmark_nav=[],
        records=[],
        metrics=FundBacktestMetrics(
            total_return_pct=0,
            annualized_return_pct=0,
            sharpe_ratio=0,
            max_drawdown_pct=0,
            benchmark_return_pct=0,
            excess_return_pct=0,
            n_cycles=0,
            n_orders=0,
        ),
    )


def test_saving_again_in_the_same_second_preserves_both_results(research_dir, fixed_clock):
    first = result_for("AAPL")
    first_path = research.save_result(first)
    original = first_path.read_bytes()
    second = result_for("MSFT")
    second_path = research.save_result(second)

    assert first_path != second_path
    assert first_path.read_bytes() == original
    assert FundBacktestResult.model_validate_json(second_path.read_text()) == second
    assert set(research.receipts("alpha")) == {first_path, second_path}
    assert all(research.summarize(path, 0)["fund"] == "alpha" for path in (first_path, second_path))


def test_concurrent_saves_in_the_same_second_keep_every_result(research_dir, fixed_clock):
    results = [result_for(ticker) for ticker in ("AAPL", "MSFT", "TEST", "SPY")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(research.save_result, results))

    assert len(set(saved)) == len(results)
    assert set(research.receipts("alpha")) == set(saved)
    assert [FundBacktestResult.model_validate_json(path.read_text()) for path in saved] == results


def test_a_name_collision_never_truncates_an_existing_receipt(research_dir, fixed_clock, monkeypatch):
    monkeypatch.setattr(research, "uuid4", lambda: UUID(int=0), raising=False)
    path = research.save_result(result_for("AAPL"))
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        research.save_result(result_for("MSFT"))
    assert path.read_bytes() == original
