"""Tests for _fetch_thirteenf_filings() worker in _thirteenf.py.

Covers pagination, has_more flag, _ensure_identity() call order,
year/quarter passthrough, SEC error wrapping, filing attribute
mapping, and company_name search via filings.find().
"""
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers to build minimal mock objects
# ---------------------------------------------------------------------------

def _make_filing(
    company: str = "BERKSHIRE HATHAWAY INC",
    cik: int = 1067983,
    filing_date: str = "2026-03-15",
    accession_no: str = "0001234567-26-000001",
    form: str = "13F-HR",
) -> MagicMock:
    f = MagicMock()
    f.company = company
    f.cik = cik
    f.filing_date = filing_date
    f.accession_no = accession_no
    f.form = form
    return f


def _make_filings_collection(filing_list: list) -> MagicMock:
    """Return a mock Filings object whose len() and slicing match filing_list."""
    filings = MagicMock()
    filings.__len__ = MagicMock(return_value=len(filing_list))
    filings.__iter__ = MagicMock(return_value=iter(filing_list))
    filings.__getitem__ = MagicMock(side_effect=lambda s: filing_list[s])
    return filings


# ---------------------------------------------------------------------------
# _fetch_thirteenf_filings tests
# ---------------------------------------------------------------------------

class TestFetchThirteenFFilings:

    def test_fetch_filings_calls_ensure_identity_first(self) -> None:
        """_ensure_identity() must be called before edgar.get_filings()."""
        from app.backend.services.insider_service import _thirteenf

        call_order: list[str] = []

        filing = _make_filing()
        filings = _make_filings_collection([filing])

        def fake_ensure_identity() -> None:
            call_order.append("ensure_identity")

        def fake_get_filings(**kwargs: object) -> MagicMock:
            call_order.append("get_filings")
            return filings

        with patch.object(_thirteenf, "_ensure_identity", side_effect=fake_ensure_identity), \
             patch.object(_thirteenf, "_get_filings", side_effect=fake_get_filings):
            _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

        assert call_order == ["ensure_identity", "get_filings"]

    def test_fetch_filings_returns_paginated_list(self) -> None:
        """Returns ThirteenFListResponse with correct filings slice."""
        from app.backend.services.insider_service import _thirteenf
        from app.backend.models.insider_schemas import ThirteenFListResponse

        filings_data = [
            _make_filing(company=f"CO{i}", cik=i, accession_no=f"000000000{i}-26-000001")
            for i in range(5)
        ]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert isinstance(result, ThirteenFListResponse)
        assert len(result.filings) == 3
        assert result.total == 5

    def test_fetch_filings_has_more_true_when_more_filings_exist(self) -> None:
        """has_more is True when offset + limit < total."""
        from app.backend.services.insider_service import _thirteenf

        filings_data = [_make_filing(company=f"CO{i}") for i in range(5)]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert result.has_more is True

    def test_fetch_filings_has_more_false_at_end(self) -> None:
        """has_more is False when offset + limit >= total."""
        from app.backend.services.insider_service import _thirteenf

        filings_data = [_make_filing(company=f"CO{i}") for i in range(3)]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert result.has_more is False

    def test_fetch_filings_passes_year_quarter_to_get_filings(self) -> None:
        """year and quarter are forwarded to edgar.get_filings() when not None."""
        from app.backend.services.insider_service import _thirteenf

        filings = _make_filings_collection([])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings) as mock_gf:
            _thirteenf._fetch_thirteenf_filings(limit=20, offset=0, year=2026, quarter=1)

        mock_gf.assert_called_once()
        call_kwargs = mock_gf.call_args.kwargs
        assert call_kwargs.get("year") == 2026
        assert call_kwargs.get("quarter") == 1

    def test_fetch_filings_omits_year_quarter_when_none(self) -> None:
        """year and quarter keys are NOT forwarded when they are None."""
        from app.backend.services.insider_service import _thirteenf

        filings = _make_filings_collection([])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings) as mock_gf:
            _thirteenf._fetch_thirteenf_filings(limit=20, offset=0, year=None, quarter=None)

        call_kwargs = mock_gf.call_args.kwargs
        assert "year" not in call_kwargs
        assert "quarter" not in call_kwargs

    def test_fetch_filings_raises_runtime_error_on_sec_failure(self) -> None:
        """SEC API errors are caught and re-raised as RuntimeError."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", side_effect=Exception("network timeout")):
            with pytest.raises(RuntimeError, match="SEC API error"):
                _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

    def test_fetch_filings_maps_filing_attributes(self) -> None:
        """Filing attributes are correctly mapped to ThirteenFFilingListItem fields."""
        from app.backend.services.insider_service import _thirteenf

        filing = _make_filing(
            company="BERKSHIRE HATHAWAY INC",
            cik=1067983,
            filing_date="2026-03-15",
            accession_no="0001234567-26-000001",
            form="13F-HR",
        )
        filings = _make_filings_collection([filing])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

        assert len(result.filings) == 1
        item = result.filings[0]
        assert item.company == "BERKSHIRE HATHAWAY INC"
        assert item.cik == 1067983
        assert item.accession_no == "0001234567-26-000001"
        assert item.form == "13F-HR"

    def test_fetch_thirteenf_filings_with_company_name_filters_via_find(self) -> None:
        """When company_name provided, calls filings.find(company_name) and returns filtered results."""
        from app.backend.services.insider_service import _thirteenf

        matching_filing = _make_filing(company="BERKSHIRE HATHAWAY INC", cik=1067983)
        filtered_filings = _make_filings_collection([matching_filing])

        all_filings = MagicMock()
        all_filings.__len__ = MagicMock(return_value=500)
        all_filings.find = MagicMock(return_value=filtered_filings)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=all_filings):
            result = _thirteenf._fetch_thirteenf_filings(
                limit=20, offset=0, year=None, quarter=None, company_name="Berkshire"
            )

        all_filings.find.assert_called_once_with("Berkshire")
        assert result.total == 1
        assert len(result.filings) == 1
        assert result.filings[0].company == "BERKSHIRE HATHAWAY INC"

    def test_fetch_thirteenf_filings_company_name_empty_results(self) -> None:
        """When filings.find() returns empty collection, response has total=0 and filings=[]."""
        from app.backend.services.insider_service import _thirteenf

        empty_filings = _make_filings_collection([])

        all_filings = MagicMock()
        all_filings.__len__ = MagicMock(return_value=500)
        all_filings.find = MagicMock(return_value=empty_filings)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=all_filings):
            result = _thirteenf._fetch_thirteenf_filings(
                limit=20, offset=0, year=None, quarter=None, company_name="UnknownCorp"
            )

        assert result.total == 0
        assert result.filings == []
        assert result.has_more is False

    def test_fetch_thirteenf_filings_without_company_name_does_not_call_find(self) -> None:
        """When company_name is None, filings.find() is NOT called and existing behavior is preserved."""
        from app.backend.services.insider_service import _thirteenf

        filing = _make_filing()
        filings = _make_filings_collection([filing])
        filings.find = MagicMock()

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(
                limit=10, offset=0, year=None, quarter=None, company_name=None
            )

        filings.find.assert_not_called()
        assert result.total == 1
        assert len(result.filings) == 1

    def test_fetch_thirteenf_filings_company_search_error_raises_runtime_error(self) -> None:
        """When filings.find() raises, a RuntimeError with descriptive message is raised."""
        from app.backend.services.insider_service import _thirteenf

        all_filings = MagicMock()
        all_filings.__len__ = MagicMock(return_value=500)
        all_filings.find = MagicMock(side_effect=Exception("SEC search index unavailable"))

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=all_filings):
            with pytest.raises(RuntimeError, match="company search"):
                _thirteenf._fetch_thirteenf_filings(
                    limit=20, offset=0, year=None, quarter=None, company_name="Berkshire"
                )
