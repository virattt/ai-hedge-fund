"""The single serialization chokepoint for opportunity reports (PRD v4 §12, M7).

Every export path and API projection MUST go through ``serialize_report``. It
refuses to emit any report missing a disclaimer — a column + one test is not
enough; the disclaimer cannot be dropped by a projection that forgets it.
"""

from src.storage.models import OpportunityReport


class DisclaimerError(ValueError):
    """Raised when a report would be emitted without a disclaimer."""


def serialize_report(report: OpportunityReport) -> dict:
    """Project an OpportunityReport to a dict, enforcing the disclaimer invariant."""
    disclaimer = (report.disclaimer or "").strip()
    version = (report.disclaimer_version or "").strip()
    if not disclaimer or not version:
        raise DisclaimerError(f"refusing to serialize report id={getattr(report, 'id', '?')} ticker={report.ticker}: " "missing disclaimer/disclaimer_version")
    return {
        "id": report.id,
        "monitor_id": report.monitor_id,
        "ticker": report.ticker,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "label": report.label,
        "confidence": report.confidence,
        "degraded": report.degraded,
        "time_horizon": report.time_horizon,
        "summary": report.summary,
        "agent_signals": report.agent_signals,
        "serenity_context": report.serenity_context,
        "risks": report.risks,
        "next_checks": report.next_checks,
        "disclaimer": disclaimer,
        "disclaimer_version": version,
    }
