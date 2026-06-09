"""cluster_buy alert rule — fires when 3+ distinct insiders buy the same ticker.

Reuses the data layer from ``discovery_service._sources.cluster_buy`` so the
filtering rules (>= 3 distinct insiders, dollar aggregation) stay in one place.
This rule just adapts the Discovery contributions into AlertCandidate objects.

Severity:
  - warning: 3-4 distinct insiders
  - critical: 5+ distinct insiders ("everyone's buying" moment)
"""

import logging
from typing import Any

from app.backend.services.alert_service._types import AlertCandidate
from app.backend.services.discovery_service._sources.cluster_buy import fetch as _fetch_cluster_buys

logger = logging.getLogger(__name__)

_BIG_CLUSTER: int = 5


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    """Read OpenInsider cluster-buy data and emit alerts per qualifying ticker."""
    try:
        contributions = await _fetch_cluster_buys()
    except Exception as exc:
        logger.warning("cluster_buy alert: source fetch failed: %s", exc)
        return []

    out: list[AlertCandidate] = []
    for ticker, signal in contributions:
        detail: dict[str, Any] = signal.detail or {}
        distinct_insiders: int = int(detail.get("distinct_insiders") or 0)
        total_value: float = float(detail.get("total_value") or 0)
        insider_names: list[str] = detail.get("insider_names") or []

        severity = "critical" if distinct_insiders >= _BIG_CLUSTER else "warning"
        names_preview = ", ".join(insider_names[:5])
        if len(insider_names) > 5:
            names_preview += f" (+{len(insider_names) - 5} more)"

        out.append(AlertCandidate(
            rule_type="cluster_buy",
            ticker=ticker[:20],
            title=f"📊 Cluster buy: {ticker} ({distinct_insiders} insiders · ${total_value:,.0f})",
            message=(
                f"Cluster insider buying detected on {ticker}.\n"
                f"{distinct_insiders} distinct insiders bought ${total_value:,.0f} total.\n"
                + (f"Insiders: {names_preview}\n" if names_preview else "")
                + (f"Date range: {detail.get('first_date')} to {detail.get('last_date')}\n"
                   if detail.get("first_date") else "")
            ),
            payload=detail,
            severity=severity,
        ))
    return out
