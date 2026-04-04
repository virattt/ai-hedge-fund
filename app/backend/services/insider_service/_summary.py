"""Filing summary builders, aggregate computation, and summary fetch worker."""
import asyncio
import logging

from app.backend.models.insider_schemas import (
    ActivityByDate,
    InsiderAggregates,
    InsiderFilingSummary,
    InsiderSummaryResponse,
)
from app.backend.services.insider_service._helpers import (
    InitialOwnershipSummaryProtocol,
    TransactionSummaryProtocol,
    _coerce_float,
    _coerce_int,
    _iter_parsed_filings,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filing summary builders
# ---------------------------------------------------------------------------


def _build_filing_summary_from_initial(
    summary: InitialOwnershipSummaryProtocol,
    *,
    filing_date: str,
    accession_no: str,
    form_type: str,
) -> InsiderFilingSummary:
    """Build a filing summary from a Form 3 InitialOwnershipSummary."""
    return InsiderFilingSummary(
        filing_date=filing_date,
        accession_no=accession_no,
        insider_name=summary.insider_name,
        position=summary.position,
        primary_activity="Initial Holdings",
        net_change=0,
        net_value=None,
        remaining_shares=_coerce_int(summary.total_holdings),
        has_10b5_1_plan=None,
        transaction_types=[],
        transaction_count=0,
        form_type=form_type,
        total_holdings=_coerce_int(summary.total_holdings),
        has_derivatives=summary.has_derivatives,
    )


def _build_filing_summary_from_transaction(
    summary: TransactionSummaryProtocol,
    *,
    filing_date: str,
    accession_no: str,
    form_type: str,
) -> InsiderFilingSummary:
    """Build a filing summary from a Form 4/5 TransactionSummary."""
    tx_types: list[str] = list(summary.transaction_types) if summary.transaction_types else []
    return InsiderFilingSummary(
        filing_date=filing_date,
        accession_no=accession_no,
        insider_name=summary.insider_name,
        position=summary.position,
        primary_activity=summary.primary_activity,
        net_change=int(summary.net_change or 0),
        net_value=_coerce_float(summary.net_value),
        remaining_shares=_coerce_int(summary.remaining_shares),
        has_10b5_1_plan=summary.has_10b5_1_plan,
        transaction_types=tx_types,
        transaction_count=int(summary.transaction_count or 0),
        form_type=form_type,
    )


def _build_filing_summary(
    ownership_summary: object,
    *,
    filing_date: str,
    accession_no: str,
    form_type: str,
) -> InsiderFilingSummary:
    """Dispatch to the correct builder based on the summary type.

    Form 3 objects implement InitialOwnershipSummaryProtocol (have total_holdings).
    Form 4/5 objects implement TransactionSummaryProtocol (have primary_activity etc.).
    """
    if isinstance(ownership_summary, InitialOwnershipSummaryProtocol):
        return _build_filing_summary_from_initial(
            ownership_summary,
            filing_date=filing_date,
            accession_no=accession_no,
            form_type=form_type,
        )
    if isinstance(ownership_summary, TransactionSummaryProtocol):
        return _build_filing_summary_from_transaction(
            ownership_summary,
            filing_date=filing_date,
            accession_no=accession_no,
            form_type=form_type,
        )
    raise TypeError(f"Unsupported ownership summary type: {type(ownership_summary)}")


# ---------------------------------------------------------------------------
# Aggregate computation
# ---------------------------------------------------------------------------


def _compute_activity_by_date(summaries: list[InsiderFilingSummary]) -> list[ActivityByDate]:
    """Group filing summaries by YYYY-MM month bucket for chart data."""
    buckets: dict[str, ActivityByDate] = {}
    for s in summaries:
        month = s.filing_date[:7] if s.filing_date and len(s.filing_date) >= 7 else "unknown"
        if month not in buckets:
            buckets[month] = ActivityByDate(date=month)
        bucket = buckets[month]
        activity = (s.primary_activity or "").lower()
        value = s.net_value or 0.0
        if "purchase" in activity or activity == "buy":
            bucket.purchases += 1
            bucket.purchase_value += value
        elif "sale" in activity or "sell" in activity:
            bucket.sales += 1
            bucket.sale_value += value
    return [buckets[k] for k in sorted(buckets)]


def _compute_aggregates(summaries: list[InsiderFilingSummary], form_type: str) -> InsiderAggregates:
    """Compute dashboard-level statistics from a list of filing summaries."""
    total_filings = len(summaries)
    total_purchases = 0
    total_sales = 0
    total_other = 0
    largest_value: float | None = None
    largest_insider: str | None = None
    plan_count = 0

    for s in summaries:
        activity = (s.primary_activity or "").lower()
        if "purchase" in activity or activity == "buy":
            total_purchases += 1
        elif "sale" in activity or "sell" in activity:
            total_sales += 1
        else:
            total_other += 1
        if s.has_10b5_1_plan is True:
            plan_count += 1
        if s.net_value is not None and (largest_value is None or s.net_value > largest_value):
            largest_value = s.net_value
            largest_insider = s.insider_name

    ratio = (plan_count / total_filings) if total_filings > 0 else 0.0
    return InsiderAggregates(
        total_filings=total_filings,
        total_purchases=total_purchases,
        total_sales=total_sales,
        total_other=total_other,
        net_sentiment=total_purchases - total_sales,
        largest_transaction_value=largest_value,
        largest_transaction_insider=largest_insider,
        plan_10b5_1_count=plan_count,
        plan_10b5_1_ratio=round(ratio, 4),
        activity_by_date=_compute_activity_by_date(summaries),
    )


# ---------------------------------------------------------------------------
# Summary fetch (synchronous worker)
# ---------------------------------------------------------------------------


def _fetch_summaries(ticker: str, form_type: str, limit: int, offset: int) -> InsiderSummaryResponse:
    """Synchronous worker: fetch and parse filing summaries from SEC EDGAR.

    Skips filings that fail to parse rather than aborting the entire request.
    Applies offset before counting toward limit.
    """
    summaries: list[InsiderFilingSummary] = []
    skipped: list[int] = [0]

    for ownership, filing_date, accession_no in _iter_parsed_filings(ticker, form_type, limit, offset, skipped):
        try:
            ownership_summary = ownership.get_ownership_summary()
            summary = _build_filing_summary(ownership_summary, filing_date=filing_date, accession_no=accession_no, form_type=form_type)
            summaries.append(summary)
        except Exception as exc:
            logger.warning("Skipping summary build %s for %s: %s", accession_no, ticker, exc)
            skipped[0] += 1

    return InsiderSummaryResponse(
        ticker=ticker.upper(),
        form_type=form_type,
        filings=summaries,
        aggregates=_compute_aggregates(summaries, form_type),
        total=len(summaries),
        skipped_count=skipped[0],
    )


async def get_insider_summary(ticker: str, form_type: str = "4", limit: int = 50, offset: int = 0) -> InsiderSummaryResponse:
    """Async entry point for filing summaries. Checks LRU+TTL cache first."""
    from app.backend.services.insider_service import _cache_get, _cache_put  # lazy import avoids circular dep

    cache_key = f"summary:{ticker.upper()}:{form_type}"
    cached = _cache_get(cache_key)
    if isinstance(cached, InsiderSummaryResponse):
        return cached
    result = await asyncio.to_thread(_fetch_summaries, ticker, form_type, limit, offset)
    _cache_put(cache_key, result)
    return result
