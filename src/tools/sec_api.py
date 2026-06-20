"""SEC EDGAR public API utilities — no API key required."""

import re
import time

import requests

_SEC_HEADERS = {"User-Agent": "ai-hedge-fund research@example.com"}
_RATE_LIMIT_DELAY = 0.15  # EDGAR public rate limit: ≤10 req/sec

_cik_cache: dict[str, str] = {}


def get_cik(ticker: str) -> str | None:
    """Return the zero-padded 10-digit CIK for a ticker, or None if not found."""
    key = ticker.upper()
    if key in _cik_cache:
        return _cik_cache[key]

    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_SEC_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    for entry in data.values():
        if str(entry.get("ticker", "")).upper() == key:
            cik = str(entry["cik_str"]).zfill(10)
            _cik_cache[key] = cik
            return cik

    return None


def get_recent_filings(cik: str, form_type: str, limit: int = 1) -> list[dict]:
    """
    Return up to `limit` recent filings of `form_type` for the given CIK.
    Each result: {"form", "date", "accession" (no dashes, 18 chars), "primary_document"}
    """
    try:
        time.sleep(_RATE_LIMIT_DELAY)
        resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_SEC_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])

    results = []
    for form, date, acc, doc in zip(forms, dates, accessions, docs):
        if form == form_type:
            results.append(
                {
                    "form": form,
                    "date": date,
                    "accession": acc.replace("-", ""),
                    "primary_document": doc,
                }
            )
            if len(results) >= limit:
                break
    return results


def fetch_filing_text(cik: str, accession: str, primary_document: str) -> str:
    """
    Download a filing and return its plain text (HTML tags stripped).
    cik: zero-padded 10-digit string
    accession: 18-char no-dash string
    """
    cik_int = str(int(cik))
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}"
    )
    try:
        time.sleep(_RATE_LIMIT_DELAY)
        resp = requests.get(url, headers=_SEC_HEADERS, timeout=30)
        if resp.status_code != 200:
            return ""
        text = re.sub(r"<[^>]+>", " ", resp.text)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def _extract_section(
    text: str, item_pattern: str, next_item_pattern: str, max_chars: int = 20_000
) -> str:
    """
    Extract text between two heading patterns (case-insensitive).

    Scans ALL occurrences of item_pattern and returns the longest match —
    this skips table-of-contents entries (which are a single short line)
    and finds the actual section body further in the document.
    """
    matches = list(re.finditer(item_pattern, text, re.IGNORECASE))
    if not matches:
        return ""

    best = ""
    for match in matches:
        start = match.start()
        rest = text[start + 1:]
        end_match = re.search(next_item_pattern, rest, re.IGNORECASE)
        section = (rest[: end_match.start()] if end_match else rest)[:max_chars]
        if len(section) > len(best):
            best = section

    return best


_SECTION_CHARS = 20_000


def get_filing_excerpts(ticker: str) -> dict[str, str]:
    """
    Return a dict of filing-type → extracted text excerpt for the most recent
    10-K (MD&A + Risk Factors), 10-Q (MD&A), and 8-K (full text).
    All values are empty strings if filings are not found.
    """
    cik = get_cik(ticker)
    if not cik:
        return {"10-K": "", "10-Q": "", "8-K": ""}

    excerpts: dict[str, str] = {}

    # 10-K: Item 7 (MD&A) + Item 1A (Risk Factors)
    filings_10k = get_recent_filings(cik, "10-K", limit=1)
    if filings_10k:
        f = filings_10k[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        mda = _extract_section(text, r"ITEM\s+7[\.\s]", r"ITEM\s+7A", _SECTION_CHARS)
        risks = _extract_section(text, r"ITEM\s+1A[\.\s]", r"ITEM\s+1B", _SECTION_CHARS)
        excerpts["10-K"] = f"[MD&A — dated {f['date']}]\n{mda}\n\n[Risk Factors]\n{risks}"
    else:
        excerpts["10-K"] = ""

    # 10-Q: Item 2 (MD&A)
    filings_10q = get_recent_filings(cik, "10-Q", limit=1)
    if filings_10q:
        f = filings_10q[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        mda = _extract_section(text, r"ITEM\s+2[\.\s]", r"ITEM\s+3", _SECTION_CHARS)
        excerpts["10-Q"] = f"[10-Q MD&A — dated {f['date']}]\n{mda}"
    else:
        excerpts["10-Q"] = ""

    # 8-K: full text (usually short)
    filings_8k = get_recent_filings(cik, "8-K", limit=1)
    if filings_8k:
        f = filings_8k[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        excerpts["8-K"] = f"[8-K — dated {f['date']}]\n{text[:_SECTION_CHARS]}"
    else:
        excerpts["8-K"] = ""

    return excerpts
