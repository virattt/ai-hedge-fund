"""Screener models and the vocabulary check — pure, no network."""

import pytest
from pydantic import ValidationError

from hedge_fund.data.screener import OrderBy, ScreenerFields, ScreenFilter, ScreenRow

# The shape GET /financials/search/screener/filters served on 2026-11-08, cut down.
FILTERS_BODY = {
    "metrics": {
        "income_statement": ["revenue", "net_income"],
        "balance_sheet": ["total_debt"],
        "cash_flow_statement": ["free_cash_flow"],
        "financial_metrics": ["market_cap", "pe_ratio", "revenue_growth", "stock_price"],
        "company": {"sector": ["Financials"], "industry": ["Banks"]},
    },
    "aliases": {"pe_ratio": "price_to_earnings_ratio"},
    "company_filters": {
        "fields": ["industry", "sector"],
        "operators": ["eq", "in"],
        "values": {"sector": ["Financials", "Health Care"], "industry": ["Banks", "Software"]},
    },
    "operators": ["gt", "lt", "gte", "lte", "eq", "in"],
}


@pytest.fixture
def fields():
    return ScreenerFields.from_api(FILTERS_BODY)


def test_a_filter_dumps_to_the_api_shape():
    assert ScreenFilter(field="market_cap", operator="gt", value=1e9).model_dump() == {
        "field": "market_cap", "operator": "gt", "value": 1e9,
    }
    assert ScreenFilter(field="sector", operator="in", value=["Financials", "Energy"]).value == ["Financials", "Energy"]
    with pytest.raises(ValidationError):
        ScreenFilter(field="market_cap", operator="between", value=1)


def test_a_row_splits_the_filing_stamp_from_the_numbers():
    row = ScreenRow.from_api({
        "ticker": "A", "filing_date": "2026-06-01", "report_period": "2026-04-30", "currency": "USD",
        "market_cap": 38399447106.24, "pe_ratio": 27.15, "price_to_earnings_ratio": 27.15,
        "sector": "Health Care", "industry": "Life Sciences Tools & Services",
    })
    assert (row.ticker, row.filing_date, row.report_period, row.sector) == ("A", "2026-06-01", "2026-04-30", "Health Care")
    assert row.values == {"market_cap": 38399447106.24, "pe_ratio": 27.15, "price_to_earnings_ratio": 27.15}
    bare = ScreenRow.from_api({"ticker": "B", "filing_date": "2026-06-01", "report_period": "2026-04-30", "currency": "USD", "market_cap": 2e9})
    assert bare.sector is None and bare.values == {"market_cap": 2e9}


def test_the_vocabulary_reads_every_metric_group_and_both_alias_names(fields):
    assert {"revenue", "total_debt", "free_cash_flow", "market_cap", "pe_ratio", "price_to_earnings_ratio"} <= fields.numeric
    assert "sector" not in fields.numeric
    assert fields.sectors == {"Financials", "Health Care"}
    assert fields.industries == {"Banks", "Software"}
    assert "stock_price" in fields.unavailable_as_of


def test_a_sound_request_has_no_problems(fields):
    assert fields.problems([
        ScreenFilter(field="market_cap", operator="gt", value=1e9),
        ScreenFilter(field="sector", operator="in", value=["financials", "Health Care"]),  # the API ignores case
        ScreenFilter(field="ticker", operator="in", value=["INTC", "ARM"]),
        ScreenFilter(field="pe_ratio", operator="in", value=[10, 20]),
    ], OrderBy(field="market_cap")) == []


@pytest.mark.parametrize("item, expected", [
    (ScreenFilter(field="momentum_6m", operator="gt", value=0), "'momentum_6m' is not a screener field"),
    (ScreenFilter(field="stock_price", operator="gt", value=5), "'stock_price' is not available point-in-time; the filing records do not carry it"),
    (ScreenFilter(field="sector", operator="gt", value="Financials"), "'sector' takes eq or in, not gt"),
    (ScreenFilter(field="sector", operator="eq", value="Tobacco"), "'Tobacco' is not a sector the screener knows"),
    (ScreenFilter(field="industry", operator="in", value=["Banks", "Airlines"]), "'Airlines' is not a industry the screener knows"),
    (ScreenFilter(field="market_cap", operator="gt", value="big"), "'market_cap' needs a number, not 'big'"),
    (ScreenFilter(field="pe_ratio", operator="in", value=15), "'pe_ratio' with in needs a list of numbers"),
    (ScreenFilter(field="ticker", operator="gt", value="A"), "'ticker' takes eq or in, not gt"),
    (ScreenFilter(field="ticker", operator="in", value=[1, 2]), "'ticker' needs a ticker or a list of tickers"),
])
def test_each_defect_is_named_in_plain_words(fields, item, expected):
    assert fields.problems([item]) == [expected]


def test_order_by_must_be_a_numeric_field_the_filings_carry(fields):
    assert fields.problems([], OrderBy(field="sector")) == ["order_by 'sector' is not a numeric screener field"]
    assert fields.problems([], OrderBy(field="stock_price")) == ["order_by 'stock_price' is not available point-in-time"]
