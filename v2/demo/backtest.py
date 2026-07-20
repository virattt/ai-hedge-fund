"""PEAD backtest dashboard — long the beats, short the misses. (Demo showcase.)

Usage:
    poetry run python -m v2.demo.backtest             # warm cache -> ~20s, offline-safe
    poetry run python -m v2.demo.backtest --refresh   # rebuild the data cache

This is a presentation-tuned front end over the real BacktestEngine
(v2/backtesting/): pinned dates, a curated 25-stock universe, and paced
trade replay. The engine, PEAD model, and data layer it drives are the
production components.

Runs post-earnings-drift across 25 stocks with point-in-time earnings data
(entries keyed to SEC filing dates — no lookahead), replaying every trade
into a live terminal dashboard: running stats, equity curve, trade tape.

All API responses are disk-cached (CachedDataClient): run once on a good
connection and every subsequent run — including on stage — is fully offline
with identical numbers.
"""

from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from dotenv import load_dotenv
from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from v2.backtesting.engine import BacktestEngine
from v2.data import CachedDataClient, FDClient
from v2.signals import PEADModel

# ---------------------------------------------------------------------------
# Demo config (rehearsal-tunable)
# ---------------------------------------------------------------------------

TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "AMD",
    "NFLX", "CRM", "JPM", "GS", "V", "MA", "UNH", "LLY", "JNJ", "XOM",
    "CVX", "WMT", "COST", "HD", "CAT",
]

START_DATE = "2023-07-01"
# Pinned (NOT date.today()): a moving end date would change the cache keys and
# the quoted stats between rehearsal and demo day. Chosen so the engine's
# padded price window (+ holding_days*2 + 10 days) also stays in the past.
END_DATE = "2026-06-13"
HOLDING_DAYS = 5
CAPITAL = 100_000.0
PER_TRADE = 10_000.0
EARNINGS_LIMIT = 40  # ~3y of 8-K/10-Q records for the PEAD lookback
REPLAY_SECONDS = 18.0  # + ~2s load ≈ 20s total
CURVE_HEIGHT = 6

BLOCKS = " ▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------------------
# Data loading (parallel, disk-cached)
# ---------------------------------------------------------------------------

def _price_window_end() -> str:
    """Mirror BacktestEngine._trade_ticker's padded price window."""
    padded = (date.fromisoformat(END_DATE) + timedelta(days=HOLDING_DAYS * 2 + 10)).isoformat()
    today = date.today().isoformat()
    return min(padded, today)


def _prefetch_ticker(ticker: str, refresh: bool) -> str:
    """Warm the disk cache with exactly the requests the engine will make."""
    with FDClient() as raw:
        fd = CachedDataClient(raw, refresh=refresh)
        fd.get_prices(ticker, START_DATE, _price_window_end())
        fd.get_earnings_history(ticker, limit=EARNINGS_LIMIT)
    return ticker


def _load_data(live: Live, refresh: bool) -> None:
    progress = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=40, complete_style="cyan"),
        TextColumn("{task.completed}/{task.total} tickers"),
    )
    task = progress.add_task(
        "loading prices + earnings surprises · financialdatasets.ai · one API key",
        total=len(TICKERS),
    )
    live.update(Group(_banner(), Panel(progress, border_style="dim")))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_prefetch_ticker, t, refresh) for t in TICKERS]
        for _ in as_completed(futures):
            progress.advance(task)
            live.refresh()
        for f in futures:
            f.result()  # surface any fetch error loudly


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _banner() -> Text:
    line = Text()
    line.append("  PEAD BACKTEST", style="bold white")
    line.append("  ·  long the beats, short the misses", style="cyan")
    line.append(f"  ·  {len(TICKERS)} stocks", style="dim")
    line.append("  ·  point-in-time earnings, no lookahead", style="dim")
    return line


def _stats_panel(metrics, equity: float, n_total: int, shown: int) -> Panel:
    grid = Table.grid(expand=True)
    for _ in range(6):
        grid.add_column(justify="center")

    def cell(label: str, value: str, style: str) -> Text:
        t = Text(justify="center")
        t.append(f"{label}\n", style="dim")
        t.append(value, style=f"bold {style}")
        return t

    m = metrics
    ret_style = "green" if m.total_return_pct >= 0 else "red"
    sharpe_style = "green" if m.sharpe_ratio > 1 else "yellow" if m.sharpe_ratio > 0 else "red"
    grid.add_row(
        cell("PORTFOLIO", f"${equity:,.0f}", "white"),
        cell("RETURN", f"{m.total_return_pct:+.2%}", ret_style),
        cell("SHARPE", f"{m.sharpe_ratio:.2f}", sharpe_style),
        cell("MAX DD", f"{m.max_drawdown_pct:.2%}", "red"),
        cell("WIN RATE", f"{m.win_rate:.0%}", "cyan"),
        cell("TRADES", f"{shown}/{n_total}  ({m.n_long}L·{m.n_short}S)", "white"),
    )
    return Panel(grid, border_style="dim")


def _curve_panel(curve: list[float], width: int) -> Panel:
    """Unicode area chart of the equity curve, green above start / red below."""
    width = max(20, width)
    # Resample the curve to one value per column
    if len(curve) <= width:
        cols = curve
    else:
        step = (len(curve) - 1) / (width - 1)
        cols = [curve[round(i * step)] for i in range(width)]

    lo = min(min(cols), CAPITAL)
    hi = max(max(cols), CAPITAL)
    span = (hi - lo) or 1.0

    rows: list[Text] = []
    levels = [((v - lo) / span) * CURVE_HEIGHT * 8 for v in cols]  # in 1/8 blocks
    for row in range(CURVE_HEIGHT - 1, -1, -1):
        line = Text()
        for v, lvl in zip(cols, levels):
            eighths = max(0, min(8, round(lvl - row * 8)))
            style = "green" if v >= CAPITAL else "red"
            line.append(BLOCKS[eighths], style=style)
        rows.append(line)

    label = Text(
        f"equity  ${cols[-1]:,.0f}   (start ${CAPITAL:,.0f} · low ${min(cols):,.0f} "
        f"· high ${max(cols):,.0f})",
        style="dim",
    )
    return Panel(Group(*rows, label), border_style="dim", title="[dim]equity curve",
                 title_align="left")


def _tape_panel(trades: list, limit: int = 20) -> Panel:
    table = Table.grid(expand=True, padding=(0, 1))
    for justify in ("left", "left", "left", "left", "right", "right", "right", "right"):
        table.add_column(justify=justify)

    for t in list(reversed(trades))[:limit]:
        surprise = t.metadata.get("eps_surprise")
        badge = Text("BEAT", style="bold green") if surprise == "BEAT" else \
            Text("MISS", style="bold red") if surprise == "MISS" else Text("-", style="dim")
        direction = Text("LONG ", style="green") if t.direction == "long" else \
            Text("SHORT", style="red")
        pnl_style = "green" if t.pnl >= 0 else "red"
        table.add_row(
            Text(t.entry_date, style="dim"),
            Text(t.ticker, style="bold cyan"),
            direction,
            badge,
            f"${t.entry_price:,.2f}",
            Text("→", style="dim"),
            f"${t.exit_price:,.2f}",
            Text(f"{t.pnl:+,.0f}  {t.return_pct:+.2%}", style=pnl_style),
        )
    return Panel(table, border_style="dim", title="[dim]trades (newest first)",
                 title_align="left")


def _frame(engine, trades_shown, n_total, width, footer: Text | None = None) -> Group:
    curve = engine._build_equity_curve(trades_shown)
    metrics = engine._compute_metrics(trades_shown, curve)
    parts = [
        _banner(),
        _stats_panel(metrics, curve[-1], n_total, len(trades_shown)),
        _curve_panel(curve, width),
        _tape_panel(trades_shown),
    ]
    if footer is not None:
        parts.append(footer)
    return Group(*parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(prog="python -m v2.demo.backtest")
    parser.add_argument("--refresh", action="store_true",
                        help="rebuild the data cache from the API")
    args = parser.parse_args()

    console = Console()
    curve_width = min(console.width - 8, 90)

    with Live(console=console, refresh_per_second=20) as live:
        # Phase A — load (parallel; disk-cached, so reruns are offline)
        _load_data(live, refresh=args.refresh)

        # Phase B — run the engine off the warm cache, then replay
        engine = BacktestEngine(capital=CAPITAL, per_trade=PER_TRADE)
        model = PEADModel(earnings_limit=EARNINGS_LIMIT)
        with FDClient() as raw:
            fd = CachedDataClient(raw)
            result = engine.run_alpha(
                model, TICKERS, fd, START_DATE, END_DATE, holding_days=HOLDING_DAYS,
            )

        trades = sorted(result.trades, key=lambda t: (t.entry_date, t.ticker))
        if not trades:
            live.update(Text("  No trades generated.", style="red"))
            return

        delay = max(0.02, min(0.35, REPLAY_SECONDS / len(trades)))
        shown: list = []
        for trade in trades:
            shown.append(trade)
            live.update(_frame(engine, shown, len(trades), curve_width))
            time.sleep(delay)

        # Phase C — freeze on the final frame
        m = result.metrics
        footer = Text()
        footer.append(f"  ✓ {m.n_trades} trades · {len(TICKERS)} stocks", style="bold green")
        footer.append(
            " · every entry keyed to an SEC filing date — no lookahead",
            style="dim",
        )
        footer.append(f" · Sharpe {m.sharpe_ratio:.2f}", style="bold white")
        live.update(_frame(engine, shown, len(trades), curve_width, footer=footer))


if __name__ == "__main__":
    main()
