from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel


class SecondOpinionSummary(BaseModel):
    symbol: str
    sleeve: str | None = None
    committee_stance: str
    confidence: float | None = None
    analyst_disagreement: str | None = None
    risk_notes: str | None = None


def summarize_second_opinion(
    decisions: Dict[str, Dict[str, Any]],
    analyst_signals: Dict[str, Any] | None = None,
    sleeve: str | None = None,
) -> List[SecondOpinionSummary]:
    """
    Convert the raw decisions payload from a hedge-fund run into a flat list of
    SecondOpinionSummary objects. This is intentionally conservative: it looks
    for obvious fields like `action` / `decision` and `confidence`.
    """
    summaries: List[SecondOpinionSummary] = []

    for symbol, data in decisions.items():
        # Best-effort extraction of stance and confidence
        stance = (
            data.get("action")
            or data.get("decision")
            or data.get("stance")
            or "HOLD"
        )
        conf = data.get("confidence") or data.get("aggregate_confidence")

        summary = SecondOpinionSummary(
            symbol=symbol,
            sleeve=sleeve or data.get("sleeve"),
            committee_stance=str(stance).upper(),
            confidence=float(conf) if isinstance(conf, (int, float)) else None,
        )
        summaries.append(summary)

    return summaries


