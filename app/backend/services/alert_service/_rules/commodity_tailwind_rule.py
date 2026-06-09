"""commodity_tailwind alert rule — fires when a tracked commodity has a strong YoY move.

Unlike the cluster_buy / analyst rules which alert per-ticker, this rule alerts
**per-commodity**. A single "WTI Oil +25% YoY" alert is more actionable than
11 ticker-level alerts (XOM, CVX, COP, OXY, etc.) all reporting the same
underlying move. The alert message lists the affected tickers from the static
ticker→commodity map.

De-dupe key: the commodity_key (e.g. "wti_oil"). Same commodity won't re-alert
within the standard 3-day window.

Severity:
  - warning: YoY 10-25% (moderate tailwind)
  - critical: YoY >= 25% (proper macro wave)
"""

import logging

from app.backend.services.alert_service._types import AlertCandidate
from app.backend.services.discovery_service._sources.commodity_tailwind import (
    _MODERATE_YOY,
    _SERIES,
    _STRONG_YOY,
    _TICKER_COMMODITY_MAP,
    _fetch_all_series_yoy,
    _real_fred_key,
)

logger = logging.getLogger(__name__)


def _affected_tickers(commodity_key: str) -> list[str]:
    """Return tickers with exposure to the given commodity, in deterministic order."""
    return sorted(
        ticker
        for ticker, exposures in _TICKER_COMMODITY_MAP.items()
        if commodity_key in exposures
    )


async def evaluate(_thresholds: dict) -> list[AlertCandidate]:
    """Read FRED commodity series and emit one alert per commodity with YoY >= threshold."""
    api_key = _real_fred_key()
    if not api_key:
        logger.info("commodity_tailwind alert: FRED_API_KEY not configured, skipping")
        return []

    try:
        yoy_by_commodity = await _fetch_all_series_yoy(api_key)
    except Exception as exc:
        logger.warning("commodity_tailwind alert: FRED fetch failed: %s", exc)
        return []

    out: list[AlertCandidate] = []
    for commodity_key, yoy in yoy_by_commodity.items():
        if yoy is None or yoy < _MODERATE_YOY:
            continue

        series_id, name, _unit = _SERIES[commodity_key]
        tickers = _affected_tickers(commodity_key)
        ticker_list = ", ".join(tickers[:12])
        if len(tickers) > 12:
            ticker_list += f" (+{len(tickers) - 12} more)"

        severity = "critical" if yoy >= _STRONG_YOY else "warning"

        out.append(AlertCandidate(
            rule_type="commodity_tailwind",
            ticker=commodity_key[:20],  # de-dupe key — one alert per commodity
            title=f"🌊 Sector tailwind: {name} +{yoy:.0f}% YoY",
            message=(
                f"{name} is up {yoy:.1f}% year-over-year.\n"
                f"Series: {series_id}\n\n"
                f"Affected tickers ({len(tickers)}):\n{ticker_list}"
            ),
            payload={
                "commodity_key": commodity_key,
                "series_id": series_id,
                "display_name": name,
                "yoy_pct": round(yoy, 2),
                "affected_tickers": tickers,
            },
            severity=severity,
        ))
    return out
