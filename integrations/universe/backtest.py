"""Validation backtests: ranked universe vs baselines, with an LLM-free agent.

Compares three universes over the same window using the deterministic
light-cycle pipeline (rule-based analysts + vote-based sizing — the exact
code path the daemon trades on light cycles, zero LLM cost):

1. ``ranked``        — this system, built as of the backtest START date
                       (no look-ahead: factors and learnability only see
                       data before the window).
2. ``current``       — the legacy hardcoded 100-stock list from
                       ``v2/backtesting/__main__.py`` (stride-sampled when a
                       smaller --size is requested, to keep its sector mix).
3. ``dollar_volume`` — naive top-N by median daily dollar volume as of the
                       start date.

Caveat (printed with results): the candidate pool comes from today's asset
master, so historical builds carry survivorship bias; it affects the ranked
and dollar-volume variants comparably.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Sequence

import pandas as pd
from dateutil.relativedelta import relativedelta

from integrations.alpaca.light_cycle import run_light_analysis
from integrations.alpaca.strategy import LIGHT_ANALYSTS
from integrations.universe.config import UniverseConfig, load_universe_config
from src.backtesting.metrics import PerformanceMetricsCalculator
from src.backtesting.portfolio import Portfolio
from src.backtesting.trader import TradeExecutor
from src.backtesting.valuation import calculate_portfolio_value

logger = logging.getLogger(__name__)


@dataclass
class BacktestReport:
    name: str
    tickers: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float = 0.0
    total_return_pct: float = 0.0
    metrics: dict = field(default_factory=dict)
    spy_return_pct: float | None = None
    days: int = 0


# ---------------------------------------------------------------------------
# LLM-free backtest loop (light-cycle agent)
# ---------------------------------------------------------------------------

def _prefetch_closes(tickers: Sequence[str], start_date: str, end_date: str) -> pd.DataFrame:
    """One price fetch per ticker; returns a date x ticker close matrix."""
    from src.tools.api import get_prices

    closes: dict[str, pd.Series] = {}
    for ticker in tickers:
        try:
            rows = get_prices(ticker, start_date, end_date)
        except Exception as exc:
            logger.warning("Price prefetch failed for %s: %s", ticker, exc)
            continue
        if not rows:
            continue
        series = pd.Series(
            {pd.Timestamp(str(r.time)[:10]): float(r.close) for r in rows}
        ).sort_index()
        closes[ticker] = series
    return pd.DataFrame(closes)


def run_light_backtest(
    *,
    name: str,
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 100_000.0,
    margin_requirement: float = 0.5,
    light_analysts: Sequence[str] = LIGHT_ANALYSTS,
) -> BacktestReport:
    """Day-by-day backtest driving the light-cycle agent. No LLM calls."""
    report = BacktestReport(
        name=name,
        tickers=list(tickers),
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    price_start = (
        datetime.strptime(start_date, "%Y-%m-%d") - relativedelta(months=2)
    ).strftime("%Y-%m-%d")
    closes = _prefetch_closes(tickers, price_start, end_date)
    if closes.empty:
        logger.warning("[%s] No price data — skipping backtest", name)
        return report

    portfolio = Portfolio(
        tickers=list(tickers),
        initial_cash=initial_capital,
        margin_requirement=margin_requirement,
    )
    executor = TradeExecutor()
    perf = PerformanceMetricsCalculator()

    dates = pd.date_range(start_date, end_date, freq="B")
    portfolio_values = []

    for current_date in dates:
        window = closes.loc[closes.index <= current_date]
        if window.empty:
            continue
        latest = window.iloc[-1]
        current_prices = {
            t: float(latest[t]) for t in tickers if t in latest.index and pd.notna(latest[t])
        }
        if not current_prices:
            continue
        tradable = list(current_prices)

        date_str = current_date.strftime("%Y-%m-%d")
        lookback_start = (current_date - relativedelta(months=1)).strftime("%Y-%m-%d")

        try:
            agent_result = run_light_analysis(
                tickers=tradable,
                portfolio=portfolio.get_snapshot(),
                start_date=lookback_start,
                end_date=date_str,
                light_analysts=list(light_analysts),
                show_reasoning=False,
            )
        except Exception as exc:
            logger.warning("[%s] Light analysis failed on %s: %s", name, date_str, exc)
            continue

        decisions = agent_result.get("decisions", {})
        for ticker in tradable:
            decision = decisions.get(ticker, {})
            action = decision.get("action", "hold")
            quantity = decision.get("quantity", 0)
            if action != "hold" and quantity:
                executor.execute_trade(ticker, action, quantity, current_prices[ticker], portfolio)

        total_value = calculate_portfolio_value(portfolio, current_prices)
        portfolio_values.append({"Date": current_date, "Portfolio Value": total_value})
        print(
            f"[{name}] {date_str}  value=${total_value:,.2f}  "
            f"({(total_value / initial_capital - 1) * 100:+.2f}%)"
        )

    if not portfolio_values:
        return report

    report.days = len(portfolio_values)
    report.final_value = float(portfolio_values[-1]["Portfolio Value"])
    report.total_return_pct = (report.final_value / initial_capital - 1.0) * 100.0
    report.metrics = dict(perf.compute_metrics(portfolio_values))
    report.spy_return_pct = _spy_return(start_date, end_date)
    return report


def _spy_return(start_date: str, end_date: str) -> float | None:
    from src.tools.api import get_prices

    try:
        rows = get_prices("SPY", start_date, end_date)
    except Exception:
        return None
    if len(rows) < 2:
        return None
    return (float(rows[-1].close) / float(rows[0].close) - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Universe variants
# ---------------------------------------------------------------------------

def current_hardcoded_universe(size: int) -> list[str]:
    """Legacy 100-stock list; stride-sampled to preserve its sector mix."""
    from v2.backtesting.__main__ import TICKERS

    if size >= len(TICKERS):
        return list(TICKERS)
    stride = len(TICKERS) / size
    return [TICKERS[int(i * stride)] for i in range(size)]


def top_dollar_volume_universe(source, config: UniverseConfig, as_of: str, size: int) -> list[str]:
    """Naive baseline: top-N Stage-0 survivors by median daily dollar volume."""
    from integrations.universe.candidates import build_candidate_pool

    candidates = build_candidate_pool(source, config, as_of)
    ranked = sorted(
        candidates,
        key=lambda c: float((c.prices["close"] * c.prices["volume"]).tail(63).median()),
        reverse=True,
    )
    return [c.symbol for c in ranked[:size]]


def ranked_universe(source, config: UniverseConfig, as_of: str, size: int) -> list[str]:
    from integrations.universe.pipeline import build_universe

    snapshot = build_universe(source, replace(config, size=size), as_of, save=False)
    return list(snapshot.tickers)


# ---------------------------------------------------------------------------
# CLI entry (alpaca-fund universe backtest)
# ---------------------------------------------------------------------------

def _force_utf8_console() -> None:
    """The agents' progress output prints unicode glyphs that crash Windows
    cp1252 consoles mid-backtest; degrade gracefully instead."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def run_comparison_backtest(argv: list[str]) -> int:
    _force_utf8_console()
    parser = argparse.ArgumentParser(
        prog="alpaca-fund universe backtest",
        description="Compare the ranked universe against the legacy list and a top-dollar-volume baseline (LLM-free).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - relativedelta(months=3)).strftime("%Y-%m-%d"),
        help="Backtest start (YYYY-MM-DD, default 3 months ago). Also the universe as-of date.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Backtest end (YYYY-MM-DD, default today)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=20,
        help="Universe size for ALL variants (default 20 to keep API usage sane; use 127 for a full run)",
    )
    parser.add_argument(
        "--universes",
        type=str,
        default="ranked,current,dollar_volume",
        help="Comma-separated variants to run: ranked,current,dollar_volume",
    )
    parser.add_argument("--initial-capital", type=float, default=100_000.0)
    parser.add_argument("--margin-requirement", type=float, default=0.5)
    parser.add_argument(
        "--analysts",
        type=str,
        default=",".join(LIGHT_ANALYSTS),
        help="Comma-separated rule-based analysts to drive the backtest "
        "(default: all light analysts; fewer = fewer API calls)",
    )
    parser.add_argument("--skip-learnability", action="store_true", help="Skip learnability in the ranked build (faster)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    variants = [v.strip() for v in args.universes.split(",") if v.strip()]
    config = load_universe_config()
    if args.skip_learnability:
        config = replace(config, learnability_enabled=False)

    source = None
    if "ranked" in variants or "dollar_volume" in variants:
        from integrations.universe.data import AlpacaUniverseDataSource

        try:
            source = AlpacaUniverseDataSource(config)
        except (ValueError, ImportError) as exc:
            print(f"Cannot build data-driven universes: {exc}", file=sys.stderr)
            return 1

    universes: dict[str, list[str]] = {}
    for variant in variants:
        try:
            if variant == "ranked":
                universes[variant] = ranked_universe(source, config, args.start_date, args.size)
            elif variant == "current":
                universes[variant] = current_hardcoded_universe(args.size)
            elif variant == "dollar_volume":
                universes[variant] = top_dollar_volume_universe(source, config, args.start_date, args.size)
            else:
                print(f"Unknown universe variant: {variant}", file=sys.stderr)
                return 1
        except Exception as exc:
            print(f"Failed to build '{variant}' universe: {exc}", file=sys.stderr)
            return 1
        print(f"\n[{variant}] {len(universes[variant])} tickers: {','.join(universes[variant])}")

    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]

    reports: list[BacktestReport] = []
    for variant, tickers in universes.items():
        print(f"\n=== Backtesting '{variant}' ({len(tickers)} tickers, {args.start_date} -> {args.end_date}) ===")
        reports.append(
            run_light_backtest(
                name=variant,
                tickers=tickers,
                start_date=args.start_date,
                end_date=args.end_date,
                initial_capital=args.initial_capital,
                margin_requirement=args.margin_requirement,
                light_analysts=analysts,
            )
        )

    _print_comparison(reports)
    print(
        "\nCaveat: candidate pools use today's asset master (survivorship bias); "
        "this affects 'ranked' and 'dollar_volume' comparably. The agent is the "
        "LLM-free light cycle, so results measure universe quality for the "
        "rule-based pipeline, not the full LLM panel."
    )
    return 0


def _print_comparison(reports: list[BacktestReport]) -> None:
    print("\n" + "=" * 96)
    print(
        f"{'Universe':<16} {'Days':>5} {'Final Value':>14} {'Return':>9} "
        f"{'Sharpe':>8} {'Sortino':>8} {'Max DD':>9} {'SPY':>8}"
    )
    print("-" * 96)
    for r in reports:
        sharpe = r.metrics.get("sharpe_ratio")
        sortino = r.metrics.get("sortino_ratio")
        max_dd = r.metrics.get("max_drawdown")
        spy = r.spy_return_pct
        print(
            f"{r.name:<16} {r.days:>5} {r.final_value:>14,.2f} {r.total_return_pct:>+8.2f}% "
            f"{sharpe if sharpe is not None else float('nan'):>8.2f} "
            f"{sortino if sortino is not None else float('nan'):>8.2f} "
            f"{max_dd if max_dd is not None else float('nan'):>8.2f}% "
            f"{spy if spy is not None else float('nan'):>+7.2f}%"
        )
    print("=" * 96)
