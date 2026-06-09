"""high_confluence rule — fires when a ticker has >= N stacked Discovery signals.

The "Super-Nova" / "Emergency Alpha" alert: when 4+ independent signal sources
agree on the same ticker AND composite score is high, that's the SNDK-style
setup we never want to miss. This rule reads the cached Discovery output and
emits a critical alert per qualifying ticker.

Threshold defaults: 4+ distinct signal sources AND total score >= 80.

Discovery service triggers this rule IMMEDIATELY on fresh compute (bypassing
the 4h AlertScheduler) when high-confluence tickers are detected — see
``discovery_service.__init__.get_ideas``.

NOTE: The discovery_service import is deliberately deferred inside the
``evaluate`` body to avoid a circular import: ``discovery_service`` triggers
``alert_service``, which would re-import ``discovery_service`` at module load.
"""

import logging

from app.backend.services.alert_service._types import AlertCandidate

logger = logging.getLogger(__name__)

_MIN_SIGNAL_SOURCES: int = 4
_MIN_SCORE: float = 80.0


async def evaluate(thresholds: dict) -> list[AlertCandidate]:
    """Read latest Discovery cache; emit alerts for qualifying tickers.

    Args:
        thresholds: Optional ``min_sources`` (int) and ``min_score`` (float)
            overrides. Defaults are 4 sources and 80.0 composite score.

    Returns:
        AlertCandidate per ticker that has >= min_sources distinct signal
        types AND total score >= min_score. Empty list if Discovery cache
        is empty or unavailable.
    """
    min_sources: int = int(thresholds.get("min_sources", _MIN_SIGNAL_SOURCES))
    min_score: float = float(thresholds.get("min_score", _MIN_SCORE))

    # Deferred import: see module docstring for circular-import rationale.
    try:
        from app.backend.services.discovery_service import get_ideas
        response = await get_ideas(limit=200)
    except Exception as exc:
        logger.warning("high_confluence: could not load Discovery ideas: %s", exc)
        return []

    out: list[AlertCandidate] = []
    for idea in response.ideas:
        # Count distinct signal source types — same source can emit multiple
        # signals for one ticker (e.g. multiple commodity exposures), so a
        # raw len(idea.signals) would over-count.
        distinct_sources: int = len({s.source for s in idea.signals})
        if distinct_sources < min_sources:
            continue
        if idea.score < min_score:
            continue

        signal_lines = [f"  · {s.label} (+{s.score:.0f})" for s in idea.signals]
        ticker_display = idea.ticker if idea.is_ticker else f"CIK {idea.cik}"

        out.append(AlertCandidate(
            rule_type="high_confluence",
            ticker=idea.ticker[:20],
            title=f"🚨 SUPER-NOVA: {ticker_display} ({distinct_sources} signals · score {idea.score:.0f})",
            message=(
                f"Emergency Alpha — {ticker_display}"
                + (f" ({idea.company})" if idea.company else "")
                + f"\nComposite score: {idea.score:.0f} across {distinct_sources} signal sources\n\n"
                + "Signals:\n"
                + "\n".join(signal_lines)
            ),
            payload={
                "ticker": idea.ticker,
                "is_ticker": idea.is_ticker,
                "cik": idea.cik,
                "company": idea.company,
                "score": idea.score,
                "distinct_sources": distinct_sources,
                "signal_sources": sorted({s.source for s in idea.signals}),
            },
            severity="critical",
        ))

    if out:
        logger.info("high_confluence: %d ticker(s) qualify", len(out))
    return out
