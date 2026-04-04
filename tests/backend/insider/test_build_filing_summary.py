"""Tests for _build_filing_summary() in insider_service.py."""
from tests.backend.insider.conftest import make_initial_ownership_summary, make_transaction_summary


class TestBuildFilingSummary:
    """_build_filing_summary extracts ownership summary objects into InsiderFilingSummary."""

    def test_transaction_summary_fields_are_propagated(self) -> None:
        from app.backend.services.insider_service import _build_filing_summary

        ts = make_transaction_summary()
        result = _build_filing_summary(ts, filing_date="2024-03-15", accession_no="0000320193-24-000081", form_type="4")

        assert result.accession_no == "0000320193-24-000081"
        assert result.filing_date == "2024-03-15"
        assert result.insider_name == "Tim Cook"
        assert result.position == "CEO"
        assert result.primary_activity == "Sale"
        assert result.net_change == -50000
        assert result.net_value == 8_750_000.0
        assert result.remaining_shares == 3_280_000
        assert result.has_10b5_1_plan is True
        assert result.transaction_count == 2
        assert result.form_type == "4"

    def test_accession_no_is_in_result(self) -> None:
        from app.backend.services.insider_service import _build_filing_summary

        ts = make_transaction_summary()
        result = _build_filing_summary(ts, filing_date="2024-01-01", accession_no="0001234567-24-000001", form_type="4")
        assert result.accession_no == "0001234567-24-000001"

    def test_none_net_value_is_allowed(self) -> None:
        from app.backend.services.insider_service import _build_filing_summary

        ts = make_transaction_summary(net_value=None)
        result = _build_filing_summary(ts, filing_date="2024-03-15", accession_no="ACC1", form_type="4")
        assert result.net_value is None

    def test_none_remaining_shares_is_allowed(self) -> None:
        from app.backend.services.insider_service import _build_filing_summary

        ts = make_transaction_summary(remaining_shares=None)
        result = _build_filing_summary(ts, filing_date="2024-03-15", accession_no="ACC1", form_type="4")
        assert result.remaining_shares is None

    def test_form3_initial_ownership_summary(self) -> None:
        """Form 3 InitialOwnershipSummary yields total_holdings and has_derivatives fields."""
        from app.backend.services.insider_service import _build_filing_summary

        ios = make_initial_ownership_summary()
        result = _build_filing_summary(ios, filing_date="2024-01-10", accession_no="0000320193-24-000015", form_type="3")

        assert result.form_type == "3"
        assert result.total_holdings == 5000
        assert result.has_derivatives is False
        assert result.net_change == 0
        assert result.primary_activity == "Initial Holdings"
