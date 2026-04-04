"""Per-filing transaction detail fetch worker."""
import asyncio
import logging

from app.backend.models.insider_schemas import InsiderDetailResponse, InsiderTransactionDetail
from app.backend.services.insider_service._helpers import (
    InitialOwnershipSummaryProtocol,
    TransactionSummaryProtocol,
    _classify_transaction_type,
    _coerce_float,
    _ensure_identity,
)

logger = logging.getLogger(__name__)


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
                ad = str(row.get("AcquiredDisposed") or "")
                shares = _coerce_float(row.get("Shares"))
                price = _coerce_float(row.get("Price"))
                transactions.append(InsiderTransactionDetail(
                    transaction_type=_classify_transaction_type(code, ad),
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
                ad = str(row.get("AcquiredDisposed") or "")
                shares = _coerce_float(row.get("Shares"))
                price = _coerce_float(row.get("Price"))
                transactions.append(InsiderTransactionDetail(
                    transaction_type=_classify_transaction_type(code, ad),
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


async def get_insider_detail(ticker: str, form_type: str, accession_no: str) -> InsiderDetailResponse:
    """Async entry point for per-filing transaction detail. Not cached (unique per filing)."""
    return await asyncio.to_thread(_fetch_detail, ticker, form_type, accession_no)
