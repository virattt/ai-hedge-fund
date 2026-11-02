"""Exposures — a single-index factor model of the book.

Every name is a beta to the mandate's benchmark plus a residual (Sharpe
1963): the model a small shop actually runs, and one whose every number a
record can carry. From it the risk stage reads three things about a book:

- its beta, `sum(w_i x beta_i)`;
- its net weight per sector, from the company facts the data provider has;
- its modelled volatility, `sqrt(beta_p^2 sigma_m^2 + sum(w_i^2 sigma_eps,i^2))`,
  annualized, with the residuals taken as uncorrelated.

Betas come from an ordinary least squares fit of about a quarter of daily
log returns (the pipeline's 100-day window) on the benchmark's, then shrunk
toward one the way Bloomberg prints them (Blume 1975: 0.67 x fitted + 0.33).
A name with fewer than sixty paired returns gets the prior outright: beta
one and no residual, so it adds market risk and nothing else. A missing
history must not silently freeze a name.

One window serves beta and volatility. A desk often measures volatility on
a shorter window so the cap reacts to a regime change; this model keeps one
window so every number on the record comes from the same bars.
"""

from __future__ import annotations

from math import log, sqrt

import numpy as np
from pydantic import BaseModel

from hedge_fund.data.protocol import DataClient

# Trading days in a year: the annualization of a daily sigma.
_TRADING_DAYS = 252
# Paired daily returns a regression needs before its beta replaces the prior.
_MIN_FACTOR_BARS = 60
# Blume (1975): fitted betas drift toward one; shrink them before use.
_BLUME_WEIGHT = 0.67


class NameExposure(BaseModel):
    """One name in the model: what the benchmark explains and what it does not."""

    beta: float                       # Blume-adjusted: 0.67 x fitted + 0.33
    residual_volatility: float        # annualized sigma of the fit's residuals
    sector: str | None                # the data provider's sector; None when it has none
    n_bars: int                       # paired daily returns the fit used


class Exposures(BaseModel):
    """The model at one date: the benchmark's volatility and every name's
    exposure. The decision carries the one its clamps were measured with."""

    as_of: str
    benchmark_volatility: float       # annualized sigma of the benchmark's daily log returns
    names: dict[str, NameExposure]

    def book_beta(self, weights: dict[str, float]) -> float:
        return sum(weight * self.names[ticker].beta for ticker, weight in weights.items())

    def sector_nets(self, weights: dict[str, float]) -> dict[str, float]:
        """Signed weight per sector; a name without a sector counts nowhere."""
        nets: dict[str, float] = {}
        for ticker, weight in weights.items():
            sector = self.names[ticker].sector
            if sector is not None:
                nets[sector] = nets.get(sector, 0.0) + weight
        return nets

    def book_volatility(self, weights: dict[str, float]) -> float:
        """Annualized: market risk through the book's beta, plus each name's
        residual risk, taken as independent of every other name's."""
        market = self.book_beta(weights) * self.benchmark_volatility
        residual = sum((weight * self.names[ticker].residual_volatility) ** 2 for ticker, weight in weights.items())
        return sqrt(market ** 2 + residual)


def exposures(
    tickers: list[str], benchmark: str, as_of: str, data_client: DataClient, start: str,
) -> Exposures:
    """Fit the model from the daily bars in [*start*, *as_of*]: the caller
    owns the window, so its fetch is the same one the marks and the
    liquidity made. Raises when the benchmark itself has too few bars: a
    factor mandate needs sixty daily returns of its benchmark."""
    market = _log_returns(benchmark, start, as_of, data_client)
    if len(market) < _MIN_FACTOR_BARS:
        raise ValueError(f"{benchmark}: {len(market)} daily returns in [{start}, {as_of}]; "
                         f"a factor limit needs at least {_MIN_FACTOR_BARS}")
    market_series = np.array(list(market.values()))
    names: dict[str, NameExposure] = {}
    for ticker in tickers:
        own = _log_returns(ticker, start, as_of, data_client)
        days = sorted(set(own) & set(market))
        facts = data_client.get_company_facts(ticker)
        sector = facts.sector if facts is not None else None
        if len(days) < _MIN_FACTOR_BARS:
            names[ticker] = NameExposure(beta=1.0, residual_volatility=0.0, sector=sector, n_bars=len(days))
            continue
        x = np.array([market[day] for day in days])
        y = np.array([own[day] for day in days])
        fitted = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
        residuals = y - (y.mean() + fitted * (x - x.mean()))
        names[ticker] = NameExposure(
            beta=_BLUME_WEIGHT * fitted + (1 - _BLUME_WEIGHT),
            residual_volatility=float(residuals.std(ddof=1)) * sqrt(_TRADING_DAYS),
            sector=sector, n_bars=len(days),
        )
    return Exposures(
        as_of=as_of,
        benchmark_volatility=float(market_series.std(ddof=1)) * sqrt(_TRADING_DAYS),
        names=names,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _log_returns(ticker: str, start: str, end: str, data_client: DataClient) -> dict[str, float]:
    """Daily log returns keyed by the day they land on, from the bars in the window."""
    bars = sorted(
        (p for p in data_client.get_prices(ticker, start, end) if start <= p.time[:10] <= end),
        key=lambda p: p.time,
    )
    return {b.time[:10]: log(b.close / a.close) for a, b in zip(bars, bars[1:])}
