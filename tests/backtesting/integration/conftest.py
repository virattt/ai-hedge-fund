import json
from pathlib import Path

import pandas as pd
import pytest


PRICES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "prices"
FM_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "financial_metrics"
NEWS_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "news"
INSIDER_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "insider_trades"


def _find_price_fixture_file(ticker: str, start: str, end: str) -> Path | None:
    # Find a fixture whose filename date range overlaps [start, end]
    # Filenames: {TICKER}_{START}_{END}.json
    candidates = sorted(PRICES_ROOT.glob(f"{ticker}_*.json"))
    for p in candidates:
        try:
            parts = p.stem.split("_")
            _, start_str, end_str = parts[0], parts[1], parts[2]
            # overlap if requested window intersects file window
            if not (end < start_str or start > end_str):
                return p
        except Exception:
            continue
    return None


def _load_price_df_from_fixture(ticker: str, start: str, end: str) -> pd.DataFrame:
    fixture_path = _find_price_fixture_file(ticker, start, end)
    assert fixture_path is not None, f"Missing price fixture for {ticker} covering {start}..{end}"
    with fixture_path.open("r") as f:
        data = json.load(f)
    # Build DataFrame similar to prices_to_df output
    df = pd.DataFrame([p for p in data["prices"]])
    df["Date"] = pd.to_datetime(df["time"]).dt.tz_convert('UTC')  # align with prices_to_df index name
    df.set_index("Date", inplace=True)
    for col in ("open", "close", "high", "low", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    # Filter by requested window
    start_ts = pd.to_datetime(start).tz_localize('UTC')
    end_ts = pd.to_datetime(end).tz_localize('UTC')
    df = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]
    return df[["open", "close", "high", "low", "volume"]]


def _find_fm_fixture_file(ticker: str, end: str) -> Path | None:
    candidates = sorted(FM_ROOT.glob(f"{ticker}_*.json"))
    for p in candidates:
        try:
            parts = p.stem.split("_")
            # {TICKER}_{START}_{END}
            _, start_str, end_str = parts[0], parts[1], parts[2]
            if start_str <= end <= end_str:
                return p
        except Exception:
            continue
    return None


def _load_financial_metrics_from_fixture(ticker: str, end: str, limit: int) -> list[dict]:
    fixture_path = _find_fm_fixture_file(ticker, end)
    assert fixture_path is not None, f"Missing financial metrics fixture for {ticker} covering ..{end}"
    with fixture_path.open("r") as f:
        data = json.load(f)
    # data should match FinancialMetricsResponse
    items = data.get("financial_metrics", [])
    # Mimic API limit behavior
    return items[:limit]


def _load_news_from_fixture(ticker: str, start: str | None, end: str, limit: int) -> list[dict]:
    # Expect exact match filename {TICKER}_{START}_{END}.json
    start_key = start or "none"
    fixture_path = NEWS_ROOT / f"{ticker}_{start or 'none'}_{end}.json"
    if not fixture_path.exists():
        # Fallback: any file that covers end
        candidates = sorted(NEWS_ROOT.glob(f"{ticker}_*.json"))
        for p in candidates:
            parts = p.stem.split("_")
            if len(parts) >= 3 and parts[1] <= end <= parts[2]:
                fixture_path = p
                break
    with fixture_path.open("r") as f:
        data = json.load(f)
    items = data.get("news", [])
    return items[:limit]


def _load_insider_from_fixture(ticker: str, start: str | None, end: str, limit: int) -> list[dict]:
    fixture_path = INSIDER_ROOT / f"{ticker}_{start or 'none'}_{end}.json"
    if not fixture_path.exists():
        candidates = sorted(INSIDER_ROOT.glob(f"{ticker}_*.json"))
        for p in candidates:
            parts = p.stem.split("_")
            if len(parts) >= 3 and parts[1] <= end <= parts[2]:
                fixture_path = p
                break
    with fixture_path.open("r") as f:
        data = json.load(f)
    items = data.get("insider_trades", [])
    return items[:limit]


@pytest.fixture(autouse=True)
def patch_engine_prices(monkeypatch):
    # No-op non-price endpoints
    monkeypatch.setattr("src.backtesting.engine.get_prices", lambda *a, **k: None)
    def _fake_get_financial_metrics(ticker: str, end_date: str, period: str = "ttm", limit: int = 10, api_key: str | None = None):
        return _load_financial_metrics_from_fixture(ticker, end_date, limit)
    monkeypatch.setattr("src.backtesting.engine.get_financial_metrics", _fake_get_financial_metrics)
    def _fake_get_insider_trades(ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000, api_key: str | None = None):
        return _load_insider_from_fixture(ticker, start_date, end_date, limit)
    def _fake_get_company_news(ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000, api_key: str | None = None):
        return _load_news_from_fixture(ticker, start_date, end_date, limit)
    monkeypatch.setattr("src.backtesting.engine.get_insider_trades", _fake_get_insider_trades)
    monkeypatch.setattr("src.backtesting.engine.get_company_news", _fake_get_company_news)

    # Patch price data loader to use fixtures
    def _fake_get_price_data(ticker: str, start_date: str, end_date: str, api_key: str | None = None):
        return _load_price_df_from_fixture(ticker, start_date, end_date)

    monkeypatch.setattr("src.backtesting.engine.get_price_data", _fake_get_price_data)
    yield


