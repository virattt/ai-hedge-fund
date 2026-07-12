"""Yahoo Finance data provider via yfinance.

Supports US and international tickers including LSE (.L suffix).
Handles GBp to GBP conversion for London-listed instruments.
"""

import logging
from datetime import datetime, timedelta
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


class YahooFinanceProvider(DataProvider):
    """Provider using yfinance for price, fundamental, and news data."""

    @property
    def name(self) -> str:
        return "Yahoo Finance"

    def supports_ticker(self, ticker: str) -> bool:
        # yfinance supports most global tickers
        return True

    def _is_lse_pence(self, ticker: str) -> bool:
        """LSE tickers return prices in GBp (pence) — we convert to GBP."""
        return ticker.upper().endswith(".L")

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderResult:
        try:
            import yfinance as yf

            data = yf.download(
                ticker, start=start_date, end=end_date,
                progress=False, auto_adjust=True
            )
            if data.empty:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                    error_message=f"No price data returned for {ticker}",
                )

            # Flatten MultiIndex columns (yfinance returns ('Close', 'TICKER') for single tickers)
            if isinstance(data.columns, __import__('pandas').MultiIndex):
                data.columns = data.columns.get_level_values(0)

            pence_conversion = self._is_lse_pence(ticker)
            bars: list[PriceBar] = []

            for idx, row in data.iterrows():
                ts = idx
                open_val = self._extract_val(row, "Open")
                high_val = self._extract_val(row, "High")
                low_val = self._extract_val(row, "Low")
                close_val = self._extract_val(row, "Close")
                volume_val = int(self._extract_val(row, "Volume", 0))

                if pence_conversion:
                    open_val /= 100.0
                    high_val /= 100.0
                    low_val /= 100.0
                    close_val /= 100.0

                bars.append(PriceBar(
                    date=ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=volume_val,
                ))

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=bars,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Yahoo Finance price fetch failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )

    def get_fundamentals(self, ticker: str) -> ProviderResult:
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or info.get("regularMarketPrice") is None:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                    error_message=f"No fundamental data for {ticker}",
                )

            fundamentals = FundamentalData(
                ticker=ticker,
                pe_ratio=info.get("trailingPE") or info.get("forwardPE"),
                pb_ratio=info.get("priceToBook"),
                ps_ratio=info.get("priceToSalesTrailing12Months"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                roe=info.get("returnOnEquity"),
                debt_to_equity=self._safe_divide(
                    info.get("totalDebt"), info.get("totalStockholderEquity")
                ),
                dividend_yield=info.get("dividendYield"),
                market_cap=info.get("marketCap"),
                source=self.name,
            )

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=fundamentals,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Yahoo Finance fundamentals failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )

    def get_news(self, ticker: str, limit: int = 20) -> ProviderResult:
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            news_items = stock.news or []

            if not news_items:
                return ProviderResult(
                    availability=DataAvailability.NO_DATA,
                    provider_name=self.name,
                    error_message=f"No news available for {ticker}",
                )

            articles: list[NewsItem] = []
            for item in news_items[:limit]:
                content = item.get("content", {})
                title = content.get("title") or item.get("title", "")
                pub_date = None
                pub_str = content.get("pubDate") or item.get("providerPublishTime")
                if pub_str:
                    try:
                        if isinstance(pub_str, (int, float)):
                            pub_date = datetime.fromtimestamp(pub_str)
                        else:
                            pub_date = datetime.fromisoformat(str(pub_str).replace("Z", "+00:00"))
                    except (ValueError, TypeError, OSError):
                        pass

                provider = content.get("provider", {})
                source_name = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)

                articles.append(NewsItem(
                    title=title,
                    source=source_name or "Yahoo Finance",
                    published=pub_date,
                    url=content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else None,
                ))

            return ProviderResult(
                availability=DataAvailability.AVAILABLE,
                data=articles,
                provider_name=self.name,
            )

        except Exception as e:
            logger.warning("Yahoo Finance news failed for %s: %s", ticker, e)
            return ProviderResult(
                availability=DataAvailability.PROVIDER_ERROR,
                provider_name=self.name,
                error_message=str(e),
            )

    @staticmethod
    def _extract_val(row, col: str, default: float = 0.0) -> float:
        import pandas as pd
        val = row.get(col, default)
        if isinstance(val, pd.Series):
            return float(val.iloc[0]) if len(val) > 0 else default
        if isinstance(val, tuple):
            val = val[0]
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_divide(num, denom) -> Optional[float]:
        try:
            if num and denom and float(denom) != 0:
                return float(num) / float(denom)
        except (TypeError, ValueError):
            pass
        return None
