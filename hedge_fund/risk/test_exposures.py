"""The single-index model — betas, residuals, sectors, and the book's numbers."""

from datetime import date as _date
from datetime import timedelta
from math import exp, sqrt

import pytest

from hedge_fund.data.models import CompanyFacts, Price
from hedge_fund.risk.exposures import Exposures, exposures, NameExposure

START = "2023-06-04"
AS_OF = "2024-06-03"
# Eighty daily log returns that alternate +1% / -1%; the benchmark's series.
MARKET = [0.01 if i % 2 == 0 else -0.01 for i in range(80)]


class FactorDataClient:
    """Canned daily log returns per ticker, one bar a day ending on the date
    asked for, plus a sector per ticker (absent: no company facts)."""

    def __init__(self, returns, sectors):
        self._returns = returns
        self._sectors = sectors

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        returns = self._returns.get(ticker, [])
        end = _date.fromisoformat(end_date)
        closes = [100.0]
        for r in returns:
            closes.append(closes[-1] * exp(r))
        return [Price(open=c, close=c, high=c, low=c, volume=1000,
                      time=f"{(end - timedelta(days=len(closes) - 1 - i)).isoformat()}T00:00:00Z")
                for i, c in enumerate(closes)]

    def get_company_facts(self, ticker):
        if ticker not in self._sectors:
            return None
        return CompanyFacts(ticker=ticker, sector=self._sectors[ticker])


def test_a_name_at_twice_the_market_fits_beta_two_shrunk_toward_one():
    data = FactorDataClient({"SPY": MARKET, "AAPL": [2 * r for r in MARKET]}, {"AAPL": "Technology"})
    model = exposures(["AAPL"], "SPY", AS_OF, data, START)
    aapl = model.names["AAPL"]
    assert aapl.beta == pytest.approx(0.67 * 2.0 + 0.33)
    assert aapl.residual_volatility == pytest.approx(0.0, abs=1e-9)
    assert aapl.sector == "Technology" and aapl.n_bars == 80
    assert model.benchmark_volatility == pytest.approx(0.01 * sqrt(80 / 79) * sqrt(252))
    assert model.as_of == AS_OF


def test_too_short_a_history_gets_the_prior_and_no_facts_gets_no_sector():
    data = FactorDataClient({"SPY": MARKET, "NEW": [0.05] * 10}, {})
    new = exposures(["NEW"], "SPY", AS_OF, data, START).names["NEW"]
    assert (new.beta, new.residual_volatility, new.sector, new.n_bars) == (1.0, 0.0, None, 10)


def test_a_benchmark_with_too_few_bars_raises():
    data = FactorDataClient({"SPY": MARKET[:20], "AAPL": MARKET}, {})
    with pytest.raises(ValueError, match="SPY: 20 daily returns"):
        exposures(["AAPL"], "SPY", AS_OF, data, START)


def test_the_book_numbers_by_hand():
    model = Exposures(as_of=AS_OF, benchmark_volatility=0.2, names={
        "A": NameExposure(beta=1.5, residual_volatility=0.3, sector="Tech", n_bars=250),
        "B": NameExposure(beta=0.5, residual_volatility=0.1, sector=None, n_bars=250),
        "C": NameExposure(beta=1.0, residual_volatility=0.0, sector="Tech", n_bars=250),
    })
    weights = {"A": 0.4, "B": -0.2, "C": -0.1}
    assert model.book_beta(weights) == pytest.approx(0.6 - 0.1 - 0.1)
    assert model.sector_nets(weights) == {"Tech": pytest.approx(0.3)}   # B has no sector: counted nowhere
    market = 0.4 * 0.2
    residual = (0.4 * 0.3) ** 2 + (0.2 * 0.1) ** 2
    assert model.book_volatility(weights) == pytest.approx(sqrt(market ** 2 + residual))
