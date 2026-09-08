"""File handling for validation \u2014 kept separate from the statistics.

The engine and stats modules never touch a filesystem; this is the only
place that reads FundBacktestResult JSON off disk, mirroring how backtests
are written out (`result.model_dump_json()`, see tui/app.py and run.py).
"""

from __future__ import annotations

from pathlib import Path

from hedge_fund.backtesting.fund import FundBacktestResult


def load_backtest_result(path: str | Path) -> FundBacktestResult:
    """Read one serialized FundBacktestResult JSON file (`model_dump_json()`
    output) back into a model. Fails loud if the file is missing or the JSON
    doesn't match the schema \u2014 same fail-loud convention as the rest of the
    project."""
    text = Path(path).read_text()
    return FundBacktestResult.model_validate_json(text)


def load_candidates(paths: dict[str, str | Path]) -> dict[str, FundBacktestResult]:
    """Load a named set of backtest result files, e.g.::

        candidates = load_candidates({
            "pead": "funds/pead-backtest-2024-06-21.json",
            "buffett": "funds/buffett-backtest-2024-06-21.json",
        })
        report = validate_candidates(candidates)
    """
    return {name: load_backtest_result(path) for name, path in paths.items()}
