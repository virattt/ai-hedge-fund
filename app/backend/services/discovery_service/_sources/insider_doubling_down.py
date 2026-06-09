"""Discovery source: insiders increasing personal holdings by ≥50% in a single trade.

Uses OpenInsider's `significant_increase` preset (already cached). Parses each
record's `delta_own` field — strings like "+50%", "+1,234%", or "New".
Emits one IdeaSignal per ticker, keeping the largest qualifying delta.

Score:
  - 20 base for ≥50% increase
  - 30 if ≥100% (doubled+)
  - 40 if ≥250% (more than tripled — extreme conviction)
"""

import logging
import re
from collections import defaultdict

from app.backend.models.discovery_schemas import IdeaSignal

logger = logging.getLogger(__name__)

_MIN_DELTA_PCT = 50.0
_DOUBLED_PCT = 100.0
_TRIPLED_PCT = 250.0


def _parse_delta_own(raw: str | None) -> float | None:
    """Convert OpenInsider delta_own cell to a percent float.

    Handles "New" (treat as 999, i.e. effectively infinite increase from zero),
    "+50%", "+1,234%", and "-12.5%" formats. Returns None if unparseable.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.lower() == "new":
        return 999.0
    cleaned = text.replace("%", "").replace(",", "").replace("+", "").strip()
    match = re.match(r"^-?\d+(?:\.\d+)?$", cleaned)
    if not match:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


async def fetch() -> list[tuple[str, IdeaSignal]]:
    try:
        from app.backend.services.openinsider_service import get_openinsider_screener
        response = await get_openinsider_screener("significant_increase", None)
    except Exception as exc:
        logger.warning("insider_doubling_down: fetch failed: %s", exc)
        return []

    by_ticker: dict[str, list[tuple[float, object]]] = defaultdict(list)
    for rec in response.records:
        if not rec.ticker:
            continue
        delta = _parse_delta_own(rec.delta_own)
        if delta is None or delta < _MIN_DELTA_PCT:
            continue
        by_ticker[rec.ticker.upper()].append((delta, rec))

    out: list[tuple[str, IdeaSignal]] = []
    for ticker, hits in by_ticker.items():
        hits.sort(key=lambda x: x[0], reverse=True)
        top_delta, top_rec = hits[0]

        if top_delta >= _TRIPLED_PCT:
            score = 40.0
        elif top_delta >= _DOUBLED_PCT:
            score = 30.0
        else:
            score = 20.0

        delta_label = "new position" if top_delta >= 900 else f"+{top_delta:.0f}%"
        label = f"{top_rec.insider_name or 'Insider'} {delta_label} stake"

        out.append((ticker, IdeaSignal(
            source="insider_doubling_down",
            score=score,
            label=label,
            detail={
                "ticker": ticker,
                "company": top_rec.company_name,
                "insider_name": top_rec.insider_name,
                "title": top_rec.title,
                "delta_own_pct": top_delta,
                "delta_own_raw": top_rec.delta_own,
                "value": top_rec.value,
                "trade_date": top_rec.trade_date,
                "qualifying_count": len(hits),
            },
        )))
    return out
