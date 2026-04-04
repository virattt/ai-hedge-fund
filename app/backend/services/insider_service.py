"""Service for fetching SEC insider trading data via edgartools.

Provides LRU+TTL cache, per-filing error resilience with skipped_count,
pagination offset support, and two async entry points: get_insider_summary
and get_insider_detail.
"""
import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import Protocol, runtime_checkable

from app.backend.models.insider_schemas import (
    ActivityByDate,
    InsiderAggregates,
    InsiderDetailResponse,
    InsiderFilingSummary,
    InsiderSummaryResponse,
    InsiderTransactionDetail,
)

logger = logging.getLogger(__name__)

_identity_set = False

# ---------------------------------------------------------------------------
# Protocols for edgartools ownership summary objects
# ---------------------------------------------------------------------------


@runtime_checkable
class TransactionSummaryProtocol(Protocol):
    """Protocol for edgartools TransactionSummary (Form 4 / Form 5)."""

    insider_name: str
    position: str
    primary_activity: str
    net_change: int | float
    net_value: float | None
    remaining_shares: int | None
    has_10b5_1_plan: bool | None
    transaction_types: list[str]
    transaction_count: int


@runtime_checkable
class InitialOwnershipSummaryProtocol(Protocol):
    """Protocol for edgartools InitialOwnershipSummary (Form 3)."""

    insider_name: str
    position: str
    total_holdings: int | None
    has_derivatives: bool | None


# ---------------------------------------------------------------------------
# LRU cache with TTL
# ---------------------------------------------------------------------------

# Values are (response_object, monotonic_timestamp).
_insider_cache: OrderedDict[str, tuple[object, float]] = OrderedDict()
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes
_CACHE_MAX_SIZE: int = 50


def _cache_get(cache_key: str) -> object | None:
    """Return cached response if present and not expired, else None.

    Evicts the entry when it has expired.
    """
    entry = _insider_cache.get(cache_key)
    if entry is None:
        return None
    response, timestamp = entry
    if time.monotonic() - timestamp > _CACHE_TTL_SECONDS:
        _insider_cache.pop(cache_key, None)
        return None
    return response


def _cache_put(cache_key: str, response: object) -> None:
    """Store response with current timestamp. Evicts oldest entry if over max size."""
    _insider_cache[cache_key] = (response, time.monotonic())
    while len(_insider_cache) > _CACHE_MAX_SIZE:
        _insider_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def _ensure_identity() -> None:
    """Set SEC EDGAR identity (required before any edgartools call)."""
    global _identity_set
    if _identity_set:
        return
    from edgar import set_identity
    identity = os.environ.get("EDGAR_IDENTITY", "AIHedgeFund user@example.com")
    set_identity(identity)
    _identity_set = True


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------


def _coerce_float(value: object) -> float | None:
    """Safely coerce an opaque edgartools value to float, returning None on failure.

    The ``object`` parameter type is intentional: edgartools returns untyped
    DataFrame cell values (numpy scalars, strings, None) that cannot be narrowed
    statically. We handle all failure modes via try/except.
    """
    if value is None:
        return None
    try:
        result = float(str(value))
        return result
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    """Safely coerce an opaque edgartools value to int, returning None on failure.

    See _coerce_float for rationale on ``object`` parameter type.
    """
    if value is None:
        return None
    try:
        result = int(str(value).split(".")[0])
        return result
    except (TypeError, ValueError):
        return None


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

    net_sentiment = total_purchases - total_sales
    ratio = (plan_count / total_filings) if total_filings > 0 else 0.0
    activity_by_date = _compute_activity_by_date(summaries)

    return InsiderAggregates(
        total_filings=total_filings,
        total_purchases=total_purchases,
        total_sales=total_sales,
        total_other=total_other,
        net_sentiment=net_sentiment,
        largest_transaction_value=largest_value,
        largest_transaction_insider=largest_insider,
        plan_10b5_1_count=plan_count,
        plan_10b5_1_ratio=round(ratio, 4),
        activity_by_date=activity_by_date,
    )


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


# ---------------------------------------------------------------------------
# Summary fetch (synchronous worker)
# ---------------------------------------------------------------------------


def _fetch_summaries(ticker: str, form_type: str, limit: int, offset: int) -> InsiderSummaryResponse:
    """Synchronous worker: fetch and parse filing summaries from SEC EDGAR.

    Skips filings that fail to parse rather than aborting the entire request.
    Applies offset before counting toward limit.
    """
    from edgar import Company

    _ensure_identity()
    company = Company(ticker)
    filings_iter = company.get_filings(form=form_type)

    summaries: list[InsiderFilingSummary] = []
    skipped_count = 0
    processed = 0
    skipped_offset = 0

    for filing in filings_iter:
        # Apply offset: skip first `offset` filings without counting as errors
        if skipped_offset < offset:
            skipped_offset += 1
            continue

        if processed >= limit:
            break

        accession_no = str(filing.accession_no)
        filing_date = str(filing.filing_date)

        try:
            ownership = filing.obj()
            ownership_summary = ownership.get_ownership_summary()
            summary = _build_filing_summary(ownership_summary, filing_date=filing_date, accession_no=accession_no, form_type=form_type)
            summaries.append(summary)
            processed += 1
        except Exception as exc:
            logger.warning("Skipping filing %s for %s: %s", accession_no, ticker, exc)
            skipped_count += 1

    aggregates = _compute_aggregates(summaries, form_type)

    return InsiderSummaryResponse(
        ticker=ticker.upper(),
        form_type=form_type,
        filings=summaries,
        aggregates=aggregates,
        total=len(summaries),
        skipped_count=skipped_count,
    )


async def get_insider_summary(ticker: str, form_type: str = "4", limit: int = 50, offset: int = 0) -> InsiderSummaryResponse:
    """Async entry point for filing summaries. Checks LRU+TTL cache first."""
    cache_key = f"summary:{ticker.upper()}:{form_type}"
    cached = _cache_get(cache_key)
    if isinstance(cached, InsiderSummaryResponse):
        return cached
    result = await asyncio.to_thread(_fetch_summaries, ticker, form_type, limit, offset)
    _cache_put(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Detail fetch (synchronous worker)
# ---------------------------------------------------------------------------


def _fetch_detail(ticker: str, form_type: str, accession_no: str) -> InsiderDetailResponse:
    """Synchronous worker: find a filing by accession_no and parse its transactions."""
    from edgar import Company

    _ensure_identity()
    company = Company(ticker)
    filings_iter = company.get_filings(form=form_type)

    target_filing = None
    for filing in filings_iter:
        if str(filing.accession_no) == accession_no:
            target_filing = filing
            break

    if target_filing is None:
        raise ValueError(f"Filing {accession_no} not found for {ticker} form {form_type}")

    filing_date = str(target_filing.filing_date)
    ownership = target_filing.obj()

    insider_name = ""
    position = ""
    try:
        summary = ownership.get_ownership_summary()
        if isinstance(summary, (TransactionSummaryProtocol, InitialOwnershipSummaryProtocol)):
            insider_name = summary.insider_name
            position = summary.position
    except Exception as exc:
        logger.debug("Could not extract insider identity for %s: %s", accession_no, exc)

    transactions: list[InsiderTransactionDetail] = []
    market_trades_count = 0
    derivative_trades_count = 0

    try:
        market_df = ownership.market_trades
        if market_df is not None and not market_df.empty:
            for _, row in market_df.iterrows():
                code = str(row.get("Code") or "")
                acquired_disposed = str(row.get("AcquiredDisposed") or "")
                tx_type = _classify_transaction_type(code, acquired_disposed)
                shares = _coerce_float(row.get("Shares"))
                price = _coerce_float(row.get("Price"))
                transactions.append(InsiderTransactionDetail(
                    transaction_type=tx_type,
                    code=code,
                    shares=shares,
                    price_per_share=price,
                    value=round(shares * price, 2) if shares is not None and price is not None else None,
                    security_title=str(row.get("Security") or ""),
                    security_type="non-derivative",
                    is_derivative=False,
                ))
                market_trades_count += 1
    except Exception as exc:
        logger.debug("Could not parse market_trades for %s: %s", accession_no, exc)

    try:
        deriv_df = ownership.derivative_trades
        if deriv_df is not None and not deriv_df.empty:
            for _, row in deriv_df.iterrows():
                code = str(row.get("Code") or "")
                acquired_disposed = str(row.get("AcquiredDisposed") or "")
                tx_type = _classify_transaction_type(code, acquired_disposed)
                shares = _coerce_float(row.get("Shares"))
                price = _coerce_float(row.get("Price"))
                transactions.append(InsiderTransactionDetail(
                    transaction_type=tx_type,
                    code=code,
                    shares=shares,
                    price_per_share=price,
                    value=round(shares * price, 2) if shares is not None and price is not None else None,
                    security_title=str(row.get("Security") or ""),
                    security_type="derivative",
                    is_derivative=True,
                ))
                derivative_trades_count += 1
    except Exception as exc:
        logger.debug("Could not parse derivative_trades for %s: %s", accession_no, exc)

    return InsiderDetailResponse(
        ticker=ticker.upper(),
        filing_date=filing_date,
        accession_no=accession_no,
        insider_name=insider_name,
        position=position,
        form_type=form_type,
        transactions=transactions,
        market_trades_count=market_trades_count,
        derivative_trades_count=derivative_trades_count,
    )


def _classify_transaction_type(code: str, acquired_disposed: str) -> str:
    """Map transaction code and A/D indicator to a human-readable type."""
    if acquired_disposed == "D":
        return "Sale"
    if code == "P":
        return "Purchase"
    if code in ("A", "G"):
        return "Grant"
    if code in ("M", "X"):
        return "Exercise"
    if code == "C":
        return "Conversion"
    return code or "Unknown"


async def get_insider_detail(ticker: str, form_type: str, accession_no: str) -> InsiderDetailResponse:
    """Async entry point for per-filing transaction detail. Not cached (unique per filing)."""
    return await asyncio.to_thread(_fetch_detail, ticker, form_type, accession_no)
