"""Saved backtest results: research/<fund>-<start>-<end>-<stamp>.json.

Both `aihf backtest` and the app write here through `save_result`; the app's
mandate picker reads the directory back through the functions below. Results
are disposable research artifacts, never inputs to a run.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hedge_fund import paths
from hedge_fund.backtesting.fund import FundBacktestResult


def save_result(result: FundBacktestResult) -> Path:
    """Write *result* where the mandate picker's history will find it."""
    paths.RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = paths.RESEARCH_DIR / f"{result.fund}-{result.start}-{result.end}-{stamp}.json"
    path.write_text(result.model_dump_json(indent=2))
    return path


def summarize(path: Path, mtime: float) -> dict | None:
    """One saved backtest result as the light summary the history pane
    renders. None if the file is unreadable or not a backtest."""
    try:
        d = json.loads(path.read_text())
        if not isinstance(d, dict) or "metrics" not in d:
            return None
        m = d["metrics"]
        return {
            "kind": "backtest", "mtime": mtime, "fund": d.get("fund", ""),
            "universe": d.get("universe", []),
            "start": d.get("start", ""), "end": d.get("end", ""),
            "benchmark": d.get("benchmark", "SPY"),
            "total": m["total_return_pct"],
            "annualized": m["annualized_return_pct"],
            "sharpe": m["sharpe_ratio"], "maxdd": m["max_drawdown_pct"],
            "benchret": m["benchmark_return_pct"],
            "excess": m["excess_return_pct"], "n_cycles": m["n_cycles"],
        }
    except (json.JSONDecodeError, KeyError, OSError, TypeError, UnicodeError):
        return None


def receipts(name: str) -> list[Path]:
    """Every saved backtest of a mandate, newest first. Filenames start with
    the mandate's name, but names can be prefixes of each other, so the
    result's own `fund` field is what decides."""
    found = []
    for p in paths.RESEARCH_DIR.glob(f"{name}-*.json"):
        summary = summarize(p, 0.0)
        if summary is not None and summary["fund"] == name:
            found.append(p)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def last_universe(name: str) -> list[str] | None:
    """The tickers this mandate was last backtested over — the ticker inputs
    prefill from it, so a returning user just presses enter."""
    for path in receipts(name):
        summary = summarize(path, 0.0)
        if summary and summary["universe"]:
            return summary["universe"]
    return None


def last_score(name: str) -> tuple[float, float, str] | None:
    """The mandate's most recent backtest result, if any: (total return,
    excess return, benchmark). A quiet scoreboard on each slot."""
    for path in receipts(name):
        summary = summarize(path, 0.0)
        if summary:
            return (summary["total"], summary["excess"], summary["benchmark"])
    return None
