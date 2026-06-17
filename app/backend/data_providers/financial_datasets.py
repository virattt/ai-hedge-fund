"""Financial Datasets API provider.

Primary provider for US-listed equities. Provides prices, fundamentals,
sentiment, and insider trading data.
"""

import logging
import os
from typing import Optional

from app.backend.data_providers.base import DataProvider
from app.backend.data_providers.models import (
    DataAvailability,
    FundamentalData,
    NewsItem,
    PriceBar,
    ProviderResult,
)

logger = logging.getLogger(__name__)


class FinancialDatasetsProvider(DataProvider):
    """Provider using the Financial Datasets API (US equities)."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "Financial Datasets"

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")

    def supports_ticker(self, ticker: str) -> bool:
        # Only supports US tickers (no .L, .TO, etc. suffixes)
        return "." not in ticker or ticker.endswith(".US")

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderResult:
        if not self.supports_ticker(ticker):
            return ProviderResult(
                availability=DataAvailability.UNSUPPORTED_TICKER,
                provider_name=self.name,
            )

        try:
            from src.tools.api import get_prices, prices_to_df
            from datetime import datetime

            prices = get_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                api_key=self.api_key,
            )

            if not prices:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                    error_message=f"No price data from Financial Datasets for {ticker}",
                )

            bars: list[PriceBar] = []
            for p in prices:
                try:
                    dt = datetime.fromisoformat(p.time.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue
                bars.append(PriceBar(
                    date=dt,
                    open=float(p.open),
                    high=float(p.high),
                    low=float(p.low),
                    close=float(p.close),
                    volume=int(p.volume),
                ))

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=bars,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Financial Datasets price fetch failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )

    def get_fundamentals(self, ticker: str) -> ProviderResult:
        if not self.supports_ticker(ticker):
            return ProviderResult(
                availability=DataAvailability.UNSUPPORTED_TICKER,
                provider_name=self.name,
            )

        try:
            from src.tools.api import get_financial_metrics
            from datetime import datetime

            metrics_list = get_financial_metrics(
                ticker=ticker,
                end_date=datetime.now().strftime("%Y-%m-%d"),
                period="ttm",
                limit=1,
                api_key=self.api_key,
            )

            if not metrics_list:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                )

            m = metrics_list[0]
            fundamentals = FundamentalData(
                ticker=ticker,
                pe_ratio=m.price_to_earnings_ratio,
                pb_ratio=m.price_to_book_ratio,
                ps_ratio=m.price_to_sales_ratio,
                revenue_growth=m.revenue_growth,
                earnings_growth=m.earnings_growth,
                profit_margin=m.net_margin,
                operating_margin=m.operating_margin,
                roe=m.return_on_equity,
                debt_to_equity=m.debt_to_equity,
                dividend_yield=m.dividend_yield,
                market_cap=m.market_cap,
                source=self.name,
            )

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=fundamentals,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Financial Datasets fundamentals failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )

    def get_news(self, ticker: str, limit: int = 20) -> ProviderResult:
        if not self.supports_ticker(ticker):
            return ProviderResult(
                availability=DataAvailability.UNSUPPORTED_TICKER,
                provider_name=self.name,
            )

        try:
            from src.tools.api import get_company_news
            from datetime import datetime

            news = get_company_news(
                ticker=ticker,
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=limit,
                api_key=self.api_key,
            )

            if not news:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                )

            articles: list[NewsItem] = []
            for item in news:
                pub_date = None
                if hasattr(item, "date") and item.date:
                    try:
                        pub_date = datetime.fromisoformat(str(item.date).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                articles.append(NewsItem(
                    title=item.title if hasattr(item, "title") else str(item),
                    source="Financial Datasets",
                    published=pub_date,
                    url=getattr(item, "url", None),
                    sentiment=getattr(item, "sentiment", None),
                ))

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=articles,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Financial Datasets news failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )
