"""analyst_upgrade alert rule — fires when Wall Street recommendations shift bullish.

Reuses the data layer from ``discovery_service._sources.analyst`` (Finnhub
``/stock/recommendation`` for watchlist tickers). Adapts Discovery contributions
into AlertCandidate objects.

Severity:
  - info: net upgrade shift of 1-2
  - warning: net upgrade shift of 3+ (strong consensus move)
"""

import logging
from typing import Any

from app.backend.services.alert_service._types import AlertCandidate
from app.backend.services.discovery_service._sources.analyst import fetch as _fetch_analyst

logger = logging.getLogger(__name__)

_BIG_SHIFT: int = 3


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    """Read analyst-upgrade contributions for watchlist tickers and emit alerts."""
    try:
        contributions = await _fetch_analyst()
    except Exception as exc:
        logger.warning("analyst_upgrade alert: source fetch failed: %s", exc)
        return []

    out: list[AlertCandidate] = []
    for ticker, signal in contributions:
        detail: dict[str, Any] = signal.detail or {}
        net_shift: int = int(detail.get("net_shift") or 0)
        if net_shift <= 0:
            continue  # source already filters this, but defensive

        severity = "warning" if net_shift >= _BIG_SHIFT else "info"
        plural = "" if net_shift == 1 else "s"

        out.append(AlertCandidate(
            rule_type="analyst_upgrade",
            ticker=ticker[:20],
            title=f"📈 Analyst upgrade: {ticker} (+{net_shift} net upgrade{plural})",
            message=(
                f"Wall Street consensus shifting bullish on {ticker}.\n"
                f"Net (strongBuy + buy) increased by {net_shift} vs prior month.\n"
                "Consensus shifts often precede price moves by 2-4 weeks."
            ),
            payload=detail,
            severity=severity,
        ))
    return out
