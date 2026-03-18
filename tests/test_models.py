from src.data.models import FinancialMetrics


def test_financial_metrics_has_cash_flow_fields():
    m = FinancialMetrics(
        ticker="03690",
        report_period="2024-12-31",
        period="ttm",
        currency="HKD",
        operating_cash_flow=57146784000.0,
        capital_expenditure=10999490000.0,
        investing_cash_flow=10205252000.0,
        financing_cash_flow=-30414660000.0,
    )
    assert m.operating_cash_flow == 57146784000.0
    assert m.capital_expenditure == 10999490000.0
    assert m.investing_cash_flow == 10205252000.0
    assert m.financing_cash_flow == -30414660000.0


def test_financial_metrics_has_balance_sheet_fields():
    m = FinancialMetrics(
        ticker="03690",
        report_period="2024-12-31",
        period="ttm",
        currency="HKD",
        cash_and_equivalents=90383717000.0,
        current_assets=209734861000.0,
        current_liabilities=107935640000.0,
    )
    assert m.cash_and_equivalents == 90383717000.0
    assert m.current_assets == 209734861000.0
    assert m.current_liabilities == 107935640000.0


def test_financial_metrics_has_income_statement_fields():
    m = FinancialMetrics(
        ticker="03690",
        report_period="2024-12-31",
        period="ttm",
        currency="HKD",
        gross_profit=129784594000.0,
        operating_income=37985429000.0,
        research_and_development=21053601000.0,
    )
    assert m.gross_profit == 129784594000.0
    assert m.operating_income == 37985429000.0
    assert m.research_and_development == 21053601000.0


def test_financial_metrics_new_fields_default_to_none():
    m = FinancialMetrics(
        ticker="AAPL",
        report_period="2024-12-31",
        period="ttm",
        currency="USD",
    )
    assert m.operating_cash_flow is None
    assert m.capital_expenditure is None
    assert m.cash_and_equivalents is None
    assert m.gross_profit is None
    assert m.research_and_development is None
