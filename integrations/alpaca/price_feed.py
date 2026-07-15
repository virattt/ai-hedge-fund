"""Batch latest-price fetch for the watch loop (minimal API usage)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from integrations.alpaca.market_hours import now_et
from integrations.alpaca.rate_limit import RateLimiter
from integrations.data.config import load_data_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceSnapshot:
    ticker: str
    price: float
    timestamp: str


class PriceFeed:
    """Fetch current prices for many tickers in as few API calls as possible."""

    def __init__(self, *, alpaca_limiter: RateLimiter | None = None) -> None:
        self._limiter = alpaca_limiter or RateLimiter(100)
        self._config = None
        self._client = None

    def fetch(self, tickers: list[str], *, include_spy: bool = True) -> dict[str, PriceSnapshot]:
        symbols = [t.upper() for t in tickers]
        if include_spy and "SPY" not in symbols:
            symbols.append("SPY")

        batch = self._fetch_alpaca_snapshots(symbols)
        if batch:
            return batch

        return self._fetch_daily_fallback(symbols)

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        config = load_data_config()
        if not config.alpaca_api_key or not config.alpaca_secret_key:
            return None
        try:
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError:
            return None
        self._config = config
        self._client = StockHistoricalDataClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
        )
        return self._client

    def _fetch_alpaca_snapshots(self, symbols: list[str]) -> dict[str, PriceSnapshot]:
        client = self._ensure_client()
        if client is None:
            return {}

        try:
            from alpaca.data.requests import StockSnapshotRequest
        except ImportError:
            return {}

        self._limiter.wait(cost=1)
        try:
            request = StockSnapshotRequest(symbol_or_symbols=symbols)
            raw = client.get_stock_snapshot(request)
        except Exception as exc:
            logger.warning("Alpaca snapshot batch failed: %s", exc)
            return {}

        if not isinstance(raw, dict):
            raw = {symbols[0]: raw} if len(symbols) == 1 else {}

        out: dict[str, PriceSnapshot] = {}
        ts = now_et().isoformat()
        for symbol in symbols:
            snap = raw.get(symbol)
            if snap is None:
                continue
            price = self._extract_price(snap)
            if price is not None and price > 0:
                out[symbol] = PriceSnapshot(ticker=symbol, price=price, timestamp=ts)
        return out

    @staticmethod
    def _extract_price(snap) -> float | None:
        trade = getattr(snap, "latest_trade", None)
        if trade is not None and getattr(trade, "price", None):
            return float(trade.price)
        quote = getattr(snap, "latest_quote", None)
        if quote is not None:
            ask = getattr(quote, "ask_price", None)
            bid = getattr(quote, "bid_price", None)
            if ask and bid:
                return float((ask + bid) / 2)
            if ask:
                return float(ask)
            if bid:
                return float(bid)
        bar = getattr(snap, "daily_bar", None) or getattr(snap, "minute_bar", None)
        if bar is not None and getattr(bar, "close", None):
            return float(bar.close)
        return None

    def _fetch_daily_fallback(self, symbols: list[str]) -> dict[str, PriceSnapshot]:
        """One get_prices call per symbol — used when Alpaca SDK unavailable."""
        from src.tools.api import get_prices

        end = now_et().date().isoformat()
        start = (now_et().date() - timedelta(days=5)).isoformat()
        out: dict[str, PriceSnapshot] = {}
        ts = now_et().isoformat()

        for symbol in symbols:
            self._limiter.wait(cost=1)
            try:
                rows = get_prices(symbol, start, end)
                if rows:
                    out[symbol] = PriceSnapshot(
                        ticker=symbol,
                        price=float(rows[-1].close),
                        timestamp=ts,
                    )
            except Exception as exc:
                logger.debug("Fallback price for %s failed: %s", symbol, exc)
        return out
