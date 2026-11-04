"""CachedDataClient tests — counting fake, no network."""

from hedge_fund.data.cached import CachedDataClient
from hedge_fund.data.models import CompanyFacts, Price, PriceSnapshot


class CountingClient:
    """Counts calls; returns canned data."""

    def __init__(self, facts=None):
        self.calls = 0
        self._facts = facts

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        self.calls += 1
        return [Price(open=1.0, close=2.0, high=2.0, low=1.0, volume=100,
                      time=f"{start_date}T00:00:00Z")]

    def get_snapshot(self, ticker):
        self.calls += 1
        return PriceSnapshot(ticker=ticker, price=100.0 + self.calls, time="2026-10-05T14:28:39Z")

    def get_company_facts(self, ticker):
        self.calls += 1
        return self._facts

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        self.calls += 1
        return []

    def get_market_cap(self, ticker, end_date):
        self.calls += 1
        return 3.0e12

    def get_earnings_history(self, ticker, limit):
        from hedge_fund.data.models import EarningsRecord
        self.calls += 1
        return [EarningsRecord(ticker=ticker, report_period="2024-01-01", source_type="8-K")]


def test_cache_hit_skips_wrapped_client(tmp_path):
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    first = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")
    second = fd.get_prices("AAPL", "2024-01-01", "2024-12-31")

    assert inner.calls == 1
    assert isinstance(second[0], Price)  # re-hydrated to the pydantic model
    assert second[0].close == first[0].close


def test_different_params_different_entries(tmp_path):
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    fd.get_prices("AAPL", "2024-01-01", "2024-12-31")
    fd.get_prices("AAPL", "2024-01-01", "2025-12-31")  # different end date

    assert inner.calls == 2


def test_refresh_busts_cache(tmp_path):
    inner = CountingClient()
    CachedDataClient(inner, cache_dir=tmp_path).get_prices("AAPL", "2024-01-01", "2024-12-31")
    CachedDataClient(inner, cache_dir=tmp_path, refresh=True).get_prices(
        "AAPL", "2024-01-01", "2024-12-31")

    assert inner.calls == 2


def test_none_item_is_cached(tmp_path):
    """A cached None (ticker without facts) must not re-hit the API."""
    inner = CountingClient(facts=None)
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    assert fd.get_company_facts("ZZZZ") is None
    assert fd.get_company_facts("ZZZZ") is None
    assert inner.calls == 1


def test_item_rehydrates(tmp_path):
    inner = CountingClient(facts=CompanyFacts(ticker="AAPL", sector="Tech"))
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    fd.get_company_facts("AAPL")
    facts = fd.get_company_facts("AAPL")

    assert inner.calls == 1
    assert isinstance(facts, CompanyFacts)
    assert facts.sector == "Tech"


def test_scalar_cached(tmp_path):
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    assert fd.get_market_cap("AAPL", "2024-12-31") == 3.0e12
    assert fd.get_market_cap("AAPL", "2024-12-31") == 3.0e12
    assert inner.calls == 1


def test_snapshot_is_never_cached(tmp_path):
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    first = fd.get_snapshot("AAPL")
    second = fd.get_snapshot("AAPL")

    assert inner.calls == 2
    assert second.price != first.price
    assert not list(tmp_path.glob("*.json"))


def test_daily_price_entries_without_fetch_metadata_are_refreshed(tmp_path):
    import json
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    path = next(tmp_path.glob("*.json"))
    payload = json.loads(path.read_text())
    payload.pop("fetched_at")
    path.write_text(json.dumps(payload))
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 2


def test_answers_about_an_unfinished_day_are_reused_for_ten_minutes(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    from hedge_fund.data import cached

    class Clock:
        now_at = datetime(2024, 1, 1, 10, 0, tzinfo=cached.NEW_YORK)
        @classmethod
        def now(cls, tz):
            return cls.now_at
    Clock.fromisoformat = datetime.fromisoformat
    monkeypatch.setattr(cached, "datetime", Clock)
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)

    # Today's headlines: served from disk inside the window, fetched again after it.
    fd.get_news("AAPL", "2024-01-01", "2024-01-01")
    fd.get_news("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 1
    Clock.now_at += timedelta(seconds=cached.SAME_DAY_TTL + 1)
    fd.get_news("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 2
    # Yesterday's are final.
    fd.get_news("AAPL", "2023-12-29", "2023-12-29")
    Clock.now_at += timedelta(days=1)
    fd.get_news("AAPL", "2023-12-29", "2023-12-29")
    assert inner.calls == 3
    # Today's minute bars follow the same rule; today's daily bar is never reused.
    fd.get_prices("AAPL", "2024-01-02", "2024-01-02", interval="minute")
    fd.get_prices("AAPL", "2024-01-02", "2024-01-02", interval="minute")
    assert inner.calls == 4
    fd.get_prices("AAPL", "2024-01-02", "2024-01-02")
    fd.get_prices("AAPL", "2024-01-02", "2024-01-02")
    assert inner.calls == 6
    # Date-less "latest" answers are final for a backtest, ten minutes for a live process.
    fd.get_company_facts("AAPL")
    Clock.now_at += timedelta(hours=1)
    fd.get_company_facts("AAPL")
    assert inner.calls == 7
    live = CachedDataClient(inner, cache_dir=tmp_path, live=True)
    live.get_company_facts("AAPL")
    assert inner.calls == 8
    live.get_company_facts("AAPL")
    assert inner.calls == 8


def test_incomplete_daily_price_cache_is_refreshed_after_date_ends(tmp_path, monkeypatch):
    from datetime import datetime
    from hedge_fund.data import cached
    class Clock:
        day = 1
        @classmethod
        def now(cls, tz):
            return datetime(2024, 1, cls.day, 23, 0, tzinfo=tz)
    monkeypatch.setattr(cached, "datetime", Clock)
    # Parsing remains the standard library's responsibility.
    Clock.fromisoformat = datetime.fromisoformat
    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 2
    Clock.day = 2
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 3
    fd.get_prices("AAPL", "2024-01-01", "2024-01-01")
    assert inner.calls == 3


def test_earnings_history_refreshed_after_fetch_date(tmp_path, monkeypatch):
    from datetime import datetime
    from hedge_fund.data import cached

    class Clock:
        day = 1
        @classmethod
        def now(cls, tz):
            return datetime(2024, 1, cls.day, 23, 0, tzinfo=tz)

    monkeypatch.setattr(cached, "datetime", Clock)
    Clock.fromisoformat = datetime.fromisoformat

    inner = CountingClient()
    fd = CachedDataClient(inner, cache_dir=tmp_path)
    
    # Day 1: fetch earnings from the API
    fd.get_earnings_history("AAPL", limit=12)
    fd.get_earnings_history("AAPL", limit=12) # cache hit
    assert inner.calls == 1
    
    # Advance clock to Day 2: should miss the cache because earnings history needs to check for newer quarters
    Clock.day = 2
    fd.get_earnings_history("AAPL", limit=12)
    assert inner.calls == 2
    
    # Second fetch on Day 2 should hit cache
    fd.get_earnings_history("AAPL", limit=12)
    assert inner.calls == 2

