"""Tests for _fetch_summaries() per-filing error handling and offset pagination."""
from unittest.mock import MagicMock, patch

from tests.backend.insider.conftest import make_filing, make_transaction_summary

# Company is imported inside _fetch_summaries via `from edgar import Company`,
# so it must be patched at the edgar module level, not on the service module.
_COMPANY_PATCH = "edgar.Company"


class TestFetchSummaries:
    """_fetch_summaries handles per-filing errors (skipped_count) and offset pagination."""

    def test_successful_filings_are_returned(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        ts = make_transaction_summary(insider_name="Test Insider")
        filing = make_filing(summary_result=ts)

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=0)

        assert response.ticker == "AAPL"
        assert len(response.filings) == 1
        assert response.skipped_count == 0

    def test_filing_that_raises_on_obj_increments_skipped_count(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        good_filing = make_filing(summary_result=make_transaction_summary())
        bad_filing = make_filing(raise_on_obj=RuntimeError("parse error"))

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [bad_filing, good_filing]
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=0)

        assert response.skipped_count == 1
        assert len(response.filings) == 1

    def test_all_filings_fail_returns_empty_with_skipped_count(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        bad1 = make_filing(raise_on_obj=RuntimeError("err1"))
        bad2 = make_filing(raise_on_obj=ValueError("err2"))

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [bad1, bad2]
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=0)

        assert response.filings == []
        assert response.skipped_count == 2

    def test_offset_skips_first_n_filings(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        filings = [
            make_filing(
                accession_no=f"ACC{i}",
                filing_date="2024-03-15",
                summary_result=make_transaction_summary(insider_name=f"Insider {i}"),
            )
            for i in range(5)
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=2)

        assert len(response.filings) == 3
        assert response.filings[0].accession_no == "ACC2"

    def test_limit_caps_number_of_returned_filings(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        filings = [
            make_filing(
                accession_no=f"ACC{i}",
                filing_date="2024-03-15",
                summary_result=make_transaction_summary(),
            )
            for i in range(10)
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                response = _fetch_summaries("AAPL", form_type="4", limit=3, offset=0)

        assert len(response.filings) == 3

    def test_accession_no_is_propagated_from_filing(self) -> None:
        from app.backend.services.insider_service import _fetch_summaries

        filing = make_filing(accession_no="0000320193-24-000099", summary_result=make_transaction_summary())

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=0)

        assert response.filings[0].accession_no == "0000320193-24-000099"

    def test_get_ownership_summary_failure_increments_skipped(self) -> None:
        """Failure inside get_ownership_summary() also causes the filing to be skipped."""
        from app.backend.services.insider_service import _fetch_summaries

        ownership = MagicMock()
        ownership.get_ownership_summary.side_effect = AttributeError("no summary")
        filing = MagicMock()
        filing.accession_no = "ACC1"
        filing.filing_date = "2024-03-15"
        filing.obj.return_value = ownership

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                response = _fetch_summaries("AAPL", form_type="4", limit=10, offset=0)

        assert response.skipped_count == 1
        assert len(response.filings) == 0
