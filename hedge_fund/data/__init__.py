"""v2 data pipeline — data provider protocol, clients (yfinance default, FD), and response models."""

from hedge_fund.data.cached import CachedDataClient
from hedge_fund.data.client import FDClient, FDClientError
from hedge_fund.data.source import data_source, data_source_key, open_data_client
from hedge_fund.data.yfinance_client import YFClientError, YFinanceClient
from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsData,
    EarningsRecord,
    Filing,
    FinancialMetrics,
    InsiderTrade,
    Price,
)
from hedge_fund.data.protocol import DataClient

__all__ = [
    "CachedDataClient",
    "CompanyFacts",
    "CompanyNews",
    "DataClient",
    "Earnings",
    "EarningsData",
    "EarningsRecord",
    "FDClient",
    "FDClientError",
    "Filing",
    "FinancialMetrics",
    "InsiderTrade",
    "Price",
    "YFClientError",
    "YFinanceClient",
    "data_source",
    "data_source_key",
    "open_data_client",
]
