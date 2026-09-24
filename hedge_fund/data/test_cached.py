"""CachedDataClient tests — counting fake, no network."""

from hedge_fund.data.cached import CachedDataClient
from hedge_fund.data.models import CompanyFacts, Price


class CountingClient:
    """Counts calls; returns canned data."""

    def __init__(self, facts=None):
        self.calls = 0
        self._facts = facts

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        self.calls += 1
        return [Price(open=1.0, close=2.0, high=2.0, low=1.0, volume=100,
                      time=f"{start_date}T00:00:00Z")]

    def get_company_facts(self, ticker):
        self.calls += 1
        return self._facts

    def get_market_cap(self, ticker, end_date):
        self.calls += 1
        return 3.0e12


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
