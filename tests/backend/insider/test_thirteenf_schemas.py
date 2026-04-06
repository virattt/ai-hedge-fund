"""Tests for new 13-F Pydantic schemas in insider_schemas.py (Phase 1.2).

Verifies required fields, optional defaults, and serialization for:
- ThirteenFFilingListItem
- ThirteenFListResponse
- CompareHoldingsRecord
- CompareHoldingsResponse
- HoldingHistoryRecord
- HoldingHistoryResponse
"""
import pytest
from pydantic import ValidationError

from app.backend.models.insider_schemas import (
    CompareHoldingsRecord,
    CompareHoldingsResponse,
    HoldingHistoryRecord,
    HoldingHistoryResponse,
    ThirteenFFilingListItem,
    ThirteenFListResponse,
)


# ---------------------------------------------------------------------------
# ThirteenFFilingListItem
# ---------------------------------------------------------------------------


class TestThirteenFFilingListItem:
    """Tests for the lightweight filing listing entry schema."""

    def _make_item(self, **overrides) -> dict:
        base = {
            "filing_date": "2026-03-15",
            "accession_no": "0001234567-26-000001",
            "company": "BERKSHIRE HATHAWAY INC",
            "cik": 1067983,
            "form": "13F-HR",
        }
        base.update(overrides)
        return base

    def test_thirteenf_filing_list_item_required_fields(self) -> None:
        """All five fields are required and populate correctly."""
        item = ThirteenFFilingListItem(**self._make_item())
        assert item.filing_date == "2026-03-15"
        assert item.accession_no == "0001234567-26-000001"
        assert item.company == "BERKSHIRE HATHAWAY INC"
        assert item.cik == 1067983
        assert item.form == "13F-HR"

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Omitting any required field raises ValidationError."""
        for field in ("filing_date", "accession_no", "company", "cik", "form"):
            data = self._make_item()
            del data[field]
            with pytest.raises(ValidationError):
                ThirteenFFilingListItem(**data)

    def test_cik_is_int(self) -> None:
        """cik field accepts and stores an integer CIK value."""
        item = ThirteenFFilingListItem(**self._make_item(cik=9876543))
        assert item.cik == 9876543

    def test_serialization_includes_all_fields(self) -> None:
        """model_dump() contains all five declared fields."""
        item = ThirteenFFilingListItem(**self._make_item())
        dumped = item.model_dump()
        for field in ("filing_date", "accession_no", "company", "cik", "form"):
            assert field in dumped


# ---------------------------------------------------------------------------
# ThirteenFListResponse
# ---------------------------------------------------------------------------


class TestThirteenFListResponse:
    """Tests for the paginated 13-F filing listing response schema."""

    def _make_item_dict(self, **overrides) -> dict:
        base = {
            "filing_date": "2026-03-15",
            "accession_no": "0001234567-26-000001",
            "company": "BERKSHIRE HATHAWAY INC",
            "cik": 1067983,
            "form": "13F-HR",
        }
        base.update(overrides)
        return base

    def _make_response(self, **overrides) -> dict:
        base = {
            "filings": [self._make_item_dict()],
            "total": 5000,
            "has_more": True,
        }
        base.update(overrides)
        return base

    def test_valid_response_instantiates(self) -> None:
        """A fully populated response instantiates without errors."""
        response = ThirteenFListResponse(**self._make_response())
        assert response.total == 5000
        assert response.has_more is True
        assert len(response.filings) == 1

    def test_skipped_count_defaults_to_zero(self) -> None:
        """skipped_count defaults to 0 when not provided."""
        response = ThirteenFListResponse(**self._make_response())
        assert response.skipped_count == 0

    def test_skipped_count_can_be_set(self) -> None:
        """skipped_count accepts a non-zero value."""
        response = ThirteenFListResponse(**self._make_response(skipped_count=3))
        assert response.skipped_count == 3

    def test_filings_are_typed(self) -> None:
        """filings list entries are ThirteenFFilingListItem instances."""
        response = ThirteenFListResponse(**self._make_response())
        assert isinstance(response.filings[0], ThirteenFFilingListItem)

    def test_empty_filings_accepted(self) -> None:
        """An empty filings list with total=0 and has_more=False is valid."""
        response = ThirteenFListResponse(**self._make_response(filings=[], total=0, has_more=False))
        assert response.filings == []
        assert response.total == 0
        assert response.has_more is False

    def test_has_more_false_serializes_correctly(self) -> None:
        """has_more=False round-trips through model_dump() correctly."""
        response = ThirteenFListResponse(**self._make_response(has_more=False))
        assert response.model_dump()["has_more"] is False


# ---------------------------------------------------------------------------
# CompareHoldingsRecord
# ---------------------------------------------------------------------------


class TestCompareHoldingsRecord:
    """Tests for a single row from compare_holdings() DataFrame schema."""

    def _make_record(self, **overrides) -> dict:
        base = {
            "cusip": "023135106",
            "ticker": "AMZN",
            "issuer": "AMAZON COM INC",
            "shares": 10000000,
            "prev_shares": 8000000,
            "value": 1500000,
            "prev_value": 1200000,
            "share_change": 2000000,
            "share_change_pct": 25.0,
            "value_change": 300000,
            "value_change_pct": 25.0,
            "status": "INCREASED",
        }
        base.update(overrides)
        return base

    def test_compare_holdings_record_all_fields(self) -> None:
        """A fully populated record instantiates and stores all values correctly."""
        record = CompareHoldingsRecord(**self._make_record())
        assert record.cusip == "023135106"
        assert record.ticker == "AMZN"
        assert record.issuer == "AMAZON COM INC"
        assert record.shares == 10000000
        assert record.prev_shares == 8000000
        assert record.value == 1500000
        assert record.prev_value == 1200000
        assert record.share_change == 2000000
        assert record.share_change_pct == pytest.approx(25.0)
        assert record.value_change == 300000
        assert record.value_change_pct == pytest.approx(25.0)
        assert record.status == "INCREASED"

    def test_optional_numeric_fields_default_to_none(self) -> None:
        """All numeric fields except status are optional and default to None."""
        record = CompareHoldingsRecord(cusip="023135106", ticker=None, issuer="AMAZON COM INC", status="NEW")
        assert record.shares is None
        assert record.prev_shares is None
        assert record.value is None
        assert record.prev_value is None
        assert record.share_change is None
        assert record.share_change_pct is None
        assert record.value_change is None
        assert record.value_change_pct is None

    def test_ticker_is_optional(self) -> None:
        """ticker field accepts None (when SEC data lacks a ticker mapping)."""
        record = CompareHoldingsRecord(**self._make_record(ticker=None))
        assert record.ticker is None

    def test_status_field_accepted_values(self) -> None:
        """status field accepts all expected status string values."""
        for status in ("NEW", "CLOSED", "INCREASED", "DECREASED", "UNCHANGED"):
            record = CompareHoldingsRecord(**self._make_record(status=status))
            assert record.status == status

    def test_missing_required_fields_raises_validation_error(self) -> None:
        """cusip, issuer, and status are required; omitting any raises ValidationError."""
        for field in ("cusip", "issuer", "status"):
            data = {"cusip": "023135106", "ticker": None, "issuer": "AMAZON COM INC", "status": "NEW"}
            del data[field]
            with pytest.raises(ValidationError):
                CompareHoldingsRecord(**data)

    def test_serialization_includes_all_fields(self) -> None:
        """model_dump() includes all twelve declared fields."""
        record = CompareHoldingsRecord(**self._make_record())
        dumped = record.model_dump()
        for field in (
            "cusip", "ticker", "issuer", "shares", "prev_shares", "value",
            "prev_value", "share_change", "share_change_pct", "value_change",
            "value_change_pct", "status",
        ):
            assert field in dumped

    def test_optional_fields_serialize_as_none_when_absent(self) -> None:
        """Optional numeric fields serialize as None in model_dump() when not set."""
        record = CompareHoldingsRecord(cusip="X", ticker=None, issuer="Y", status="NEW")
        dumped = record.model_dump()
        assert dumped["shares"] is None
        assert dumped["prev_shares"] is None
        assert dumped["share_change_pct"] is None
        assert dumped["value_change_pct"] is None


# ---------------------------------------------------------------------------
# CompareHoldingsResponse
# ---------------------------------------------------------------------------


class TestCompareHoldingsResponse:
    """Tests for the /thirteenf/compare endpoint response schema."""

    def _make_record_dict(self, **overrides) -> dict:
        base = {
            "cusip": "023135106",
            "ticker": "AMZN",
            "issuer": "AMAZON COM INC",
            "status": "INCREASED",
        }
        base.update(overrides)
        return base

    def _make_response(self, **overrides) -> dict:
        base = {
            "accession_no": "0001234567-26-000001",
            "current_period": "2025-12-31",
            "previous_period": "2025-09-30",
            "manager_name": "BERKSHIRE HATHAWAY INC",
            "records": [self._make_record_dict()],
            "total": 150,
        }
        base.update(overrides)
        return base

    def test_valid_response_instantiates(self) -> None:
        """A fully populated compare response instantiates without errors."""
        response = CompareHoldingsResponse(**self._make_response())
        assert response.accession_no == "0001234567-26-000001"
        assert response.current_period == "2025-12-31"
        assert response.previous_period == "2025-09-30"
        assert response.manager_name == "BERKSHIRE HATHAWAY INC"
        assert response.total == 150

    def test_records_are_typed(self) -> None:
        """records list entries are CompareHoldingsRecord instances."""
        response = CompareHoldingsResponse(**self._make_response())
        assert isinstance(response.records[0], CompareHoldingsRecord)

    def test_empty_records_accepted(self) -> None:
        """Empty records list with total=0 is valid (e.g., no positions changed)."""
        response = CompareHoldingsResponse(**self._make_response(records=[], total=0))
        assert response.records == []
        assert response.total == 0

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Omitting any required field raises ValidationError."""
        for field in ("accession_no", "current_period", "previous_period", "manager_name", "records", "total"):
            data = self._make_response()
            del data[field]
            with pytest.raises(ValidationError):
                CompareHoldingsResponse(**data)


# ---------------------------------------------------------------------------
# HoldingHistoryRecord
# ---------------------------------------------------------------------------


class TestHoldingHistoryRecord:
    """Tests for a single row from holding_history() DataFrame schema."""

    def test_holding_history_record_periods_data(self) -> None:
        """periods_data dict stores period strings mapped to share counts."""
        record = HoldingHistoryRecord(
            cusip="023135106",
            ticker="AMZN",
            issuer="AMAZON COM INC",
            periods_data={
                "2025-03-31": 7000000,
                "2025-06-30": 8000000,
                "2025-09-30": 9000000,
                "2025-12-31": 10000000,
            },
        )
        assert record.cusip == "023135106"
        assert record.ticker == "AMZN"
        assert record.issuer == "AMAZON COM INC"
        assert record.periods_data["2025-03-31"] == 7000000
        assert record.periods_data["2025-12-31"] == 10000000

    def test_periods_data_values_can_be_none(self) -> None:
        """periods_data values accept None when a holding was absent in that period."""
        record = HoldingHistoryRecord(
            cusip="X",
            ticker=None,
            issuer="SOME CORP",
            periods_data={"2025-03-31": None, "2025-06-30": 5000},
        )
        assert record.periods_data["2025-03-31"] is None
        assert record.periods_data["2025-06-30"] == 5000

    def test_ticker_is_optional(self) -> None:
        """ticker field accepts None."""
        record = HoldingHistoryRecord(cusip="X", ticker=None, issuer="CORP", periods_data={})
        assert record.ticker is None

    def test_missing_required_fields_raises_validation_error(self) -> None:
        """cusip, issuer, and periods_data are required; omitting any raises ValidationError."""
        for field in ("cusip", "issuer", "periods_data"):
            data = {"cusip": "X", "ticker": None, "issuer": "CORP", "periods_data": {}}
            del data[field]
            with pytest.raises(ValidationError):
                HoldingHistoryRecord(**data)

    def test_empty_periods_data_is_valid(self) -> None:
        """An empty periods_data dict is accepted without errors."""
        record = HoldingHistoryRecord(cusip="X", ticker=None, issuer="CORP", periods_data={})
        assert record.periods_data == {}

    def test_serialization_round_trips_periods_data(self) -> None:
        """model_dump() preserves periods_data dict structure exactly."""
        periods = {"2025-03-31": 100, "2025-06-30": None}
        record = HoldingHistoryRecord(cusip="X", ticker="T", issuer="Y", periods_data=periods)
        dumped = record.model_dump()
        assert dumped["periods_data"] == periods


# ---------------------------------------------------------------------------
# HoldingHistoryResponse
# ---------------------------------------------------------------------------


class TestHoldingHistoryResponse:
    """Tests for the /thirteenf/history endpoint response schema."""

    def _make_record_dict(self, **overrides) -> dict:
        base = {
            "cusip": "023135106",
            "ticker": "AMZN",
            "issuer": "AMAZON COM INC",
            "periods_data": {"2025-12-31": 10000000},
        }
        base.update(overrides)
        return base

    def _make_response(self, **overrides) -> dict:
        base = {
            "accession_no": "0001234567-26-000001",
            "manager_name": "BERKSHIRE HATHAWAY INC",
            "periods": ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"],
            "records": [self._make_record_dict()],
            "total": 150,
        }
        base.update(overrides)
        return base

    def test_holding_history_response_serialization(self) -> None:
        """model_dump() includes all fields with correct types."""
        response = HoldingHistoryResponse(**self._make_response())
        dumped = response.model_dump()
        assert dumped["accession_no"] == "0001234567-26-000001"
        assert dumped["manager_name"] == "BERKSHIRE HATHAWAY INC"
        assert dumped["periods"] == ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
        assert dumped["total"] == 150
        assert len(dumped["records"]) == 1

    def test_valid_response_instantiates(self) -> None:
        """A fully populated history response instantiates without errors."""
        response = HoldingHistoryResponse(**self._make_response())
        assert response.accession_no == "0001234567-26-000001"
        assert response.manager_name == "BERKSHIRE HATHAWAY INC"
        assert len(response.periods) == 4
        assert response.total == 150

    def test_records_are_typed(self) -> None:
        """records list entries are HoldingHistoryRecord instances."""
        response = HoldingHistoryResponse(**self._make_response())
        assert isinstance(response.records[0], HoldingHistoryRecord)

    def test_empty_records_and_periods_accepted(self) -> None:
        """Empty records and periods lists with total=0 are valid."""
        response = HoldingHistoryResponse(**self._make_response(records=[], periods=[], total=0))
        assert response.records == []
        assert response.periods == []
        assert response.total == 0

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Omitting any required field raises ValidationError."""
        for field in ("accession_no", "manager_name", "periods", "records", "total"):
            data = self._make_response()
            del data[field]
            with pytest.raises(ValidationError):
                HoldingHistoryResponse(**data)

    def test_periods_data_nested_in_records(self) -> None:
        """Records within the response preserve periods_data nesting."""
        response = HoldingHistoryResponse(**self._make_response())
        assert "2025-12-31" in response.records[0].periods_data
        assert response.records[0].periods_data["2025-12-31"] == 10000000
