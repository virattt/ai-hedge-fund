from unittest.mock import MagicMock, patch

import pytest

from src.tools.sec_api import (
    _extract_section,
    get_cik,
    get_recent_filings,
)


MOCK_TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."},
}


def _mock_get(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    if "company_tickers" in url:
        resp.json.return_value = MOCK_TICKERS_JSON
    elif "submissions" in url:
        resp.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K"],
                    "filingDate": ["2024-11-01", "2024-08-01", "2024-11-05"],
                    "accessionNumber": [
                        "0000320193-24-000123",
                        "0000320193-24-000098",
                        "0000320193-24-000150",
                    ],
                    "primaryDocument": [
                        "aapl-20240930.htm",
                        "aapl-20240629.htm",
                        "aapl-8k.htm",
                    ],
                }
            }
        }
    else:
        resp.text = "<html><body><p>ITEM 7. MANAGEMENT DISCUSSION Revenue grew 10% this year due to strong iPhone sales. ITEM 7A. QUANTITATIVE</p></body></html>"
    return resp


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_returns_padded_string(mock_get):
    import src.tools.sec_api as sec
    sec._cik_cache.clear()
    cik = get_cik("AAPL")
    assert cik == "0000320193"


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_case_insensitive(mock_get):
    import src.tools.sec_api as sec
    sec._cik_cache.clear()
    cik = get_cik("aapl")
    assert cik == "0000320193"


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_returns_none_for_unknown(mock_get):
    import src.tools.sec_api as sec
    sec._cik_cache.clear()
    cik = get_cik("XXXXXXX")
    assert cik is None


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_recent_filings_returns_10k(mock_get):
    filings = get_recent_filings("0000320193", "10-K", limit=1)
    assert len(filings) == 1
    assert filings[0]["form"] == "10-K"
    assert filings[0]["date"] == "2024-11-01"
    assert "accession" in filings[0]
    assert "primary_document" in filings[0]


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_recent_filings_returns_8k(mock_get):
    filings = get_recent_filings("0000320193", "8-K", limit=1)
    assert len(filings) == 1
    assert filings[0]["form"] == "8-K"


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_recent_filings_accession_has_no_dashes(mock_get):
    filings = get_recent_filings("0000320193", "10-K", limit=1)
    assert "-" not in filings[0]["accession"]


def test_extract_section_finds_text():
    text = "...preamble... ITEM 7. Management Discussion revenue grew 10% ITEM 7A. more stuff"
    section = _extract_section(text, r"ITEM\s+7[\.\s]", r"ITEM\s+7A", max_chars=500)
    assert "revenue grew" in section.lower()


def test_extract_section_returns_empty_when_not_found():
    text = "no matching headings here"
    section = _extract_section(text, r"ITEM\s+99", r"ITEM\s+100", max_chars=500)
    assert section == ""
