"""Tests for _compute_aggregates() and _compute_activity_by_date() in insider_service.py."""
from app.backend.models.insider_schemas import InsiderFilingSummary


def _make_summary(
    *,
    primary_activity: str = "Sale",
    net_change: int = -10000,
    net_value: float | None = 1_000_000.0,
    has_10b5_1_plan: bool | None = None,
    insider_name: str = "A. Insider",
    filing_date: str = "2024-03-15",
    accession_no: str = "ACC1",
    form_type: str = "4",
) -> InsiderFilingSummary:
    return InsiderFilingSummary(
        filing_date=filing_date,
        accession_no=accession_no,
        insider_name=insider_name,
        position="VP",
        primary_activity=primary_activity,
        net_change=net_change,
        net_value=net_value,
        remaining_shares=100_000,
        has_10b5_1_plan=has_10b5_1_plan,
        transaction_types=[primary_activity],
        transaction_count=1,
        form_type=form_type,
    )


class TestComputeAggregates:
    """_compute_aggregates derives dashboard stats from a list of InsiderFilingSummary."""

    def test_counts_purchases_and_sales(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        summaries = [
            _make_summary(primary_activity="Purchase", net_change=1000),
            _make_summary(primary_activity="Sale", net_change=-500),
            _make_summary(primary_activity="Sale", net_change=-200),
        ]
        agg = _compute_aggregates(summaries, form_type="4")
        assert agg.total_purchases == 1
        assert agg.total_sales == 2
        assert agg.total_other == 0
        assert agg.total_filings == 3

    def test_net_sentiment_is_purchases_minus_sales(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        summaries = [
            _make_summary(primary_activity="Purchase", net_change=1000),
            _make_summary(primary_activity="Purchase", net_change=500),
            _make_summary(primary_activity="Sale", net_change=-200),
        ]
        agg = _compute_aggregates(summaries, form_type="4")
        assert agg.net_sentiment == 1  # 2 purchases - 1 sale

    def test_largest_transaction_value_and_insider(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        summaries = [
            _make_summary(net_value=500_000.0, insider_name="Small Seller"),
            _make_summary(net_value=15_000_000.0, insider_name="Tim Cook"),
            _make_summary(net_value=1_000_000.0, insider_name="Another"),
        ]
        agg = _compute_aggregates(summaries, form_type="4")
        assert agg.largest_transaction_value == 15_000_000.0
        assert agg.largest_transaction_insider == "Tim Cook"

    def test_10b5_1_ratio_computed_correctly(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        summaries = [
            _make_summary(has_10b5_1_plan=True),
            _make_summary(has_10b5_1_plan=True),
            _make_summary(has_10b5_1_plan=False),
            _make_summary(has_10b5_1_plan=None),
        ]
        agg = _compute_aggregates(summaries, form_type="4")
        assert agg.plan_10b5_1_count == 2
        assert abs(agg.plan_10b5_1_ratio - 0.5) < 0.001

    def test_empty_summaries_returns_zero_aggregates(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        agg = _compute_aggregates([], form_type="4")
        assert agg.total_filings == 0
        assert agg.net_sentiment == 0
        assert agg.largest_transaction_value is None
        assert agg.plan_10b5_1_ratio == 0.0

    def test_other_activities_are_counted(self) -> None:
        from app.backend.services.insider_service import _compute_aggregates

        summaries = [
            _make_summary(primary_activity="Option Exercise"),
            _make_summary(primary_activity="Gift"),
        ]
        agg = _compute_aggregates(summaries, form_type="4")
        assert agg.total_other == 2
        assert agg.total_purchases == 0
        assert agg.total_sales == 0


class TestComputeActivityByDate:
    """_compute_activity_by_date groups filing summaries into monthly chart buckets."""

    def test_single_sale_creates_monthly_bucket(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        summaries = [_make_summary(primary_activity="Sale", net_value=1_000_000.0, filing_date="2024-03-15")]
        result = _compute_activity_by_date(summaries)
        assert len(result) == 1
        assert result[0].date == "2024-03"
        assert result[0].sales == 1
        assert result[0].purchases == 0

    def test_purchases_and_sales_in_same_month_are_merged(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        summaries = [
            _make_summary(primary_activity="Purchase", net_value=500_000.0, filing_date="2024-03-10"),
            _make_summary(primary_activity="Sale", net_value=1_000_000.0, filing_date="2024-03-20"),
        ]
        result = _compute_activity_by_date(summaries)
        assert len(result) == 1
        assert result[0].purchases == 1
        assert result[0].sales == 1
        assert result[0].purchase_value == 500_000.0
        assert result[0].sale_value == 1_000_000.0

    def test_different_months_create_separate_buckets(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        summaries = [
            _make_summary(primary_activity="Sale", filing_date="2024-01-15"),
            _make_summary(primary_activity="Purchase", filing_date="2024-03-10"),
        ]
        result = _compute_activity_by_date(summaries)
        dates = [r.date for r in result]
        assert "2024-01" in dates
        assert "2024-03" in dates
        assert len(result) == 2

    def test_results_are_sorted_by_date(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        summaries = [
            _make_summary(primary_activity="Sale", filing_date="2024-06-01"),
            _make_summary(primary_activity="Sale", filing_date="2024-01-01"),
            _make_summary(primary_activity="Sale", filing_date="2024-03-01"),
        ]
        result = _compute_activity_by_date(summaries)
        dates = [r.date for r in result]
        assert dates == sorted(dates)

    def test_empty_summaries_returns_empty_list(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        result = _compute_activity_by_date([])
        assert result == []

    def test_none_net_value_does_not_crash(self) -> None:
        from app.backend.services.insider_service import _compute_activity_by_date

        summaries = [_make_summary(primary_activity="Sale", net_value=None, filing_date="2024-03-15")]
        result = _compute_activity_by_date(summaries)
        assert result[0].sale_value == 0.0
