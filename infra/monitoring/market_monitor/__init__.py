import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

import azure.functions as func
from azure.cosmos import CosmosClient, PartitionKey, exceptions as cosmos_exceptions
from azure.storage.queue import QueueClient

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.data.models import Price  # noqa: E402
from src.tools.api import get_prices  # noqa: E402


EASTERN = ZoneInfo("America/New_York")


@dataclass
class SignalSummary:
    ticker: str
    percent_change: float
    volume_ratio: float | None
    latest: Price
    previous: Price
    average_volume: float | None
    reasons: list[str]

    @property
    def triggered(self) -> bool:
        return bool(self.reasons)


class CosmosCooldownStore:
    """Persist ticker trigger timestamps in Cosmos DB."""

    def __init__(self, endpoint: str, key: str, database: str, container: str) -> None:
        self._client = CosmosClient(url=endpoint, credential=key)
        self._database = self._client.create_database_if_not_exists(id=database)
        self._container = self._database.create_container_if_not_exists(
            id=container,
            partition_key=PartitionKey(path="/ticker"),
            offer_throughput=400,
        )

    def get_last_trigger(self, ticker: str) -> dt.datetime | None:
        try:
            item = self._container.read_item(item=ticker, partition_key=ticker)
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None
        except cosmos_exceptions.CosmosHttpResponseError as exc:
            logging.error("Cosmos read failed for %s: %s", ticker, exc)
            return None

        timestamp = item.get("last_triggered_utc")
        if not timestamp:
            return None
        try:
            parsed = dt.datetime.fromisoformat(timestamp)
        except ValueError:
            logging.warning("Invalid timestamp stored for %s: %s", ticker, timestamp)
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)

    def upsert_trigger(self, ticker: str, triggered_at: dt.datetime, reasons: list[str]) -> None:
        payload = {
            "id": ticker,
            "ticker": ticker,
            "last_triggered_utc": triggered_at.isoformat(),
            "last_reasons": reasons,
        }
        try:
            self._container.upsert_item(payload)
        except cosmos_exceptions.CosmosHttpResponseError as exc:
            logging.error("Failed to persist trigger for %s: %s", ticker, exc)


def _parse_watchlist(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [token.strip().upper() for token in raw.split(",") if token.strip()]


def _parse_price_time(value: str) -> dt.datetime:
    sanitized = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(sanitized)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = dt.datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            logging.warning("Unable to parse price timestamp: %s", value)
            parsed = dt.datetime.utcnow()
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _isoformat(timestamp: dt.datetime) -> str:
    return timestamp.replace(microsecond=0).isoformat()


def _load_queue_client() -> QueueClient:
    connection = (
        os.getenv("MARKET_MONITOR_QUEUE_CONNECTION_STRING")
        or os.getenv("AZURE_STORAGE_QUEUE_CONNECTION_STRING")
        or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        or os.getenv("AzureWebJobsStorage")
    )
    queue_name = (
        os.getenv("MARKET_MONITOR_QUEUE_NAME")
        or os.getenv("ALERT_QUEUE_NAME")
        or os.getenv("AZURE_STORAGE_QUEUE_NAME")
    )
    if not connection or not queue_name:
        raise RuntimeError("Queue storage configuration is missing")
    client = QueueClient.from_connection_string(connection, queue_name)
    try:
        client.create_queue()
    except Exception:  # Queue may already exist
        pass
    return client


def _ensure_cosmos_store() -> CosmosCooldownStore:
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    database = os.getenv("COSMOS_DATABASE")
    container = os.getenv("COSMOS_CONTAINER")
    if not all([endpoint, key, database, container]):
        raise RuntimeError("Cosmos DB configuration is missing required settings")
    return CosmosCooldownStore(endpoint, key, database, container)


def _is_market_hours(now_utc: dt.datetime) -> bool:
    eastern_now = now_utc.astimezone(EASTERN)
    if eastern_now.weekday() >= 5:  # Saturday/Sunday
        return False
    market_open = eastern_now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = eastern_now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= eastern_now <= market_close


def _history_window_days(volume_window: int) -> int:
    default_days = int(os.getenv("MARKET_MONITOR_LOOKBACK_DAYS", "30"))
    return max(default_days, volume_window + 2)


def _fetch_price_history(ticker: str, start_date: str, end_date: str) -> list[Price]:
    prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date)
    prices = sorted(prices, key=lambda price: _parse_price_time(price.time))
    return prices


def _evaluate_signals(
    ticker: str,
    prices: Sequence[Price],
    percent_threshold: float,
    volume_multiplier: float,
    volume_window: int,
) -> SignalSummary | None:
    if len(prices) < 2:
        logging.info("Not enough price history for %s to compute signals", ticker)
        return None

    sorted_prices = list(prices)
    latest = sorted_prices[-1]
    previous = sorted_prices[-2]
    if previous.close == 0:
        logging.warning("Previous close is zero for %s; skipping", ticker)
        return None

    percent_change = (latest.close - previous.close) / previous.close

    historical_window = sorted_prices[max(0, len(sorted_prices) - volume_window - 1) : -1]
    average_volume = None
    volume_ratio = None
    if historical_window:
        average_volume = mean(price.volume for price in historical_window)
        if average_volume > 0:
            volume_ratio = latest.volume / average_volume

    reasons: list[str] = []
    if percent_change >= percent_threshold:
        reasons.append("price_breakout")
    if volume_ratio is not None and volume_ratio >= volume_multiplier:
        reasons.append("volume_spike")

    summary = SignalSummary(
        ticker=ticker,
        percent_change=percent_change,
        volume_ratio=volume_ratio,
        latest=latest,
        previous=previous,
        average_volume=average_volume,
        reasons=reasons,
    )
    return summary


def _compose_queue_payload(
    ticker: str,
    triggered_at: dt.datetime,
    analysis_window_minutes: int,
    summary: SignalSummary,
    watchlist: Iterable[str],
) -> dict:
    window_end = triggered_at
    window_start = triggered_at - dt.timedelta(minutes=analysis_window_minutes)
    correlation_hints = {
        "related_watchlist": [symbol for symbol in watchlist if symbol != ticker],
        "basis": summary.reasons,
    }
    payload = {
        "tickers": [ticker],
        "analysis_window": {
            "start": _isoformat(window_start),
            "end": _isoformat(window_end),
        },
        "correlation_hints": correlation_hints,
        "signals": summary.reasons,
        "market_snapshot": {
            "percent_change": round(summary.percent_change, 6),
            "volume_ratio": round(summary.volume_ratio, 6) if summary.volume_ratio is not None else None,
            "latest_close": summary.latest.close,
            "previous_close": summary.previous.close,
            "latest_volume": summary.latest.volume,
            "average_volume": summary.average_volume,
        },
        "triggered_at": _isoformat(triggered_at),
    }
    return payload


def main(market_timer: func.TimerRequest) -> None:
    logging.info("Market monitor timer triggered at %s", market_timer.schedule_status.last if market_timer and market_timer.schedule_status else "unknown")

    now_utc = dt.datetime.now(dt.timezone.utc)
    if not _is_market_hours(now_utc):
        logging.info("Outside market hours - skipping execution")
        return

    watchlist_env = (
        os.getenv("MARKET_MONITOR_WATCHLIST")
        or os.getenv("WATCHLIST_TICKERS")
        or os.getenv("DEFAULT_WATCHLIST")
    )
    watchlist = _parse_watchlist(watchlist_env)
    if not watchlist:
        watchlist = ["AAPL", "MSFT", "NVDA"]
        logging.warning("No watchlist configured; falling back to default %s", watchlist)

    percent_threshold = float(os.getenv("MARKET_MONITOR_PERCENT_CHANGE_THRESHOLD", "0.02"))
    volume_multiplier = float(os.getenv("MARKET_MONITOR_VOLUME_SPIKE_MULTIPLIER", "1.5"))
    volume_window = int(os.getenv("MARKET_MONITOR_VOLUME_LOOKBACK", "10"))
    analysis_window_minutes = int(os.getenv("MARKET_MONITOR_ANALYSIS_WINDOW_MINUTES", "120"))
    cooldown_seconds = int(os.getenv("MARKET_MONITOR_COOLDOWN_SECONDS", str(30 * 60)))

    try:
        queue_client = _load_queue_client()
    except RuntimeError as exc:
        logging.error("Queue client initialization failed: %s", exc)
        return

    try:
        cooldown_store = _ensure_cosmos_store()
    except RuntimeError as exc:
        logging.error("Cosmos configuration error: %s", exc)
        return

    cooldown_window = dt.timedelta(seconds=cooldown_seconds)
    history_days = _history_window_days(volume_window)
    today_eastern = now_utc.astimezone(EASTERN).date()
    start_date = (today_eastern - dt.timedelta(days=history_days)).isoformat()
    end_date = today_eastern.isoformat()

    for ticker in watchlist:
        try:
            prices = _fetch_price_history(ticker, start_date, end_date)
        except Exception as exc:  # noqa: BLE001 - log and continue on data failure
            logging.exception("Failed to fetch prices for %s: %s", ticker, exc)
            continue

        summary = _evaluate_signals(ticker, prices, percent_threshold, volume_multiplier, volume_window)
        if not summary or not summary.triggered:
            continue

        last_trigger = cooldown_store.get_last_trigger(ticker)
        if last_trigger and now_utc - last_trigger < cooldown_window:
            logging.info("Ticker %s skipped due to cooldown (last trigger at %s)", ticker, last_trigger)
            continue

        payload = _compose_queue_payload(ticker, now_utc, analysis_window_minutes, summary, watchlist)
        try:
            queue_client.send_message(json.dumps(payload))
            logging.info("Enqueued analysis request for %s with reasons %s", ticker, summary.reasons)
            cooldown_store.upsert_trigger(ticker, now_utc, summary.reasons)
        except Exception as exc:  # noqa: BLE001 - surface queue issues
            logging.exception("Failed to enqueue analysis for %s: %s", ticker, exc)

