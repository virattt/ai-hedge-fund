"""Tests for ownership change Pydantic schemas (Phase 5.1).

Verifies field types, defaults, required/optional constraints, and serialization
for OwnershipChangeRecord and OwnershipChangesResponse introduced in Phase 5.
"""
import pytest
from pydantic import ValidationError

from app.backend.models.insider_schemas import OwnershipChangeRecord, OwnershipChangesResponse


# ---------------------------------------------------------------------------
# OwnershipChangeRecord
# ---------------------------------------------------------------------------


class TestOwnershipChangeRecord:
    """Tests for the per-filing ownership change row schema."""

    def _make_record(self, **overrides) -> dict:
        base = {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": "Tim Cook",
            "position": "CEO",
            "shares_before": 3330000,
            "shares_after": 3280000,
            "net_change": -50000,
            "form_type": "4",
        }
        base.update(overrides)
        return base

    def test_valid_record_instantiates(self) -> None:
        """A fully populated record instantiates without errors."""
        record = OwnershipChangeRecord(**self._make_record())
        assert record.filing_date == "2024-03-15"
        assert record.accession_no == "0000320193-24-000081"
        assert record.insider_name == "Tim Cook"
        assert record.net_change == -50000
        assert record.shares_before == 3330000
        assert record.shares_after == 3280000

    def test_net_change_is_required(self) -> None:
        """Omitting net_change must raise ValidationError."""
        data = self._make_record()
        del data["net_change"]
        with pytest.raises(ValidationError):
            OwnershipChangeRecord(**data)

    def test_shares_before_is_optional(self) -> None:
        """shares_before may be None when remaining_shares was not available."""
        record = OwnershipChangeRecord(**self._make_record(shares_before=None))
        assert record.shares_before is None

    def test_shares_after_is_optional(self) -> None:
        """shares_after (remaining_shares) may be None."""
        record = OwnershipChangeRecord(**self._make_record(shares_after=None))
        assert record.shares_after is None

    def test_serialization_includes_all_fields(self) -> None:
        """model_dump() must include all required fields."""
        record = OwnershipChangeRecord(**self._make_record())
        dumped = record.model_dump()
        assert "filing_date" in dumped
        assert "accession_no" in dumped
        assert "insider_name" in dumped
        assert "position" in dumped
        assert "net_change" in dumped
        assert "shares_before" in dumped
        assert "shares_after" in dumped

    def test_shares_before_null_when_no_remaining_shares(self) -> None:
        """Explicitly passing None for shares_before results in null serialization."""
        record = OwnershipChangeRecord(**self._make_record(shares_before=None))
        dumped = record.model_dump()
        assert dumped["shares_before"] is None

    def test_net_change_can_be_positive(self) -> None:
        """Positive net_change (purchase) is accepted."""
        record = OwnershipChangeRecord(**self._make_record(net_change=10000))
        assert record.net_change == 10000

    def test_net_change_can_be_negative(self) -> None:
        """Negative net_change (sale) is accepted."""
        record = OwnershipChangeRecord(**self._make_record(net_change=-5000))
        assert record.net_change == -5000


# ---------------------------------------------------------------------------
# OwnershipChangesResponse
# ---------------------------------------------------------------------------


class TestOwnershipChangesResponse:
    """Tests for the top-level ownership changes endpoint response schema."""

    def _make_record_dict(self, insider_name: str = "Tim Cook", net_change: int = -50000) -> dict:
        return {
            "filing_date": "2024-03-15",
            "accession_no": "0000320193-24-000081",
            "insider_name": insider_name,
            "position": "CEO",
            "shares_before": 3330000,
            "shares_after": 3280000,
            "net_change": net_change,
            "form_type": "4",
        }

    def _make_response(self, **overrides) -> dict:
        base = {
            "ticker": "AAPL",
            "records": [self._make_record_dict()],
            "insiders": ["Tim Cook"],
            "total": 1,
        }
        base.update(overrides)
        return base

    def test_valid_response_instantiates(self) -> None:
        """A fully populated response instantiates without errors."""
        response = OwnershipChangesResponse(**self._make_response())
        assert response.ticker == "AAPL"
        assert response.total == 1
        assert len(response.records) == 1
        assert response.insiders == ["Tim Cook"]

    def test_skipped_count_defaults_to_zero(self) -> None:
        """skipped_count defaults to 0 when not provided."""
        response = OwnershipChangesResponse(**self._make_response())
        assert response.skipped_count == 0

    def test_skipped_count_can_be_set(self) -> None:
        """skipped_count accepts a non-zero value."""
        response = OwnershipChangesResponse(**self._make_response(skipped_count=3))
        assert response.skipped_count == 3

    def test_records_are_typed(self) -> None:
        """records list entries are OwnershipChangeRecord instances."""
        response = OwnershipChangesResponse(**self._make_response())
        assert isinstance(response.records[0], OwnershipChangeRecord)

    def test_empty_records_list_accepted(self) -> None:
        """An empty records list with total=0 is valid."""
        response = OwnershipChangesResponse(**self._make_response(records=[], insiders=[], total=0))
        assert response.records == []
        assert response.total == 0

    def test_insiders_ordering_preserved(self) -> None:
        """insiders list preserves the provided order (sorted by activity count in service)."""
        insiders = ["Tim Cook", "Luca Maestri", "Jeff Williams"]
        response = OwnershipChangesResponse(**self._make_response(insiders=insiders))
        assert response.insiders == insiders

    def test_multiple_records_from_different_insiders(self) -> None:
        """Multiple records for different insiders are all preserved."""
        records = [
            self._make_record_dict(insider_name="Tim Cook"),
            self._make_record_dict(insider_name="Luca Maestri"),
        ]
        response = OwnershipChangesResponse(**self._make_response(records=records, insiders=["Tim Cook", "Luca Maestri"], total=2))
        assert len(response.records) == 2
        assert response.records[0].insider_name == "Tim Cook"
        assert response.records[1].insider_name == "Luca Maestri"

    def test_serialization_includes_skipped_count(self) -> None:
        """model_dump() includes skipped_count key."""
        response = OwnershipChangesResponse(**self._make_response(skipped_count=2))
        dumped = response.model_dump()
        assert dumped["skipped_count"] == 2
        assert dumped["ticker"] == "AAPL"
