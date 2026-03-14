"""Data validation and cross-validation for multiple data sources."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates and cross-validates data from multiple sources."""

    def __init__(
        self,
        source_weights: Optional[Dict[str, float]] = None,
        price_threshold: float = 0.02,
        min_sources_for_validation: int = 1,
    ):
        """
        Initialize data validator.

        Args:
            source_weights: Weights for each data source (higher = more trusted)
            price_threshold: Maximum allowed price deviation (as fraction, e.g., 0.02 = 2%)
            min_sources_for_validation: Minimum number of sources required for validation
        """
        self.source_weights = source_weights or {
            "AKShare": 1.0,
            "YFinance": 0.8,
            "FinancialDatasets": 1.0,
        }
        self.price_threshold = price_threshold
        self.min_sources_for_validation = min_sources_for_validation
        self.logger = logging.getLogger(__name__)

    def cross_validate_prices(
        self, data_sources: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Cross-validate price data from multiple sources.

        Args:
            data_sources: Dictionary mapping source name to list of price dictionaries

        Returns:
            List of validated price dictionaries with weighted averages and confidence scores
        """
        if not data_sources:
            self.logger.warning("No data sources provided for validation")
            return []

        # Filter out empty sources
        valid_sources = {k: v for k, v in data_sources.items() if v}

        if not valid_sources:
            self.logger.warning("All data sources are empty")
            return []

        # If only one source, return it with confidence based on source quality
        if len(valid_sources) == 1:
            source_name = list(valid_sources.keys())[0]
            prices = list(valid_sources.values())[0]
            weight = self.source_weights.get(source_name, 0.5)
            confidence = min(weight, 0.8)  # Cap at 80% for single source

            for price in prices:
                price["confidence"] = confidence
                price["data_source"] = source_name
                price["num_sources"] = 1

            self.logger.info(
                f"Single source validation: {source_name}, {len(prices)} records, confidence={confidence:.2f}"
            )
            return prices

        # Multiple sources: cross-validate by timestamp
        return self._merge_and_validate_prices(valid_sources)

    def _merge_and_validate_prices(
        self, data_sources: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Merge and validate prices from multiple sources."""
        # Group prices by date
        prices_by_date: Dict[str, Dict[str, Dict]] = {}

        for source_name, prices in data_sources.items():
            for price in prices:
                # Normalize date to YYYY-MM-DD
                date_key = self._normalize_date(price.get("time", ""))
                if not date_key:
                    continue

                if date_key not in prices_by_date:
                    prices_by_date[date_key] = {}

                prices_by_date[date_key][source_name] = price

        # Validate and merge prices for each date
        validated_prices = []

        for date_key in sorted(prices_by_date.keys()):
            source_prices = prices_by_date[date_key]

            if len(source_prices) < self.min_sources_for_validation:
                # Not enough sources, skip or use single source
                if len(source_prices) == 1:
                    source_name = list(source_prices.keys())[0]
                    price = list(source_prices.values())[0]
                    price["confidence"] = 0.6  # Lower confidence for unvalidated data
                    price["data_source"] = source_name
                    price["num_sources"] = 1
                    validated_prices.append(price)
                continue

            # Calculate weighted average and validate
            validated_price = self._validate_price_group(source_prices, date_key)
            if validated_price:
                validated_prices.append(validated_price)

        self.logger.info(
            f"Cross-validated {len(validated_prices)} price records from {len(data_sources)} sources"
        )
        return validated_prices

    def _validate_price_group(
        self, source_prices: Dict[str, Dict], date_key: str
    ) -> Optional[Dict]:
        """Validate and merge prices from multiple sources for a single date."""
        # Extract close prices for comparison
        close_prices = []
        weights = []

        for source_name, price in source_prices.items():
            close = price.get("close", 0)
            if close > 0:
                close_prices.append(close)
                weights.append(self.source_weights.get(source_name, 0.5))

        if not close_prices:
            return None

        # Calculate statistics
        avg_close = sum(p * w for p, w in zip(close_prices, weights)) / sum(weights)
        max_deviation = max(abs(p - avg_close) / avg_close for p in close_prices)

        # Check if deviation exceeds threshold
        if max_deviation > self.price_threshold:
            self.logger.warning(
                f"Price deviation {max_deviation:.2%} exceeds threshold "
                f"{self.price_threshold:.2%} for {date_key}"
            )

        # Calculate confidence score
        confidence = self._calculate_confidence(
            num_sources=len(close_prices),
            max_deviation=max_deviation,
        )

        # Calculate weighted average for all fields
        validated_price = {
            "open": self._weighted_average(
                [p.get("open", 0) for p in source_prices.values()],
                [self.source_weights.get(s, 0.5) for s in source_prices.keys()],
            ),
            "close": avg_close,
            "high": self._weighted_average(
                [p.get("high", 0) for p in source_prices.values()],
                [self.source_weights.get(s, 0.5) for s in source_prices.keys()],
            ),
            "low": self._weighted_average(
                [p.get("low", 0) for p in source_prices.values()],
                [self.source_weights.get(s, 0.5) for s in source_prices.keys()],
            ),
            "volume": int(
                self._weighted_average(
                    [p.get("volume", 0) for p in source_prices.values()],
                    [self.source_weights.get(s, 0.5) for s in source_prices.keys()],
                )
            ),
            "time": list(source_prices.values())[0]["time"],  # Use first source's timestamp
            "confidence": confidence,
            "data_sources": ",".join(source_prices.keys()),
            "num_sources": len(source_prices),
            "max_deviation": max_deviation,
        }

        return validated_price

    def _weighted_average(self, values: List[float], weights: List[float]) -> float:
        """Calculate weighted average."""
        if not values or not weights:
            return 0.0

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        return sum(v * w for v, w in zip(values, weights)) / total_weight

    def _calculate_confidence(
        self, num_sources: int, max_deviation: float
    ) -> float:
        """
        Calculate confidence score based on number of sources and deviation.

        Args:
            num_sources: Number of data sources
            max_deviation: Maximum deviation from average (as fraction)

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence from number of sources (0.5 to 1.0)
        source_confidence = min(0.5 + (num_sources - 1) * 0.2, 1.0)

        # Deviation penalty (0 to 1, where 1 = no penalty)
        if max_deviation <= self.price_threshold:
            deviation_factor = 1.0
        else:
            # Linear penalty for deviations above threshold
            deviation_factor = max(0.0, 1.0 - (max_deviation - self.price_threshold) * 5)

        # Combined confidence
        confidence = source_confidence * deviation_factor

        return max(0.0, min(1.0, confidence))

    def validate_financial_metrics(
        self, data_sources: Dict[str, Optional[Dict]]
    ) -> Optional[Dict]:
        """
        Validate and merge financial metrics from multiple sources.

        Args:
            data_sources: Dictionary mapping source name to financial metrics dict

        Returns:
            Merged financial metrics with confidence scores
        """
        # Filter out None/empty sources
        valid_sources = {k: v for k, v in data_sources.items() if v}

        if not valid_sources:
            self.logger.warning("No valid financial metrics sources")
            return None

        # If only one source, return it with confidence
        if len(valid_sources) == 1:
            source_name = list(valid_sources.keys())[0]
            metrics = list(valid_sources.values())[0].copy()
            weight = self.source_weights.get(source_name, 0.5)
            metrics["confidence"] = min(weight, 0.7)  # Cap at 70% for single source
            metrics["data_source"] = source_name
            metrics["num_sources"] = 1
            return metrics

        # Multiple sources: merge with weighted average
        return self._merge_financial_metrics(valid_sources)

    def _merge_financial_metrics(
        self, data_sources: Dict[str, Dict]
    ) -> Dict:
        """Merge financial metrics from multiple sources."""
        # Start with the first source as base
        merged = list(data_sources.values())[0].copy()

        # Metric fields that should be averaged
        numeric_fields = [
            "market_cap", "enterprise_value", "price_to_earnings_ratio",
            "price_to_book_ratio", "price_to_sales_ratio",
            "enterprise_value_to_ebitda_ratio", "enterprise_value_to_revenue_ratio",
            "free_cash_flow_yield", "peg_ratio", "gross_margin",
            "operating_margin", "net_margin", "return_on_equity",
            "return_on_assets", "return_on_invested_capital", "asset_turnover",
            "inventory_turnover", "receivables_turnover", "days_sales_outstanding",
            "operating_cycle", "working_capital_turnover", "current_ratio",
            "quick_ratio", "cash_ratio", "operating_cash_flow_ratio",
            "debt_to_equity", "debt_to_assets", "interest_coverage",
            "revenue_growth", "earnings_growth", "book_value_growth",
            "earnings_per_share_growth", "free_cash_flow_growth",
            "operating_income_growth", "ebitda_growth", "payout_ratio",
            "earnings_per_share", "book_value_per_share", "free_cash_flow_per_share",
        ]

        # Calculate weighted average for each numeric field
        for field in numeric_fields:
            values = []
            weights = []

            for source_name, metrics in data_sources.items():
                value = metrics.get(field)
                if value is not None:
                    values.append(value)
                    weights.append(self.source_weights.get(source_name, 0.5))

            if values:
                merged[field] = self._weighted_average(values, weights)
            else:
                merged[field] = None

        # Add metadata
        merged["confidence"] = self._calculate_metrics_confidence(len(data_sources))
        merged["data_sources"] = ",".join(data_sources.keys())
        merged["num_sources"] = len(data_sources)

        self.logger.info(
            f"Merged financial metrics from {len(data_sources)} sources, "
            f"confidence={merged['confidence']:.2f}"
        )

        return merged

    def _calculate_metrics_confidence(self, num_sources: int) -> float:
        """Calculate confidence for merged financial metrics."""
        # Higher confidence with more sources
        return min(0.6 + (num_sources - 1) * 0.15, 0.95)

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format."""
        if not date_str:
            return ""

        try:
            # Try common date formats
            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If all fail, try parsing ISO format
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")

        except Exception as e:
            self.logger.warning(f"Failed to parse date {date_str}: {e}")
            return ""

    def validate_news(self, data_sources: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Validate and merge news from multiple sources.

        Args:
            data_sources: Dictionary mapping source name to list of news items

        Returns:
            Deduplicated and validated list of news items
        """
        all_news = []

        for source_name, news_list in data_sources.items():
            for news_item in news_list:
                news_item = news_item.copy()
                news_item["data_source"] = source_name
                all_news.append(news_item)

        # Deduplicate by title similarity (simple approach)
        unique_news = []
        seen_titles = set()

        for news in sorted(all_news, key=lambda x: x.get("date", ""), reverse=True):
            title = news.get("title", "").lower().strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        self.logger.info(
            f"Validated {len(unique_news)} unique news items from "
            f"{len(data_sources)} sources ({len(all_news)} total)"
        )

        return unique_news
