"""Tests for insider trading Pydantic schemas.

Verifies field types, defaults, serialization, and required/optional constraints
for all insider dashboard schemas introduced in Phase 1.1.
"""
import pytest
from pydantic import ValidationError

from app.backend.models.insider_schemas import (
    ActivityByDate,
    InsiderAggregates,
    InsiderDetailResponse,
    InsiderFilingSummary,
    InsiderSummaryResponse,
    InsiderTransactionDetail,
)


# ---------------------------------------------------------------------------
# InsiderFilingSummary
# ---------------------------------------------------------------------------


class TestInsiderFilingSummary:
    """Tests for the per-filing summary schema."""

    def _make_summary(self, **overrides) -> dict:
        base = {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "primary_activity": "Sale",
            "net_change": -50000,
            "net_value": 8750000.0,
            "remaining_shares": 3280000,
            "has_10b5_1_plan": True,
            "transaction_types": ["Sale"],
            "transaction_count": 2,
            "form_type": "4",
        }
        base.update(overrides)
        return base

    def test_accession_no_is_required(self) -> None:
        """accession_no is a required field - omitting it must raise ValidationError."""
        data = self._make_summary()
        del data["accession_no"]
        with pytest.raises(ValidationError):
            InsiderFilingSummary(**data)

    def test_valid_summary_instantiates(self) -> None:
        """A fully populated summary must instantiate without errors."""
        summary = InsiderFilingSummary(**self._make_summary())
        assert summary.accession_no == "0000320193-24-000081"
        assert summary.insider_name == "Tim Cook"
        assert summary.net_change == -50000
        assert summary.net_value == 8750000.0
        assert summary.has_10b5_1_plan is True

    def test_filing_index_field_is_absent(self) -> None:
        """The old filing_index field must not exist in the serialized output."""
        summary = InsiderFilingSummary(**self._make_summary())
        dumped = summary.model_dump()
        assert "filing_index" not in dumped

    def test_optional_fields_default_to_none(self) -> None:
        """remaining_shares, net_value, and has_10b5_1_plan may be None."""
        data = self._make_summary(
            remaining_shares=None,
            net_value=None,
            has_10b5_1_plan=None,
        )
        summary = InsiderFilingSummary(**data)
        assert summary.remaining_shares is None
        assert summary.net_value is None
        assert summary.has_10b5_1_plan is None

    def test_form3_extra_fields_accepted(self) -> None:
        """Form 3 fields (total_holdings, has_derivatives) must be accepted."""
        data = self._make_summary(
            form_type="3",
            primary_activity="Initial Holdings",
            net_change=0,
            net_value=0,
            total_holdings=5000,
            has_derivatives=False,
        )
        summary = InsiderFilingSummary(**data)
        assert summary.total_holdings == 5000
        assert summary.has_derivatives is False

    def test_transaction_types_defaults_to_empty_list(self) -> None:
        """transaction_types should default to an empty list when omitted."""
        data = self._make_summary()
        del data["transaction_types"]
        summary = InsiderFilingSummary(**data)
        assert summary.transaction_types == []

    def test_serialization_round_trip(self) -> None:
        """model_dump() output must contain accession_no and exclude filing_index."""
        summary = InsiderFilingSummary(**self._make_summary())
        dumped = summary.model_dump()
        assert "accession_no" in dumped
        assert "filing_index" not in dumped


# ---------------------------------------------------------------------------
# ActivityByDate
# ---------------------------------------------------------------------------


class TestActivityByDate:
    """Tests for the monthly chart-data schema."""

    def test_valid_activity_instantiates(self) -> None:
        """All required fields must populate correctly."""
        activity = ActivityByDate(
            date="2024-03",
            purchases=3,
            sales=8,
            purchase_value=500000.0,
            sale_value=12000000.0,
        )
        assert activity.date == "2024-03"
        assert activity.purchases == 3
        assert activity.sale_value == 12000000.0

    def test_date_is_required(self) -> None:
        """Omitting date must raise ValidationError."""
        with pytest.raises(ValidationError):
            ActivityByDate(purchases=1, sales=0, purchase_value=0.0, sale_value=0.0)

    def test_counts_default_to_zero(self) -> None:
        """purchases and sales should default to 0 when omitted."""
        activity = ActivityByDate(date="2024-01", purchase_value=0.0, sale_value=0.0)
        assert activity.purchases == 0
        assert activity.sales == 0


# ---------------------------------------------------------------------------
# InsiderAggregates
# ---------------------------------------------------------------------------


class TestInsiderAggregates:
    """Tests for the dashboard-level aggregate stats schema."""

    def _make_aggregates(self, **overrides) -> dict:
        base = {
            "total_filings": 50,
            "total_purchases": 12,
            "total_sales": 35,
            "total_other": 3,
            "net_sentiment": -23,
            "largest_transaction_value": 15000000.0,
            "largest_transaction_insider": "Tim Cook",
            "plan_10b5_1_count": 28,
            "plan_10b5_1_ratio": 0.56,
            "activity_by_date": [
                {
                    "date": "2024-03",
                    "purchases": 3,
                    "sales": 8,
                    "purchase_value": 500000.0,
                    "sale_value": 12000000.0,
                }
            ],
        }
        base.update(overrides)
        return base

    def test_valid_aggregates_instantiates(self) -> None:
        """A fully populated aggregates object must instantiate without errors."""
        agg = InsiderAggregates(**self._make_aggregates())
        assert agg.total_filings == 50
        assert agg.net_sentiment == -23
        assert agg.plan_10b5_1_ratio == 0.56
        assert len(agg.activity_by_date) == 1

    def test_activity_by_date_items_are_typed(self) -> None:
        """activity_by_date entries must be ActivityByDate instances."""
        agg = InsiderAggregates(**self._make_aggregates())
        assert isinstance(agg.activity_by_date[0], ActivityByDate)

    def test_optional_aggregate_fields(self) -> None:
        """largest_transaction_insider may be None when no filings exist."""
        data = self._make_aggregates(
            largest_transaction_value=None,
            largest_transaction_insider=None,
        )
        agg = InsiderAggregates(**data)
        assert agg.largest_transaction_insider is None

    def test_activity_by_date_defaults_empty(self) -> None:
        """activity_by_date should default to an empty list when omitted."""
        data = self._make_aggregates()
        del data["activity_by_date"]
        agg = InsiderAggregates(**data)
        assert agg.activity_by_date == []


# ---------------------------------------------------------------------------
# InsiderSummaryResponse
# ---------------------------------------------------------------------------


class TestInsiderSummaryResponse:
    """Tests for the top-level summary endpoint response schema."""

    def _make_response(self, **overrides) -> dict:
        filing = {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "primary_activity": "Sale",
            "net_change": -50000,
            "net_value": 8750000.0,
            "remaining_shares": 3280000,
            "has_10b5_1_plan": True,
            "transaction_types": ["Sale"],
            "transaction_count": 2,
            "form_type": "4",
        }
        aggregates = {
            "total_filings": 1,
            "total_purchases": 0,
            "total_sales": 1,
            "total_other": 0,
            "net_sentiment": -1,
            "largest_transaction_value": 8750000.0,
            "largest_transaction_insider": "Tim Cook",
            "plan_10b5_1_count": 1,
            "plan_10b5_1_ratio": 1.0,
            "activity_by_date": [],
        }
        base = {
            "ticker": "AAPL",
            "form_type": "4",
            "filings": [filing],
            "aggregates": aggregates,
            "total": 1,
        }
        base.update(overrides)
        return base

    def test_skipped_count_defaults_to_zero(self) -> None:
        """skipped_count must default to 0 when not provided."""
        response = InsiderSummaryResponse(**self._make_response())
        assert response.skipped_count == 0

    def test_skipped_count_can_be_set(self) -> None:
        """skipped_count must accept a non-zero value."""
        response = InsiderSummaryResponse(**self._make_response(skipped_count=3))
        assert response.skipped_count == 3

    def test_filings_are_typed(self) -> None:
        """filings list entries must be InsiderFilingSummary instances."""
        response = InsiderSummaryResponse(**self._make_response())
        assert isinstance(response.filings[0], InsiderFilingSummary)

    def test_aggregates_are_typed(self) -> None:
        """aggregates must be an InsiderAggregates instance."""
        response = InsiderSummaryResponse(**self._make_response())
        assert isinstance(response.aggregates, InsiderAggregates)

    def test_ticker_and_form_type_present(self) -> None:
        """Top-level ticker and form_type fields must be present."""
        response = InsiderSummaryResponse(**self._make_response())
        assert response.ticker == "AAPL"
        assert response.form_type == "4"

    def test_serialization_includes_skipped_count(self) -> None:
        """model_dump() output must include skipped_count key."""
        response = InsiderSummaryResponse(**self._make_response(skipped_count=2))
        dumped = response.model_dump()
        assert dumped["skipped_count"] == 2


# ---------------------------------------------------------------------------
# InsiderTransactionDetail
# ---------------------------------------------------------------------------


class TestInsiderTransactionDetail:
    """Tests for the per-transaction detail row schema."""

    def _make_transaction(self, **overrides) -> dict:
        base = {
            "transaction_type": "Sale",
            "code": "S",
            "description": "Open market or private sale",
            "shares": 25000.0,
            "price_per_share": 175.0,
            "value": 4375000.0,
            "security_type": "non-derivative",
            "security_title": "Common Stock",
            "is_10b5_1_plan": True,
            "is_derivative": False,
        }
        base.update(overrides)
        return base

    def test_valid_transaction_instantiates(self) -> None:
        """A fully populated transaction must instantiate without errors."""
        tx = InsiderTransactionDetail(**self._make_transaction())
        assert tx.transaction_type == "Sale"
        assert tx.code == "S"
        assert tx.shares == 25000.0
        assert tx.is_derivative is False

    def test_optional_fields_accept_none(self) -> None:
        """shares, price_per_share, value may be None."""
        data = self._make_transaction(shares=None, price_per_share=None, value=None)
        tx = InsiderTransactionDetail(**data)
        assert tx.shares is None
        assert tx.price_per_share is None
        assert tx.value is None

    def test_is_10b5_1_plan_defaults_to_none(self) -> None:
        """is_10b5_1_plan should default to None when omitted."""
        data = self._make_transaction()
        del data["is_10b5_1_plan"]
        tx = InsiderTransactionDetail(**data)
        assert tx.is_10b5_1_plan is None


# ---------------------------------------------------------------------------
# InsiderDetailResponse
# ---------------------------------------------------------------------------


class TestInsiderDetailResponse:
    """Tests for the detail endpoint response schema."""

    def _make_detail_response(self, **overrides) -> dict:
        transaction = {
            "transaction_type": "Sale",
            "code": "S",
            "description": "Open market or private sale",
            "shares": 25000.0,
            "price_per_share": 175.0,
            "value": 4375000.0,
            "security_type": "non-derivative",
            "security_title": "Common Stock",
            "is_10b5_1_plan": True,
            "is_derivative": False,
        }
        base = {
            "ticker": "AAPL",
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "form_type": "4",
            "transactions": [transaction],
            "market_trades_count": 2,
            "derivative_trades_count": 0,
        }
        base.update(overrides)
        return base

    def test_accession_no_is_required(self) -> None:
        """accession_no is required on the detail response."""
        data = self._make_detail_response()
        del data["accession_no"]
        with pytest.raises(ValidationError):
            InsiderDetailResponse(**data)

    def test_valid_response_instantiates(self) -> None:
        """A fully populated detail response must instantiate without errors."""
        response = InsiderDetailResponse(**self._make_detail_response())
        assert response.accession_no == "0000320193-24-000081"
        assert response.ticker == "AAPL"
        assert response.market_trades_count == 2
        assert response.derivative_trades_count == 0

    def test_transactions_are_typed(self) -> None:
        """transactions list entries must be InsiderTransactionDetail instances."""
        response = InsiderDetailResponse(**self._make_detail_response())
        assert isinstance(response.transactions[0], InsiderTransactionDetail)

    def test_empty_transactions_list_accepted(self) -> None:
        """An empty transactions list is valid."""
        response = InsiderDetailResponse(**self._make_detail_response(transactions=[]))
        assert response.transactions == []

    def test_serialization_includes_accession_no(self) -> None:
        """model_dump() output must include accession_no key."""
        response = InsiderDetailResponse(**self._make_detail_response())
        dumped = response.model_dump()
        assert "accession_no" in dumped
        assert dumped["accession_no"] == "0000320193-24-000081"
