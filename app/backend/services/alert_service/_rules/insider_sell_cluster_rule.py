"""Bear-side alert rule: 3+ insiders dumping the same ticker.

Uses OpenInsider's `cluster_sell` preset (sales > $25k, 3+ insiders, 90d).
Doesn't feed Discovery (which is bullish-only) — instead it warns that a
held name is showing coordinated insider exits.

Severity:
  - warning: 3-4 distinct sellers
  - critical: 5+ distinct sellers OR total value ≥ $10M
"""

import logging
from collections import defaultdict

from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)

_MIN_INSIDERS = 3
_BIG_CLUSTER = 5
_BIG_DOLLAR = 10_000_000.0


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("cluster_sell", None)
    except Exception as exc:
        logger.warning("insider_sell_cluster: source fetch failed: %s", exc)
        return []

    by_ticker: dict[str, list] = defaultdict(list)
    for rec in response.records:
        if rec.ticker:
            by_ticker[rec.ticker.upper()].append(rec)

    out: list[AlertCandidate] = []
    for ticker, recs in by_ticker.items():
        distinct_insiders = len({r.insider_name for r in recs if r.insider_name})
        if distinct_insiders < _MIN_INSIDERS:
            continue

        total_value = sum(r.value or 0 for r in recs)
        insider_names = sorted({r.insider_name for r in recs if r.insider_name})
        names_preview = ", ".join(insider_names[:5])
        if len(insider_names) > 5:
            names_preview += f" (+{len(insider_names) - 5} more)"

        is_critical = distinct_insiders >= _BIG_CLUSTER or total_value >= _BIG_DOLLAR
        severity = "critical" if is_critical else "warning"

        dates = [r.trade_date for r in recs if r.trade_date]
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None

        out.append(AlertCandidate(
            rule_type="insider_sell_cluster",
            ticker=ticker[:20],
            title=f"⚠️ Cluster sell: {ticker} ({distinct_insiders} insiders · ${total_value:,.0f})",
            message=(
                f"Coordinated insider selling on {ticker}.\n"
                f"{distinct_insiders} distinct insiders sold ${total_value:,.0f} total.\n"
                + (f"Insiders: {names_preview}\n" if names_preview else "")
                + (f"Date range: {first_date} to {last_date}\n" if first_date else "")
            ),
            payload={
                "ticker": ticker,
                "distinct_insiders": distinct_insiders,
                "total_value": total_value,
                "transaction_count": len(recs),
                "insider_names": insider_names[:10],
                "first_date": first_date,
                "last_date": last_date,
            },
            severity=severity,
        ))
    return out
