"""Squeeze setup rule — high short interest + insider buy validation."""

import logging

from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)


async def evaluate(thresholds: dict) -> list[AlertCandidate]:
    """Identify squeeze candidates from the Finnhub data feed.

    thresholds:
        min_short_pct: float (default 25.0)
        min_days_to_cover: float (default 2.0)
        require_insider_buy: bool (default True)
    """
    from app.backend.services.finnhub_service import get_squeeze_candidates

    min_short = float(thresholds.get("min_short_pct", 25.0))
    min_days = float(thresholds.get("min_days_to_cover", 2.0))
    require_insider = bool(thresholds.get("require_insider_buy", True))

    try:
        response = await get_squeeze_candidates()
    except Exception as exc:
        logger.warning("Squeeze rule could not fetch Finnhub data: %s", exc)
        return []

    out: list[AlertCandidate] = []
    for c in response.candidates:
        spct = c.short_pct_float or 0.0
        dtc = c.days_to_cover or 0.0
        if spct < min_short:
            continue
        if dtc < min_days:
            continue
        if require_insider and (c.insider_buy_count or 0) <= 0:
            continue

        severity = "critical" if spct >= 35 else ("warning" if spct >= 30 else "info")
        message = (
            f"{c.company_name or c.ticker} ({c.ticker})\n"
            f"Short: {spct:.1f}% of float · {dtc:.1f} days to cover\n"
            f"Insider buys: {c.insider_buy_count} totaling ${c.insider_buy_value:,.0f}"
        )
        if c.latest_insider_buy_date:
            message += f"\nLatest insider buy: {c.latest_insider_buy_date}"

        out.append(AlertCandidate(
            rule_type="squeeze",
            ticker=c.ticker,
            title=f"Squeeze setup: {c.ticker} ({spct:.0f}% short)",
            message=message,
            payload={
                "short_pct_float": spct,
                "days_to_cover": dtc,
                "insider_buy_count": c.insider_buy_count,
                "insider_buy_value": c.insider_buy_value,
                "latest_insider_buy_date": c.latest_insider_buy_date,
            },
            severity=severity,
        ))
    return out
