"""Tests for Pydantic data models in src/data/models.py.

Validates schema enforcement, optional field handling, and edge cases
for the core data structures used across the trading system.
"""

import pytest
from pydantic import ValidationError

from src.data.models import (
    AnalystSignal,
    CompanyFacts,
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Portfolio,
    Position,
    Price,
    PriceResponse,
    TickerAnalysis,
)


class TestPrice:
    def test_valid_price(self):
        p = Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1_000_000, time="2024-01-15")
        assert p.close == 105.0
        assert p.volume == 1_000_000

    def test_price_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1_000_000)
            # missing 'time'

    def test_price_negative_values_allowed(self):
        """Price model doesn't enforce positivity — that's a business rule, not schema."""
        p = Price(open=-1.0, close=-2.0, high=0.0, low=-5.0, volume=0, time="2024-01-01")
        assert p.open == -1.0

    def test_price_zero_volume(self):
        p = Price(open=10.0, close=10.0, high=10.0, low=10.0, volume=0, time="2024-01-01")
        assert p.volume == 0


class TestPriceResponse:
    def test_empty_prices_list(self):
        pr = PriceResponse(ticker="AAPL", prices=[])
        assert pr.prices == []
        assert pr.ticker == "AAPL"

    def test_multiple_prices(self):
        prices = [
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1000, time="2024-01-01"),
            Price(open=105.0, close=102.0, high=106.0, low=101.0, volume=2000, time="2024-01-02"),
        ]
        pr = PriceResponse(ticker="MSFT", prices=prices)
        assert len(pr.prices) == 2


class TestFinancialMetrics:
    def test_all_nullable_fields_explicitly_none(self):
        """FinancialMetrics requires all fields, but they accept None."""
        fm = FinancialMetrics(
            ticker="AAPL",
            report_period="2024-Q1",
            period="ttm",
            currency="USD",
            market_cap=None,
            enterprise_value=None,
            price_to_earnings_ratio=None,
            price_to_book_ratio=None,
            price_to_sales_ratio=None,
            enterprise_value_to_ebitda_ratio=None,
            enterprise_value_to_revenue_ratio=None,
            free_cash_flow_yield=None,
            peg_ratio=None,
            gross_margin=None,
            operating_margin=None,
            net_margin=None,
            return_on_equity=None,
            return_on_assets=None,
            return_on_invested_capital=None,
            asset_turnover=None,
            inventory_turnover=None,
            receivables_turnover=None,
            days_sales_outstanding=None,
            operating_cycle=None,
            working_capital_turnover=None,
            current_ratio=None,
            quick_ratio=None,
            cash_ratio=None,
            operating_cash_flow_ratio=None,
            debt_to_equity=None,
            debt_to_assets=None,
            interest_coverage=None,
            revenue_growth=None,
            earnings_growth=None,
            book_value_growth=None,
            earnings_per_share_growth=None,
            free_cash_flow_growth=None,
            operating_income_growth=None,
            ebitda_growth=None,
            payout_ratio=None,
            earnings_per_share=None,
            book_value_per_share=None,
            free_cash_flow_per_share=None,
        )
        assert fm.market_cap is None
        assert fm.debt_to_equity is None

    def test_missing_required_field_raises(self):
        """FinancialMetrics fields are typed float|None but still required."""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                ticker="AAPL",
                report_period="2024-Q1",
                period="ttm",
                currency="USD",
                # missing all the float|None fields
            )

    def test_with_values(self):
        fm = FinancialMetrics(
            ticker="AAPL",
            report_period="2024-Q1",
            period="ttm",
            currency="USD",
            market_cap=3_000_000_000_000.0,
            enterprise_value=3.1e12,
            price_to_earnings_ratio=28.5,
            price_to_book_ratio=45.0,
            price_to_sales_ratio=8.0,
            enterprise_value_to_ebitda_ratio=22.0,
            enterprise_value_to_revenue_ratio=8.5,
            free_cash_flow_yield=0.035,
            peg_ratio=2.1,
            gross_margin=0.45,
            operating_margin=0.30,
            net_margin=0.25,
            return_on_equity=1.5,
            return_on_assets=0.28,
            return_on_invested_capital=0.55,
            asset_turnover=1.1,
            inventory_turnover=35.0,
            receivables_turnover=14.0,
            days_sales_outstanding=26.0,
            operating_cycle=35.0,
            working_capital_turnover=-10.0,
            current_ratio=0.99,
            quick_ratio=0.94,
            cash_ratio=0.30,
            operating_cash_flow_ratio=0.95,
            debt_to_equity=1.87,
            debt_to_assets=0.32,
            interest_coverage=29.0,
            revenue_growth=0.02,
            earnings_growth=0.11,
            book_value_growth=-0.05,
            earnings_per_share_growth=0.13,
            free_cash_flow_growth=0.01,
            operating_income_growth=0.07,
            ebitda_growth=0.06,
            payout_ratio=0.15,
            earnings_per_share=6.42,
            book_value_per_share=3.95,
            free_cash_flow_per_share=6.73,
        )
        assert fm.market_cap == 3_000_000_000_000.0
        assert fm.gross_margin == 0.45


class TestLineItem:
    def test_extra_fields_allowed(self):
        """LineItem uses model_config extra='allow' for dynamic financial fields."""
        li = LineItem(
            ticker="AAPL",
            report_period="2024-Q1",
            period="ttm",
            currency="USD",
            revenue=394_328_000_000.0,
            net_income=97_000_000_000.0,
        )
        assert li.revenue == 394_328_000_000.0
        assert li.net_income == 97_000_000_000.0

    def test_no_extra_fields(self):
        li = LineItem(ticker="MSFT", report_period="2024-Q2", period="annual", currency="USD")
        assert li.ticker == "MSFT"


class TestInsiderTrade:
    def test_minimal_insider_trade(self):
        """InsiderTrade requires ticker and filing_date; other fields are Optional with None defaults."""
        trade = InsiderTrade(
            ticker="AAPL",
            issuer=None,
            name=None,
            title=None,
            is_board_director=None,
            transaction_date=None,
            transaction_shares=None,
            transaction_price_per_share=None,
            transaction_value=None,
            shares_owned_before_transaction=None,
            shares_owned_after_transaction=None,
            security_title=None,
            filing_date="2024-03-15",
        )
        assert trade.issuer is None
        assert trade.transaction_shares is None

    def test_full_insider_trade(self):
        trade = InsiderTrade(
            ticker="TSLA",
            issuer="Tesla Inc",
            name="Elon Musk",
            title="CEO",
            is_board_director=False,
            transaction_date="2024-03-01",
            transaction_shares=10_000.0,
            transaction_price_per_share=175.50,
            transaction_value=1_755_000.0,
            shares_owned_before_transaction=100_000.0,
            shares_owned_after_transaction=110_000.0,
            security_title="Common Stock",
            filing_date="2024-03-05",
        )
        assert trade.transaction_value == 1_755_000.0


class TestCompanyNews:
    def test_minimal_news(self):
        news = CompanyNews(ticker="AAPL", title="Apple Q1 Earnings", source="Reuters", date="2024-01-25", url="https://example.com")
        assert news.sentiment is None
        assert news.author is None

    def test_news_with_sentiment(self):
        news = CompanyNews(ticker="AAPL", title="Beat", source="CNBC", date="2024-01-25", url="https://example.com", sentiment="positive")
        assert news.sentiment == "positive"


class TestCompanyFacts:
    def test_minimal_company_facts(self):
        cf = CompanyFacts(ticker="AAPL", name="Apple Inc.")
        assert cf.industry is None
        assert cf.is_active is None

    def test_full_company_facts(self):
        cf = CompanyFacts(
            ticker="AAPL",
            name="Apple Inc.",
            industry="Consumer Electronics",
            sector="Technology",
            exchange="NASDAQ",
            is_active=True,
            market_cap=3_000_000_000_000.0,
            number_of_employees=164_000,
        )
        assert cf.number_of_employees == 164_000


class TestPosition:
    def test_defaults(self):
        pos = Position(ticker="AAPL")
        assert pos.cash == 0.0
        assert pos.shares == 0

    def test_with_values(self):
        pos = Position(ticker="AAPL", cash=50_000.0, shares=100)
        assert pos.shares == 100


class TestPortfolio:
    def test_empty_portfolio(self):
        port = Portfolio(positions={}, total_cash=100_000.0)
        assert port.total_cash == 100_000.0
        assert port.positions == {}

    def test_portfolio_with_positions(self):
        port = Portfolio(
            positions={
                "AAPL": Position(ticker="AAPL", cash=0.0, shares=50),
                "MSFT": Position(ticker="MSFT", cash=0.0, shares=30),
            },
            total_cash=50_000.0,
        )
        assert len(port.positions) == 2
        assert port.positions["AAPL"].shares == 50


class TestAnalystSignal:
    def test_all_none(self):
        sig = AnalystSignal()
        assert sig.signal is None
        assert sig.confidence is None
        assert sig.reasoning is None
        assert sig.max_position_size is None

    def test_with_dict_reasoning(self):
        sig = AnalystSignal(signal="bullish", confidence=0.85, reasoning={"score": 8, "notes": "Strong fundamentals"})
        assert sig.reasoning["score"] == 8

    def test_with_string_reasoning(self):
        sig = AnalystSignal(signal="bearish", confidence=0.3, reasoning="Weak earnings outlook")
        assert isinstance(sig.reasoning, str)


class TestTickerAnalysis:
    def test_ticker_analysis(self):
        ta = TickerAnalysis(
            ticker="AAPL",
            analyst_signals={
                "warren_buffett": AnalystSignal(signal="bullish", confidence=0.9),
                "michael_burry": AnalystSignal(signal="bearish", confidence=0.6),
            },
        )
        assert len(ta.analyst_signals) == 2
        assert ta.analyst_signals["warren_buffett"].signal == "bullish"
