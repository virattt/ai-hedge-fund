"""Transcript fetching — SEC EDGAR 8-K only."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class EarningsFetchError(Exception):
    pass


@dataclass
class TranscriptFetchResult:
    transcripts: list[dict]
    source: str


def fetch_transcripts_edgar(ticker: str, limit: int = 2) -> list[dict]:
    from app.backend.services.insider_service._helpers import _ensure_identity
    _ensure_identity()

    from edgar import Company
    company = Company(ticker.upper())
    filings = company.get_filings(form="8-K").latest(20)

    results = []
    for filing in filings:
        items_str = str(filing.items or "").lower() if filing.items else ""
        doc_desc = str(filing.primary_doc_description or "").lower() if filing.primary_doc_description else ""
        is_earnings = "2.02" in items_str or any(kw in doc_desc for kw in ("earnings", "conference call", "financial results", "quarterly results"))
        if not is_earnings:
            continue

        try:
            text = filing.text()
            if not text or len(text) < 500:
                continue
        except Exception:
            continue

        filed = str(filing.filing_date or "") if filing.filing_date else ""
        month = 1
        if filed and len(filed) >= 7:
            try:
                month = int(filed[5:7])
            except ValueError:
                pass

        quarter_map = {1: "Q4", 2: "Q4", 3: "Q1", 4: "Q1", 5: "Q2", 6: "Q2", 7: "Q2", 8: "Q3", 9: "Q3", 10: "Q3", 11: "Q4", 12: "Q4"}
        q = quarter_map.get(month, "Q4")

        year = 0
        if filed and len(filed) >= 4:
            try:
                year = int(filed[:4])
            except ValueError:
                pass

        results.append({
            "quarter": q,
            "year": year,
            "date": filed,
            "content": text,
        })

        if len(results) >= limit:
            break

    if not results:
        raise EarningsFetchError(f"No EDGAR 8-K earnings transcripts found for {ticker}")
    return results


def fetch_transcripts(ticker: str, limit: int = 2) -> TranscriptFetchResult:
    return TranscriptFetchResult(
        transcripts=fetch_transcripts_edgar(ticker, limit),
        source="edgar",
    )
