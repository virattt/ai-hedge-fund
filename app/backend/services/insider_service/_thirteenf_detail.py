"""13F-HR detail worker functions (compare holdings, holding history).

Provides two worker functions that load a parsed ThirteenF report via a
shared LRU-cached helper and extract comparison or history DataFrames.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache

from app.backend.models.insider_schemas import (
    AggregateHoldingCompanyDetail,
    AggregateHoldingRecord,
    AggregateHoldingsResponse,
    CompareHoldingsRecord,
    CompareHoldingsResponse,
    HoldingHistoryRecord,
    HoldingHistoryResponse,
)
from app.backend.services.insider_service._helpers import (
    _ensure_identity,
    _sanitize_dataframe_records,
)


@dataclass
class _CIKFetchResult:
    """Result of fetching compare holdings for a single CIK."""
    cik: int
    company_name: str
    compare: CompareHoldingsResponse
from app.backend.services.insider_service._thirteenf import (
    _ThirteenFProto,
    _find_filing,
    _get_filings,
)

logger = logging.getLogger(__name__)

_HISTORY_FIXED_COLS = ("Cusip", "Ticker", "Issuer")


@lru_cache(maxsize=32)
def _load_thirteenf_report(accession_no: str) -> _ThirteenFProto:
    """Return a parsed ThirteenF report object (LRU-cached by accession number)."""
    _ensure_identity()
    try:
        filing = _find_filing(accession_no)
    except Exception as exc:
        raise RuntimeError(
            f"SEC API error while looking up filing {accession_no}: {exc}"
        ) from exc

    if filing is None:
        raise ValueError(f"Filing {accession_no} not found in EDGAR")

    return filing.obj()


def _fetch_compare_holdings(accession_no: str) -> CompareHoldingsResponse:
    """Return quarter-over-quarter holding comparison for a single 13F-HR filing."""
    logger.debug("Fetching compare holdings for filing %s", accession_no)
    report = _load_thirteenf_report(accession_no)
    comparison = report.compare_holdings()

    if comparison is None:
        raise ValueError(
            f"No comparison data available for filing {accession_no} (no previous quarter found)"
        )

    raw_records = _sanitize_dataframe_records(comparison.data)
    records: list[CompareHoldingsRecord] = [
        CompareHoldingsRecord(
            cusip=str(row.get("Cusip", "")),
            ticker=row.get("Ticker") or None,
            issuer=str(row.get("Issuer", "")),
            shares=row.get("Shares"),
            prev_shares=row.get("PrevShares"),
            value=row.get("Value"),
            prev_value=row.get("PrevValue"),
            share_change=row.get("ShareChange"),
            share_change_pct=row.get("ShareChangePct"),
            value_change=row.get("ValueChange"),
            value_change_pct=row.get("ValueChangePct"),
            status=str(row.get("Status", "")),
        )
        for row in raw_records
    ]

    return CompareHoldingsResponse(
        accession_no=accession_no,
        current_period=str(comparison.current_period),
        previous_period=str(comparison.previous_period),
        manager_name=str(comparison.manager_name),
        records=records,
        total=len(records),
    )


def _fetch_holding_history(accession_no: str, periods: int) -> HoldingHistoryResponse:
    """Return multi-period holding history for a single 13F-HR filing."""
    logger.debug("Fetching holding history for filing %s periods=%d", accession_no, periods)
    report = _load_thirteenf_report(accession_no)
    history = report.holding_history(periods=periods)

    if history is None:
        raise ValueError(f"No holding history available for filing {accession_no}")

    df = history.data
    all_cols: list[str] = list(df.columns)
    period_cols = [c for c in all_cols if c not in _HISTORY_FIXED_COLS]

    raw_records = _sanitize_dataframe_records(df)
    records: list[HoldingHistoryRecord] = []
    for row in raw_records:
        pdata = {col: row.get(col) for col in period_cols}
        valid_vals = [v for v in (pdata.get(c) for c in period_cols) if v is not None]
        change_pct: float | None = None
        if len(valid_vals) >= 2 and valid_vals[0] != 0:
            change_pct = round((valid_vals[-1] - valid_vals[0]) / valid_vals[0] * 100, 1)
        records.append(
            HoldingHistoryRecord(
                cusip=str(row.get("Cusip", "")),
                ticker=row.get("Ticker") or None,
                issuer=str(row.get("Issuer", "")),
                periods_data=pdata,
                change_pct=change_pct,
            )
        )

    return HoldingHistoryResponse(
        accession_no=accession_no,
        manager_name=str(history.manager_name),
        periods=period_cols,
        records=records,
        total=len(records),
    )


def _fetch_aggregate_holdings(cik_list: list[int]) -> AggregateHoldingsResponse:
    """Fetch compare holdings for each CIK's most recent filing and aggregate by ticker."""
    _ensure_identity()
    logger.info("Fetching aggregate holdings for %d CIKs", len(cik_list))

    # Resolve CIK → company name from the DB cache
    from app.backend.database.connection import SessionLocal
    from app.backend.database.models import ThirteenFCompany

    db = SessionLocal()
    try:
        rows = db.query(ThirteenFCompany).filter(ThirteenFCompany.cik.in_(cik_list)).all()
        cik_to_company = {r.cik: r.company for r in rows}
    finally:
        db.close()

    # Get all 13F-HR filings once, then find most recent per CIK
    filings = _get_filings(form="13F-HR")
    cik_set = set(cik_list)
    cik_to_accession: dict[int, str] = {}
    for filing in filings:
        cik = int(filing.cik)
        if cik in cik_set and cik not in cik_to_accession:
            cik_to_accession[cik] = str(filing.accession_no)
        if len(cik_to_accession) == len(cik_set):
            break  # found most recent for all

    # Fetch compare holdings in parallel and aggregate
    errors: list[str] = []
    ticker_groups: dict[str, list[tuple[str, int, CompareHoldingsRecord]]] = {}

    # Build work items, skipping CIKs without accessions
    work_items: list[_CIKFetchResult | None] = []
    cik_company_map: dict[int, str] = {}
    for cik in cik_list:
        company_name = cik_to_company.get(cik, f"CIK {cik}")
        cik_company_map[cik] = company_name
        accession = cik_to_accession.get(cik)
        if not accession:
            errors.append(company_name)

    def _fetch_one(cik: int, accession: str) -> _CIKFetchResult:
        return _CIKFetchResult(
            cik=cik,
            company_name=cik_company_map[cik],
            compare=_fetch_compare_holdings(accession),
        )

    fetchable = [(cik, cik_to_accession[cik]) for cik in cik_list if cik in cik_to_accession]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_one, cik, acc): cik for cik, acc in fetchable}
        for future in as_completed(futures):
            cik = futures[future]
            try:
                result = future.result()
                for rec in result.compare.records:
                    if not rec.ticker:
                        continue
                    ticker_groups.setdefault(rec.ticker, []).append((result.company_name, result.cik, rec))
            except Exception as exc:
                logger.warning("Failed to fetch compare holdings for %s (CIK %d): %s", cik_company_map[cik], cik, exc)
                errors.append(cik_company_map[cik])

    # Build aggregated records
    agg_records: list[AggregateHoldingRecord] = []
    for ticker, entries in ticker_groups.items():
        details: list[AggregateHoldingCompanyDetail] = []
        total_shares = 0
        total_value = 0
        total_prev_shares = 0
        total_prev_value = 0
        share_pcts: list[float] = []
        value_pcts: list[float] = []
        issuer = entries[0][2].issuer

        for company_name, cik, rec in entries:
            details.append(AggregateHoldingCompanyDetail(
                company=company_name,
                cik=cik,
                shares=rec.shares,
                prev_shares=rec.prev_shares,
                share_change_pct=rec.share_change_pct,
                value=rec.value,
                prev_value=rec.prev_value,
                value_change_pct=rec.value_change_pct,
                status=rec.status,
            ))
            total_shares += rec.shares or 0
            total_value += rec.value or 0
            total_prev_shares += rec.prev_shares or 0
            total_prev_value += rec.prev_value or 0
            if rec.share_change_pct is not None:
                share_pcts.append(rec.share_change_pct)
            if rec.value_change_pct is not None:
                value_pcts.append(rec.value_change_pct)

        agg_records.append(AggregateHoldingRecord(
            ticker=ticker,
            issuer=issuer,
            companies=len(entries),
            company_details=details,
            total_shares=total_shares,
            total_value=total_value,
            total_prev_shares=total_prev_shares,
            total_prev_value=total_prev_value,
            avg_share_change_pct=round(sum(share_pcts) / len(share_pcts), 1) if share_pcts else None,
            avg_value_change_pct=round(sum(value_pcts) / len(value_pcts), 1) if value_pcts else None,
        ))

    # Sort: most companies first, then by total value desc
    agg_records.sort(key=lambda r: (-r.companies, -r.total_value))

    return AggregateHoldingsResponse(
        records=agg_records,
        total=len(agg_records),
        companies_processed=len(cik_list) - len(errors),
        errors=errors,
    )
