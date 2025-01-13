from pydantic import BaseModel

class FinancialMetrics(BaseModel):
    ticker: str
    calendar_date: str
    report_period: str
    period: str
    currency: str
    market_cap: float | None
    enterprise_value: float | None
    price_to_earnings_ratio: float | None
    price_to_book_ratio: float | None
    price_to_sales_ratio: float | None
    enterprise_value_to_ebitda_ratio: float | None
    enterprise_value_to_revenue_ratio: float | None
    free_cash_flow_yield: float | None
    peg_ratio: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    return_on_equity: float | None
    return_on_assets: float | None
    return_on_invested_capital: float | None
    asset_turnover: float | None
    inventory_turnover: float | None
    receivables_turnover: float | None
    days_sales_outstanding: float | None
    operating_cycle: float | None
    working_capital_turnover: float | None
    current_ratio: float | None
    quick_ratio: float | None
    cash_ratio: float | None
    operating_cash_flow_ratio: float | None
    debt_to_equity: float | None
    debt_to_assets: float | None
    interest_coverage: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    book_value_growth: float | None
    earnings_per_share_growth: float | None
    free_cash_flow_growth: float | None
    operating_income_growth: float | None
    ebitda_growth: float | None
    payout_ratio: float | None
    earnings_per_share: float | None
    book_value_per_share: float | None
    free_cash_flow_per_share: float | None

class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics] 