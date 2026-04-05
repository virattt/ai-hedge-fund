"""Tests for grants & exercises Pydantic schemas (Phase 6.1).

Verifies field types, defaults, required/optional constraints, and serialization
for GrantRecord and GrantsResponse introduced in Phase 6.
"""
import pytest
from pydantic import ValidationError

from app.backend.models.insider_schemas import GrantRecord, GrantsResponse


# ---------------------------------------------------------------------------
# GrantRecord
# ---------------------------------------------------------------------------


class TestGrantRecord:
    """Tests for the per-derivative-trade grant/exercise row schema."""

    def _make_record(self, **overrides) -> dict:
        base = {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "transaction_type": "Exercise",
            "security_title": "Common Stock",
            "acquired_disposed": "A",
            "code": "M",
        }
        base.update(overrides)
        return base

    def test_valid_record_instantiates(self) -> None:
        """A fully populated record instantiates without errors."""
        record = GrantRecord(**self._make_record(
            exercise_price=0.01,
            expiration_date="2030-01-01",
            shares=50000,
            underlying_security="Common Stock",
        ))
        assert record.filing_date == "2024-03-15"
        assert record.accession_no == "0000320193-24-000081"
        assert record.insider_name == "Tim Cook"
        assert record.transaction_type == "Exercise"
        assert record.exercise_price == pytest.approx(0.01)
        assert record.shares == 50000

    def test_required_fields_present(self) -> None:
        """Omitting a required field raises ValidationError."""
        for required in ("filing_date", "accession_no", "insider_name", "position",
                         "transaction_type", "security_title", "acquired_disposed", "code"):
            data = self._make_record()
            del data[required]
            with pytest.raises(ValidationError):
                GrantRecord(**data)

    def test_exercise_price_is_optional(self) -> None:
        """exercise_price defaults to None when not provided."""
        record = GrantRecord(**self._make_record())
        assert record.exercise_price is None

    def test_expiration_date_is_optional(self) -> None:
        """expiration_date defaults to None when not provided."""
        record = GrantRecord(**self._make_record())
        assert record.expiration_date is None

    def test_shares_is_optional(self) -> None:
        """shares defaults to None when not provided."""
        record = GrantRecord(**self._make_record())
        assert record.shares is None

    def test_underlying_security_is_optional(self) -> None:
        """underlying_security defaults to None when not provided."""
        record = GrantRecord(**self._make_record())
        assert record.underlying_security is None

    def test_exercise_price_can_be_zero(self) -> None:
        """exercise_price accepts 0.0 (common for restricted stock)."""
        record = GrantRecord(**self._make_record(exercise_price=0.0))
        assert record.exercise_price == pytest.approx(0.0)

    def test_acquired_disposed_a(self) -> None:
        """acquired_disposed 'A' is accepted."""
        record = GrantRecord(**self._make_record(acquired_disposed="A"))
        assert record.acquired_disposed == "A"

    def test_acquired_disposed_d(self) -> None:
        """acquired_disposed 'D' is accepted."""
        record = GrantRecord(**self._make_record(acquired_disposed="D"))
        assert record.acquired_disposed == "D"

    def test_transaction_type_grant(self) -> None:
        """transaction_type 'Grant' is accepted."""
        record = GrantRecord(**self._make_record(transaction_type="Grant", code="A"))
        assert record.transaction_type == "Grant"

    def test_transaction_type_conversion(self) -> None:
        """transaction_type 'Conversion' is accepted."""
        record = GrantRecord(**self._make_record(transaction_type="Conversion", code="C"))
        assert record.transaction_type == "Conversion"

    def test_serialization_includes_all_fields(self) -> None:
        """model_dump() includes all declared fields."""
        record = GrantRecord(**self._make_record(
            exercise_price=5.0,
            expiration_date="2030-12-31",
            shares=10000,
            underlying_security="Restricted Stock Unit",
        ))
        dumped = record.model_dump()
        for field in ("filing_date", "accession_no", "insider_name", "position",
                      "transaction_type", "security_title", "exercise_price",
                      "expiration_date", "shares", "underlying_security",
                      "acquired_disposed", "code"):
            assert field in dumped

    def test_optional_fields_serialize_as_none(self) -> None:
        """Optional fields missing at construction serialize as None in model_dump()."""
        record = GrantRecord(**self._make_record())
        dumped = record.model_dump()
        assert dumped["exercise_price"] is None
        assert dumped["expiration_date"] is None
        assert dumped["shares"] is None
        assert dumped["underlying_security"] is None


# ---------------------------------------------------------------------------
# GrantsResponse
# ---------------------------------------------------------------------------


class TestGrantsResponse:
    """Tests for the top-level grants & exercises endpoint response schema."""

    def _make_record_dict(self, **overrides) -> dict:
        base = {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "transaction_type": "Exercise",
            "security_title": "Common Stock",
            "acquired_disposed": "A",
            "code": "M",
        }
        base.update(overrides)
        return base

    def _make_response(self, **overrides) -> dict:
        base = {
            "ticker": "AAPL",
            "records": [self._make_record_dict()],
            "total": 1,
        }
        base.update(overrides)
        return base

    def test_valid_response_instantiates(self) -> None:
        """A fully populated response instantiates without errors."""
        response = GrantsResponse(**self._make_response())
        assert response.ticker == "AAPL"
        assert response.total == 1
        assert len(response.records) == 1

    def test_skipped_count_defaults_to_zero(self) -> None:
        """skipped_count defaults to 0 when not provided."""
        response = GrantsResponse(**self._make_response())
        assert response.skipped_count == 0

    def test_skipped_count_can_be_set(self) -> None:
        """skipped_count accepts a non-zero value."""
        response = GrantsResponse(**self._make_response(skipped_count=5))
        assert response.skipped_count == 5

    def test_records_are_typed(self) -> None:
        """records list entries are GrantRecord instances."""
        response = GrantsResponse(**self._make_response())
        assert isinstance(response.records[0], GrantRecord)

    def test_empty_records_accepted(self) -> None:
        """An empty records list with total=0 is valid."""
        response = GrantsResponse(**self._make_response(records=[], total=0))
        assert response.records == []
        assert response.total == 0

    def test_multiple_records_preserved(self) -> None:
        """Multiple grant records for different transaction types are preserved."""
        records = [
            self._make_record_dict(transaction_type="Grant", code="A"),
            self._make_record_dict(transaction_type="Exercise", code="M"),
        ]
        response = GrantsResponse(**self._make_response(records=records, total=2))
        assert len(response.records) == 2
        assert response.records[0].transaction_type == "Grant"
        assert response.records[1].transaction_type == "Exercise"

    def test_serialization_includes_skipped_count(self) -> None:
        """model_dump() includes skipped_count and ticker."""
        response = GrantsResponse(**self._make_response(skipped_count=2))
        dumped = response.model_dump()
        assert dumped["skipped_count"] == 2
        assert dumped["ticker"] == "AAPL"

    def test_ticker_required(self) -> None:
        """Omitting ticker must raise ValidationError."""
        data = self._make_response()
        del data["ticker"]
        with pytest.raises(ValidationError):
            GrantsResponse(**data)
