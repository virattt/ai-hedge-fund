"""End-of-day performance reports: daily/weekly/monthly/yearly.

Daily reports are computed from Alpaca fills + the cycle ledgers and saved
to data/reports/daily/YYYY-MM-DD.{json,md}. Longer periods aggregate the
stored daily JSONs. Every report ends with a short two-paragraph advisory
prompt (LLM-generated) meant to be pasted into the coding model (Cursor)
to guide the next round of system upgrades.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Period = Literal["daily", "weekly", "monthly", "yearly"]

_LEDGER_DIR = Path("data/ledger")
_REPORT_ROOT = Path("data/reports")


# ---------------------------------------------------------------------------
# Data model


@dataclass
class PeriodReport:
    period: Period
    start_date: str
    end_date: str
    equity_start: float | None
    equity_end: float | None
    pnl: float | None
    pnl_pct: float | None
    fills: int
    notional: float
    turnover_x: float | None
    realized_total: float
    realized_by_symbol: dict[str, float]
    winners: int
    losers: int
    unrealized_total: float
    open_positions: list[dict[str, Any]]
    cycles: dict[str, int]
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trading_days: int = 1
    advisory: str = ""
    # Churn diagnostics
    fills_by_symbol: dict[str, int] = field(default_factory=dict)
    round_trips: int = 0
    avg_hold_minutes: float | None = None
    orders_by_cycle: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Alpaca data collection (daily only)


def _fetch_fills(client: Any, day: date) -> list[dict[str, Any]]:
    """All filled orders whose fill time (ET) falls on `day`, oldest first."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    from integrations.alpaca.market_hours import now_et

    et = now_et().tzinfo
    fills: list[dict[str, Any]] = []
    after = datetime.combine(day - timedelta(days=1), datetime.min.time())
    until: datetime | None = None
    for _page in range(20):  # paginate in case of >500 orders
        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500, after=after, until=until)
        orders = client.get_orders(req)
        if not orders:
            break
        for o in orders:
            if not o.filled_at or not o.filled_qty or float(o.filled_qty) <= 0:
                continue
            if o.filled_at.astimezone(et).date() != day:
                continue
            fills.append(
                {
                    "symbol": o.symbol,
                    "side": "buy" if "buy" in str(o.side).lower() else "sell",
                    "qty": float(o.filled_qty),
                    "price": float(o.filled_avg_price or 0.0),
                    "filled_at": o.filled_at.isoformat(),
                }
            )
        if len(orders) < 500:
            break
        until = min(o.submitted_at for o in orders if o.submitted_at)
    fills.sort(key=lambda f: f["filled_at"])
    return fills


def compute_realized_pnl(fills: list[dict[str, Any]]) -> dict[str, float]:
    """Average-cost realized P&L per symbol from a chronological fill stream.

    Tracks signed inventory per symbol; a fill that reduces or flips the
    position realizes P&L against the average cost.
    """
    pos: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # [signed qty, avg cost]
    realized: dict[str, float] = defaultdict(float)
    for f in fills:
        sym, px = f["symbol"], f["price"]
        sq = f["qty"] if f["side"] == "buy" else -f["qty"]
        inv, avg = pos[sym]
        if inv * sq >= 0:
            tot = inv + sq
            avg = (abs(inv) * avg + abs(sq) * px) / abs(tot) if tot != 0 else 0.0
            pos[sym] = [tot, avg]
        else:
            closed = min(abs(sq), abs(inv))
            realized[sym] += closed * (px - avg) * (1 if inv > 0 else -1)
            rem = inv + sq
            pos[sym] = [rem, avg if rem * inv > 0 else px]
    return dict(realized)


def compute_round_trips(fills: list[dict[str, Any]]) -> tuple[int, float | None]:
    """Count same-day round trips (position opened then fully closed) and
    the average open-to-flat hold time in minutes."""
    inventory: dict[str, float] = defaultdict(float)
    opened_at: dict[str, datetime] = {}
    holds: list[float] = []
    trips = 0
    for f in fills:
        sym = f["symbol"]
        sq = f["qty"] if f["side"] == "buy" else -f["qty"]
        prev = inventory[sym]
        inventory[sym] = prev + sq
        try:
            ts = datetime.fromisoformat(f["filled_at"])
        except (TypeError, ValueError):
            continue
        if prev == 0 and inventory[sym] != 0:
            opened_at[sym] = ts
        elif prev != 0 and inventory[sym] == 0:
            trips += 1
            start = opened_at.pop(sym, None)
            if start is not None:
                holds.append((ts - start).total_seconds() / 60)
    avg_hold = round(sum(holds) / len(holds), 1) if holds else None
    return trips, avg_hold


def _orders_by_cycle(day: date) -> dict[str, int]:
    """Submitted order counts per cycle kind, from the day's ledgers."""
    counts: dict[str, int] = defaultdict(int)
    prefix = day.strftime("%Y%m%d")
    for path in sorted(_LEDGER_DIR.glob(f"{prefix}T*_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        kind = data.get("cycle_kind", "unknown")
        for entry in data.get("execution", []):
            if isinstance(entry, dict) and entry.get("submitted"):
                counts[kind] += 1
    return dict(counts)


def _equity_curve_from_ledgers(day: date) -> list[dict[str, Any]]:
    """Per-cycle equity snapshots recorded in the day's ledger files."""
    points: list[dict[str, Any]] = []
    prefix = day.strftime("%Y%m%d")
    for path in sorted(_LEDGER_DIR.glob(f"{prefix}T*_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        match = re.search(r"Equity: \$([\d,\.]+)", data.get("account_summary", ""))
        if not match:
            continue
        points.append(
            {
                "timestamp": data.get("timestamp"),
                "equity": float(match.group(1).replace(",", "")),
                "cycle_kind": data.get("cycle_kind", "unknown"),
            }
        )
    return points


def _cycle_counts(curve: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for point in curve:
        counts[point["cycle_kind"]] += 1
    return dict(counts)


def build_daily_report(day: date | None = None) -> PeriodReport:
    """Compute today's report from Alpaca fills, positions, and ledgers."""
    from alpaca.trading.client import TradingClient

    from integrations.alpaca.config import load_alpaca_config
    from integrations.alpaca.market_hours import trading_date

    day = day or trading_date()
    cfg = load_alpaca_config()
    client = TradingClient(api_key=cfg.api_key, secret_key=cfg.secret_key, paper=cfg.paper)

    account = client.get_account()
    equity_end = float(account.equity)
    equity_start = float(account.last_equity)

    fills = _fetch_fills(client, day)
    notional = sum(f["qty"] * f["price"] for f in fills)
    realized = compute_realized_pnl(fills)

    positions = client.get_all_positions()
    open_positions = [
        {
            "symbol": p.symbol,
            "side": "short" if "short" in str(p.side).lower() else "long",
            "qty": abs(float(p.qty)),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price) if p.current_price else None,
            "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
        }
        for p in positions
    ]
    unrealized_total = sum(p["unrealized_pl"] for p in open_positions)

    curve = _equity_curve_from_ledgers(day)
    pnl = equity_end - equity_start

    fills_by_symbol: dict[str, int] = defaultdict(int)
    for f in fills:
        fills_by_symbol[f["symbol"]] += 1
    round_trips, avg_hold = compute_round_trips(fills)

    return PeriodReport(
        period="daily",
        start_date=day.isoformat(),
        end_date=day.isoformat(),
        equity_start=equity_start,
        equity_end=equity_end,
        pnl=round(pnl, 2),
        pnl_pct=round(pnl / equity_start * 100, 4) if equity_start else None,
        fills=len(fills),
        notional=round(notional, 2),
        turnover_x=round(notional / equity_end, 2) if equity_end else None,
        realized_total=round(sum(realized.values()), 2),
        realized_by_symbol={k: round(v, 2) for k, v in sorted(realized.items(), key=lambda kv: kv[1])},
        winners=sum(1 for v in realized.values() if v > 0),
        losers=sum(1 for v in realized.values() if v < 0),
        unrealized_total=round(unrealized_total, 2),
        open_positions=open_positions,
        cycles=_cycle_counts(curve),
        equity_curve=curve,
        trading_days=1,
        fills_by_symbol=dict(sorted(fills_by_symbol.items(), key=lambda kv: -kv[1])),
        round_trips=round_trips,
        avg_hold_minutes=avg_hold,
        orders_by_cycle=_orders_by_cycle(day),
    )


# ---------------------------------------------------------------------------
# Period aggregation (weekly / monthly / yearly) from stored dailies


def _period_start(period: Period, end_day: date) -> date:
    if period == "weekly":
        return end_day - timedelta(days=end_day.weekday())  # Monday
    if period == "monthly":
        return end_day.replace(day=1)
    if period == "yearly":
        return end_day.replace(month=1, day=1)
    return end_day


def _load_daily_reports(start: date, end: date) -> list[dict[str, Any]]:
    reports = []
    directory = _REPORT_ROOT / "daily"
    if not directory.exists():
        return reports
    for path in sorted(directory.glob("*.json")):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if start <= day <= end:
            try:
                reports.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return reports


def build_period_report(period: Period, end_day: date | None = None) -> PeriodReport:
    """Aggregate stored daily reports into a weekly/monthly/yearly view."""
    from integrations.alpaca.market_hours import trading_date

    end_day = end_day or trading_date()
    start_day = _period_start(period, end_day)
    dailies = _load_daily_reports(start_day, end_day)
    if not dailies:
        raise ValueError(
            f"No daily reports found between {start_day} and {end_day} — "
            "generate daily reports first (alpaca-fund report --period daily)."
        )

    realized: dict[str, float] = defaultdict(float)
    for d in dailies:
        for sym, val in d.get("realized_by_symbol", {}).items():
            realized[sym] += val

    equity_start = dailies[0].get("equity_start")
    equity_end = dailies[-1].get("equity_end")
    pnl = (equity_end - equity_start) if (equity_start and equity_end) else None
    notional = round(sum(d.get("notional", 0.0) for d in dailies), 2)

    cycles: dict[str, int] = defaultdict(int)
    for d in dailies:
        for kind, count in d.get("cycles", {}).items():
            cycles[kind] += count

    orders_by_cycle: dict[str, int] = defaultdict(int)
    fills_by_symbol: dict[str, int] = defaultdict(int)
    for d in dailies:
        for kind, count in d.get("orders_by_cycle", {}).items():
            orders_by_cycle[kind] += count
        for sym, count in d.get("fills_by_symbol", {}).items():
            fills_by_symbol[sym] += count

    return PeriodReport(
        period=period,
        start_date=dailies[0]["start_date"],
        end_date=dailies[-1]["end_date"],
        equity_start=equity_start,
        equity_end=equity_end,
        pnl=round(pnl, 2) if pnl is not None else None,
        pnl_pct=round(pnl / equity_start * 100, 4) if pnl is not None and equity_start else None,
        fills=sum(d.get("fills", 0) for d in dailies),
        notional=notional,
        turnover_x=round(notional / equity_end, 2) if equity_end else None,
        realized_total=round(sum(realized.values()), 2),
        realized_by_symbol={k: round(v, 2) for k, v in sorted(realized.items(), key=lambda kv: kv[1])},
        winners=sum(1 for v in realized.values() if v > 0),
        losers=sum(1 for v in realized.values() if v < 0),
        unrealized_total=dailies[-1].get("unrealized_total", 0.0),
        open_positions=dailies[-1].get("open_positions", []),
        cycles=dict(cycles),
        equity_curve=[],  # per-cycle curves stay in the dailies
        trading_days=len(dailies),
        fills_by_symbol=dict(sorted(fills_by_symbol.items(), key=lambda kv: -kv[1])),
        round_trips=sum(d.get("round_trips", 0) for d in dailies),
        avg_hold_minutes=None,  # only meaningful within a single day
        orders_by_cycle=dict(orders_by_cycle),
    )


# ---------------------------------------------------------------------------
# Advisory prompt (LLM, with deterministic fallback)


def _report_digest(report: PeriodReport) -> str:
    """Compact plain-text digest of the report for the advisory prompt."""
    # realized_by_symbol is sorted ascending, but slicing it blindly leaks
    # positives into "losers" (and vice versa) when one side has <5 entries.
    items = list(report.realized_by_symbol.items())
    neg = [(s, v) for s, v in items if v < 0][:5]
    pos = [(s, v) for s, v in sorted(items, key=lambda kv: -kv[1]) if v > 0][:5]
    losers = ", ".join(f"{s} {v:+.0f}" for s, v in neg) or "none"
    winners = ", ".join(f"{s} {v:+.0f}" for s, v in pos) or "none"
    lines = [
        f"Period: {report.period} {report.start_date}..{report.end_date} ({report.trading_days} trading days)",
        f"P&L: {report.pnl} ({report.pnl_pct}%) | equity {report.equity_start} -> {report.equity_end}",
        f"Fills: {report.fills} | notional ${report.notional:,.0f} | turnover {report.turnover_x}x equity",
        f"Realized: {report.realized_total} across {report.winners} winners / {report.losers} losers",
        f"Top losers: {losers}",
        f"Top winners: {winners}",
        f"Unrealized on open book: {report.unrealized_total} across {len(report.open_positions)} positions",
        f"Cycle counts: {report.cycles}",
        f"Same-day round trips: {report.round_trips} | avg hold {report.avg_hold_minutes} min",
        f"Submitted orders by cycle source: {report.orders_by_cycle}",
        f"Most-traded symbols: {dict(list(report.fills_by_symbol.items())[:8])}",
    ]
    return "\n".join(lines)


def generate_advisory(report: PeriodReport, *, model_name: str, model_provider: str) -> str:
    """Two-paragraph upgrade prompt for the coding model, from report data."""
    digest = _report_digest(report)
    prompt = (
        "You are the performance-review layer of an autonomous AI hedge fund. "
        "The trading system is a Python codebase (LangGraph analyst agents, an "
        "Alpaca execution daemon with heavy LLM cycles and light rule-based "
        "cycles, a risk governor enforcing daily turnover/fill caps, symbol "
        "cooldowns, position-count limits and an intraday drawdown breaker, "
        "and a factor-based universe selector). Below is the "
        f"{report.period} trading report.\n\n{digest}\n\n"
        "Write EXACTLY two paragraphs, addressed to a coding assistant (Cursor) "
        "that maintains this codebase. Paragraph 1: diagnose the most costly "
        "behavioral problems evident in the numbers (churn, whipsaw, sizing, "
        "timing, concentration - whatever the data supports). Paragraph 2: "
        "prescribe the few highest-leverage code changes to make before the "
        "next session, concretely enough to implement. Plain text only, no "
        "headers, no bullet lists, no markdown."
    )
    try:
        from src.llm.models import ModelProvider, get_model

        llm = get_model(model_name, ModelProvider(model_provider))
        response = llm.invoke(prompt)
        text = str(response.content).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Advisory LLM call failed — using rule-based fallback: %s", exc)
    return _fallback_advisory(report)


def _fallback_advisory(report: PeriodReport) -> str:
    """Deterministic advisory when no LLM is reachable."""
    problems: list[str] = []
    if report.turnover_x and report.turnover_x > 3:
        problems.append(
            f"turnover was {report.turnover_x}x equity, so spread/slippage costs likely exceed edge; "
            "positions are being reversed between cycles instead of held"
        )
    if report.losers > report.winners:
        problems.append(
            f"closed trades ran {report.winners} winners to {report.losers} losers, suggesting entries "
            "are noise-driven rather than signal-driven"
        )
    if report.unrealized_total < 0 and report.pnl is not None and abs(report.unrealized_total) > abs(report.pnl) / 2:
        problems.append("most of the loss sits in unrealized P&L on recently opened positions")
    para1 = (
        f"In the {report.period} report ({report.start_date} to {report.end_date}) the account moved "
        f"{report.pnl if report.pnl is not None else 'n/a'} ({report.pnl_pct}%) on {report.fills} fills. "
        + ("Key issues: " + "; ".join(problems) + "." if problems else "No acute behavioral problems stood out.")
    )
    para2 = (
        "Prioritize: give heavy cycles position memory (entry time, entry price, current P&L in the prompt) "
        "and require a signal reversal threshold before closing same-day positions; enforce one round trip "
        "per symbol per day and a daily notional turnover budget of roughly 2x equity; block new entries in "
        "the final 30-45 minutes of the session; and log realized P&L per closed round trip in the ledger "
        "so attribution is automatic."
    )
    return f"{para1}\n\n{para2}"


# ---------------------------------------------------------------------------
# Persistence + orchestration


def _to_markdown(report: PeriodReport) -> str:
    lines = [
        f"# {report.period.capitalize()} trading report — {report.start_date} to {report.end_date}",
        "",
        f"- **P&L:** {report.pnl} ({report.pnl_pct}%) | equity {report.equity_start} → {report.equity_end}",
        f"- **Fills:** {report.fills} | notional ${report.notional:,.0f} | turnover {report.turnover_x}x",
        f"- **Realized:** {report.realized_total} ({report.winners} winners / {report.losers} losers)",
        f"- **Unrealized:** {report.unrealized_total} across {len(report.open_positions)} open positions",
        f"- **Cycles:** {report.cycles}",
        "",
        "## Churn diagnostics",
        "",
        f"- **Same-day round trips:** {report.round_trips}"
        + (f" (avg hold {report.avg_hold_minutes} min)" if report.avg_hold_minutes is not None else ""),
        f"- **Submitted orders by cycle source:** {report.orders_by_cycle}",
        f"- **Most-traded symbols:** "
        + (
            ", ".join(f"{s} ({n})" for s, n in list(report.fills_by_symbol.items())[:10])
            if report.fills_by_symbol
            else "none"
        ),
        "",
        "## Realized P&L by symbol",
        "",
        "| Symbol | P&L |",
        "| --- | ---: |",
    ]
    for sym, val in report.realized_by_symbol.items():
        lines.append(f"| {sym} | {val:+.2f} |")
    if report.open_positions:
        lines += [
            "",
            "## Open positions",
            "",
            "| Symbol | Side | Qty | Entry | Last | Unrealized |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for p in report.open_positions:
            last = f"{p['current_price']:.2f}" if p.get("current_price") else "-"
            lines.append(
                f"| {p['symbol']} | {p['side']} | {p['qty']:.0f} | "
                f"{p['avg_entry_price']:.2f} | {last} | {p['unrealized_pl']:+.2f} |"
            )
    lines += ["", "## Upgrade advisory (paste into Cursor)", "", report.advisory, ""]
    return "\n".join(lines)


def save_report(report: PeriodReport, root: Path | None = None) -> Path:
    directory = (root or _REPORT_ROOT) / report.period
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / report.end_date
    base.with_suffix(".json").write_text(
        json.dumps(asdict(report), indent=2), encoding="utf-8"
    )
    base.with_suffix(".md").write_text(_to_markdown(report), encoding="utf-8")
    return base.with_suffix(".md")


def _is_period_end(period: Period, day: date) -> bool:
    """Whether `day` is the last trading day of the period (weekend-aware)."""
    nxt = day + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    if period == "weekly":
        return nxt.isocalendar()[:2] != day.isocalendar()[:2]
    if period == "monthly":
        return nxt.month != day.month
    if period == "yearly":
        return nxt.year != day.year
    return True


def run_end_of_day_reports(
    *,
    model_name: str,
    model_provider: str,
    day: date | None = None,
) -> list[tuple[PeriodReport, Path]]:
    """Generate the daily report plus any period reports that end today."""
    from integrations.alpaca.market_hours import trading_date

    day = day or trading_date()
    written: list[tuple[PeriodReport, Path]] = []

    daily = build_daily_report(day)
    daily.advisory = generate_advisory(daily, model_name=model_name, model_provider=model_provider)
    written.append((daily, save_report(daily)))

    for period in ("weekly", "monthly", "yearly"):
        if not _is_period_end(period, day):
            continue
        try:
            rep = build_period_report(period, day)  # type: ignore[arg-type]
        except ValueError as exc:
            logger.warning("Skipping %s report: %s", period, exc)
            continue
        rep.advisory = generate_advisory(rep, model_name=model_name, model_provider=model_provider)
        written.append((rep, save_report(rep)))

    return written
