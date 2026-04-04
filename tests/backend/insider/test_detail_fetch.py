"""Tests for _fetch_detail() and get_insider_detail() in _detail.py (Remediation.2).

Covers:
- Happy path: filing found, both market + derivative trades parsed
- Filing not found → ValueError raised
- Identity extraction failure → insider_name/position default to empty strings
- market_trades parse exception → skipped gracefully, derivative still parsed
- derivative_trades parse exception → skipped gracefully, market still parsed
- Ticker uppercased in response
- Empty DataFrames produce zero trade counts
- get_insider_detail: async entry point delegates to _fetch_detail via asyncio.to_thread
- get_insider_detail: propagates ValueError from _fetch_detail
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.backend.models.insider_schemas import InsiderDetailResponse, InsiderTransactionDetail


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------


def _make_market_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a fake market_trades DataFrame matching edgartools columns."""
    defaults = {"Security": "Common Stock", "Date": "2024-03-15", "Code": "S", "Shares": 25000.0, "Price": 175.0, "AcquiredDisposed": "D"}
    if rows is None:
        rows = [defaults]
    return pd.DataFrame([dict(defaults, **row) for row in rows])


def _make_derivative_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a fake derivative_trades DataFrame matching edgartools columns."""
    defaults = {"Security": "Stock Option", "Date": "2024-03-15", "Code": "M", "Shares": 50000.0, "Price": None, "AcquiredDisposed": "A"}
    if rows is None:
        rows = [defaults]
    return pd.DataFrame([dict(defaults, **row) for row in rows])


def _make_transaction_summary(
    insider_name: str = "Tim Cook",
    position: str = "CEO",
) -> SimpleNamespace:
    """Build a fake TransactionSummary-compatible namespace."""
    return SimpleNamespace(
        insider_name=insider_name,
        position=position,
        primary_activity="Sale",
        net_change=-25000,
        net_value=4375000.0,
        remaining_shares=3000000,
        has_10b5_1_plan=True,
        transaction_types=["Sale"],
        transaction_count=1,
    )


def _make_ownership_mock(
    *,
    market_df: pd.DataFrame | None = None,
    derivative_df: pd.DataFrame | None = None,
    summary: SimpleNamespace | None = None,
    raise_on_summary: Exception | None = None,
) -> MagicMock:
    """Build a mock ownership object returned by filing.obj()."""
    ownership = MagicMock()
    if raise_on_summary is not None:
        ownership.get_ownership_summary.side_effect = raise_on_summary
    else:
        ownership.get_ownership_summary.return_value = summary
    ownership.market_trades = market_df if market_df is not None else pd.DataFrame()
    ownership.derivative_trades = derivative_df if derivative_df is not None else pd.DataFrame()
    return ownership


def _make_filing_mock(
    accession_no: str = "0000320193-24-000081",
    filing_date: str = "2024-03-15",
    ownership: MagicMock | None = None,
) -> MagicMock:
    """Build a mock edgartools Filing object."""
    filing = MagicMock()
    filing.accession_no = accession_no
    filing.filing_date = filing_date
    filing.obj.return_value = ownership if ownership is not None else MagicMock()
    return filing


_COMPANY_PATCH = "edgar.Company"


# ---------------------------------------------------------------------------
# _fetch_detail
# ---------------------------------------------------------------------------


class TestFetchDetail:
    """Tests for the synchronous _fetch_detail() worker."""

    def test_happy_path_market_and_derivative_trades(self) -> None:
        """Filing found: both market and derivative trades parsed into transactions."""
        from app.backend.services.insider_service._detail import _fetch_detail

        ownership = _make_ownership_mock(
            market_df=_make_market_df(),
            derivative_df=_make_derivative_df(),
            summary=_make_transaction_summary(),
        )
        filing = _make_filing_mock(ownership=ownership)

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                result = _fetch_detail("AAPL", "4", "0000320193-24-000081")

        assert isinstance(result, InsiderDetailResponse)
        assert result.ticker == "AAPL"
        assert result.insider_name == "Tim Cook"
        assert result.position == "CEO"
        assert result.market_trades_count == 1
        assert result.derivative_trades_count == 1
        assert len(result.transactions) == 2

    def test_filing_not_found_raises_value_error(self) -> None:
        """No filing matches accession_no → ValueError raised."""
        from app.backend.services.insider_service._detail import _fetch_detail

        other_filing = _make_filing_mock(accession_no="0000000000-99-000000")

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [other_filing]
                with pytest.raises(ValueError, match="Filing .* not found"):
                    _fetch_detail("AAPL", "4", "0000320193-24-000081")

    def test_identity_extraction_failure_handled_gracefully(self) -> None:
        """get_ownership_summary() raises → insider_name/position default to empty strings."""
        from app.backend.services.insider_service._detail import _fetch_detail

        ownership = _make_ownership_mock(raise_on_summary=RuntimeError("no summary"))
        filing = _make_filing_mock(ownership=ownership)

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                result = _fetch_detail("AAPL", "4", "0000320193-24-000081")

        assert result.insider_name == ""
        assert result.position == ""

    def test_market_trades_parse_error_skipped_derivative_still_parsed(self) -> None:
        """_parse_trade_rows raises for market trades → skipped, derivative still parsed."""
        from app.backend.services.insider_service._detail import _fetch_detail

        fake_deriv_record = InsiderTransactionDetail(
            transaction_type="Exercise", code="M", shares=50000.0,
            price_per_share=None, value=None, security_type="derivative",
            security_title="Stock Option", is_derivative=True,
        )

        ownership = _make_ownership_mock()
        filing = _make_filing_mock(ownership=ownership)

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                with patch(
                    "app.backend.services.insider_service._detail._parse_trade_rows",
                    side_effect=[RuntimeError("market parse error"), [fake_deriv_record]],
                ):
                    result = _fetch_detail("AAPL", "4", "0000320193-24-000081")

        assert result.market_trades_count == 0
        assert result.derivative_trades_count == 1

    def test_derivative_trades_parse_error_skipped_market_still_parsed(self) -> None:
        """_parse_trade_rows raises for derivative trades → skipped, market still parsed."""
        from app.backend.services.insider_service._detail import _fetch_detail

        fake_market_record = InsiderTransactionDetail(
            transaction_type="Sale", code="S", shares=25000.0,
            price_per_share=175.0, value=4375000.0, security_type="non-derivative",
            security_title="Common Stock", is_derivative=False,
        )

        ownership = _make_ownership_mock()
        filing = _make_filing_mock(ownership=ownership)

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                with patch(
                    "app.backend.services.insider_service._detail._parse_trade_rows",
                    side_effect=[[fake_market_record], RuntimeError("deriv parse error")],
                ):
                    result = _fetch_detail("AAPL", "4", "0000320193-24-000081")

        assert result.market_trades_count == 1
        assert result.derivative_trades_count == 0

    def test_ticker_uppercased_in_response(self) -> None:
        """ticker in the response is always uppercased."""
        from app.backend.services.insider_service._detail import _fetch_detail

        filing = _make_filing_mock(ownership=_make_ownership_mock())

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                result = _fetch_detail("aapl", "4", "0000320193-24-000081")

        assert result.ticker == "AAPL"

    def test_empty_trades_produce_zero_counts(self) -> None:
        """Empty market and derivative DataFrames → zero trade counts."""
        from app.backend.services.insider_service._detail import _fetch_detail

        filing = _make_filing_mock(ownership=_make_ownership_mock(
            market_df=pd.DataFrame(), derivative_df=pd.DataFrame(),
        ))

        with patch("app.backend.services.insider_service._detail._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                result = _fetch_detail("AAPL", "4", "0000320193-24-000081")

        assert result.market_trades_count == 0
        assert result.derivative_trades_count == 0
        assert result.transactions == []


# ---------------------------------------------------------------------------
# get_insider_detail (async entry point)
# ---------------------------------------------------------------------------


class TestGetInsiderDetail:
    """Tests for the async get_insider_detail() entry point."""

    @pytest.mark.asyncio
    async def test_delegates_to_fetch_detail_via_asyncio_to_thread(self) -> None:
        """get_insider_detail calls _fetch_detail and returns its result."""
        expected = InsiderDetailResponse(
            ticker="AAPL", filing_date="2024-03-15",
            accession_no="0000320193-24-000081",
            insider_name="Tim Cook", position="CEO", form_type="4",
            transactions=[], market_trades_count=0, derivative_trades_count=0,
        )
        with patch(
            "app.backend.services.insider_service._detail._fetch_detail",
            return_value=expected,
        ) as mock_fetch:
            from app.backend.services.insider_service._detail import get_insider_detail
            result = await get_insider_detail("AAPL", "4", "0000320193-24-000081")

        mock_fetch.assert_called_once_with("AAPL", "4", "0000320193-24-000081")
        assert result.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_propagates_value_error_from_fetch_detail(self) -> None:
        """ValueError from _fetch_detail (filing not found) propagates to caller."""
        with patch(
            "app.backend.services.insider_service._detail._fetch_detail",
            side_effect=ValueError("Filing not found for AAPL form 4"),
        ):
            from app.backend.services.insider_service._detail import get_insider_detail
            with pytest.raises(ValueError, match="Filing not found"):
                await get_insider_detail("AAPL", "4", "0000000000-00-000000")
