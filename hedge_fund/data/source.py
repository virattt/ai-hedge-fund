"""Pick the data provider from the environment.

HEDGE_FUND_DATA_SOURCE selects it: ``yfinance`` (default, free, no key) or
``financialdatasets`` (paid, needs FINANCIAL_DATASETS_API_KEY). Every entry
point opens its client through ``open_data_client()`` so switching providers
is one environment variable, not an edit at each call site.
"""

from __future__ import annotations

import os

_ENV = "HEDGE_FUND_DATA_SOURCE"
_SOURCES = {
    "yfinance": None,
    "financialdatasets": "FINANCIAL_DATASETS_API_KEY",
}


def data_source() -> str:
    source = os.environ.get(_ENV, "yfinance").strip().lower() or "yfinance"
    if source not in _SOURCES:
        raise ValueError(f"{_ENV}={source!r}; expected one of {sorted(_SOURCES)}")
    return source


def data_source_key() -> str | None:
    """The env var the selected provider needs, or None for keyless ones."""
    return _SOURCES[data_source()]


def open_data_client():
    """A fresh (uncached) client for the selected provider; use as a context manager."""
    if data_source() == "financialdatasets":
        from hedge_fund.data.client import FDClient
        return FDClient()
    from hedge_fund.data.yfinance_client import YFinanceClient
    return YFinanceClient()
