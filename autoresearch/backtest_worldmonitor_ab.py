"""
Run A/B portfolio backtest with World Monitor overlay OFF vs ON.

Usage:
  poetry run python -m autoresearch.backtest_worldmonitor_ab
  poetry run python -m autoresearch.backtest_worldmonitor_ab --start 2025-08-01 --end 2026-03-07 --weights oos
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    SECTOR_OOS_SHARPE,
    SECTOR_SHARPE,
    compute_portfolio_metrics,
    portfolio_values_to_returns,
    run_sector_backtest,
)


@dataclass
class ABRunResult:
    label: str
    metrics: dict
    sector_count: int


def _weights_for_mode(mode: str, sectors: list[str]) -> dict[str, float]:
    if mode == "equal":
        return {s: 1.0 / len(sectors) for s in sectors}
    if mode == "sharpe":
        values = {s: max(SECTOR_SHARPE.get(s, 0), 0.01) for s in sectors}
    else:
        values = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in sectors}
    total = sum(values.values())
    return {s: values[s] / total for s in sectors}


def _run_once(
    *,
    weights_mode: str,
    exclude: set[str],
    start: str | None,
    end: str | None,
    cost_bps: float,
    wm_enabled: bool,
    label: str,
) -> ABRunResult:
    sectors = [s for s in SECTOR_CONFIG if s not in exclude]
    returns_by_sector: dict[str, pd.Series] = {}

    for sector in sectors:
        mod, path = SECTOR_CONFIG[sector]
        try:
            pv, _metrics, _ = run_sector_backtest(
                mod,
                path,
                start=start,
                end=end,
                cost_bps=cost_bps,
                wm_enabled=wm_enabled,
            )
        except Exception:
            continue
        returns_by_sector[sector] = portfolio_values_to_returns(pv)

    if not returns_by_sector:
        return ABRunResult(label=label, metrics={"sharpe": 0.0, "sortino": 0.0, "max_dd": 0.0, "total_return_pct": 0.0}, sector_count=0)

    aligned = pd.DataFrame(returns_by_sector).dropna(how="all").ffill().bfill().fillna(0)
    w = _weights_for_mode(weights_mode, list(returns_by_sector.keys()))
    port_ret = pd.Series(0.0, index=aligned.index)
    for sector in returns_by_sector:
        port_ret = port_ret + w[sector] * aligned[sector].reindex(port_ret.index).fillna(0)

    return ABRunResult(label=label, metrics=compute_portfolio_metrics(port_ret), sector_count=len(returns_by_sector))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", choices=["equal", "sharpe", "oos"], default="oos")
    parser.add_argument("--exclude", type=str, default="")
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    parser.add_argument("--cost-bps", type=float, default=0)
    parser.add_argument(
        "--output-json",
        type=str,
        default="autoresearch/logs/worldmonitor_ab_report.json",
        help="Where to save the A/B report JSON",
    )
    args = parser.parse_args()

    exclude = {s.strip() for s in args.exclude.split(",") if s.strip()}
    baseline = _run_once(
        weights_mode=args.weights,
        exclude=exclude,
        start=args.start,
        end=args.end,
        cost_bps=args.cost_bps,
        wm_enabled=False,
        label="wm_off",
    )
    wm_on = _run_once(
        weights_mode=args.weights,
        exclude=exclude,
        start=args.start,
        end=args.end,
        cost_bps=args.cost_bps,
        wm_enabled=True,
        label="wm_on",
    )

    delta = {
        "sharpe": wm_on.metrics["sharpe"] - baseline.metrics["sharpe"],
        "sortino": wm_on.metrics["sortino"] - baseline.metrics["sortino"],
        "max_dd": wm_on.metrics["max_dd"] - baseline.metrics["max_dd"],
        "total_return_pct": wm_on.metrics["total_return_pct"] - baseline.metrics["total_return_pct"],
    }
    report = {
        "config": {
            "weights": args.weights,
            "exclude": sorted(exclude),
            "start": args.start,
            "end": args.end,
            "cost_bps": args.cost_bps,
        },
        "baseline": {"label": baseline.label, "metrics": baseline.metrics, "sector_count": baseline.sector_count},
        "wm_on": {"label": wm_on.label, "metrics": wm_on.metrics, "sector_count": wm_on.sector_count},
        "delta": delta,
    }

    print("World Monitor A/B")
    print("-" * 40)
    print("Baseline:", baseline.metrics)
    print("WM On:   ", wm_on.metrics)
    print("Delta:   ", delta)

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

