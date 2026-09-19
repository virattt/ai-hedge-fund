"""FDClient contract tests — mocked HTTP, no API key required.

Pins the two Phase 0 guarantees:

1. Fail-loud: infrastructure failures RAISE FDClientError instead of
   silently returning empty (silent empties poison backtests — missing
   data reads as "no signal").
2. Point-in-time: get_financial_metrics filters on filing_date (when the
   data became public), not report_period (which leaks 3-6 weeks of
   future into a backtest).
"""

import pytest
import requests

from hedge_fund.data import FDClient, FDClientError


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def client():
    c = FDClient(api_key="test-key")
    yield c
    c.close()


def test_missing_api_key_raises(monkeypatch):
    """Live construction names FINANCIAL_DATASETS_API_KEY instead of failing later."""
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="FINANCIAL_DATASETS_API_KEY"):
        FDClient()


def _stub(client, responses):
    """Replace the session's request method; each call pops one response.

    A response that is an Exception instance is raised instead.
    """
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    client._session.request = fake_request
    return calls


# ---------------------------------------------------------------------------
# Fail-loud contract
# ---------------------------------------------------------------------------

def test_http_500_raises(client):
    _stub(client, [_FakeResponse(500, text="internal error")])
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 500


def test_http_401_raises(client):
    _stub(client, [_FakeResponse(401, text="bad key")])
    with pytest.raises(FDClientError) as exc_info:
        client.get_financial_metrics("AAPL", "2024-12-31")
    assert exc_info.value.status_code == 401
    assert exc_info.value.path == "/financial-metrics/"
    assert "FINANCIAL_DATASETS_API_KEY" in str(exc_info.value)


def test_http_403_raises_with_key_hint(client):
    _stub(client, [_FakeResponse(403, text="forbidden")])
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 403
    assert exc_info.value.path == "/prices/"
    assert "FINANCIAL_DATASETS_API_KEY" in str(exc_info.value)


def test_network_error_raises(client):
    _stub(client, [requests.ConnectionError("boom")])
    with pytest.raises(FDClientError):
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")


def test_404_means_no_data_not_failure(client):
    """404 is 'this data does not exist' — a data fact, not a failure."""
    _stub(client, [_FakeResponse(404)])
    assert client.get_financial_metrics("ZZZZ", "2024-12-31") == []


def test_429_retries_then_raises_when_exhausted(client, monkeypatch):
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    _stub(client, [_FakeResponse(429)] * (len(FDClient._RETRY_DELAYS) + 1))
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 429
    assert "quota" in str(exc_info.value).lower() or "retry" in str(exc_info.value).lower()


def test_429_then_success_recovers(client, monkeypatch):
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    _stub(client, [
        _FakeResponse(429),
        _FakeResponse(200, {"prices": [{
            "open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0,
            "volume": 100, "time": "2024-01-02",
        }]}),
    ])
    prices = client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert len(prices) == 1


# ---------------------------------------------------------------------------
# Point-in-time contract
# ---------------------------------------------------------------------------

def test_financial_metrics_filters_on_filing_date(client):
    """The metrics query must use filing_date_lte (public-knowledge date),
    never report_period_lte (fiscal period end = lookahead leak)."""
    calls = _stub(client, [_FakeResponse(200, {"financial_metrics": []})])

    client.get_financial_metrics("AAPL", "2024-06-30", period="ttm", limit=4)

    params = calls[0]["params"]
    assert params["filing_date_lte"] == "2024-06-30"
    assert "report_period_lte" not in params


# ---------------------------------------------------------------------------
# Pagination contract
# ---------------------------------------------------------------------------

def _price_row(day):
    return {
        "open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0,
        "volume": 100, "time": f"2024-01-{day:02d}",
    }


def test_follows_next_page_url_to_the_end(client):
    """The API caps list responses at a fixed page size; the client must
    reassemble the full result by following next_page_url until absent."""
    calls = _stub(client, [
        _FakeResponse(200, {
            "prices": [_price_row(1), _price_row(2)],
            "next_page_url": "https://api.financialdatasets.ai/prices/?cursor=page2",
        }),
        _FakeResponse(200, {
            "prices": [_price_row(3), _price_row(4)],
            "next_page_url": "https://api.financialdatasets.ai/prices/?cursor=page3",
        }),
        _FakeResponse(200, {"prices": [_price_row(5)]}),
    ])

    prices = client.get_prices("AAPL", "2024-01-01", "2024-12-31")

    assert [p.time for p in prices] == [f"2024-01-0{d}" for d in (1, 2, 3, 4, 5)]
    # Pages 2+ request the next_page_url verbatim — no re-derived params.
    assert calls[1]["url"] == "https://api.financialdatasets.ai/prices/?cursor=page2"
    assert calls[2]["url"] == "https://api.financialdatasets.ai/prices/?cursor=page3"
    assert "params" not in calls[1]


def test_no_next_page_url_means_single_request(client):
    calls = _stub(client, [_FakeResponse(200, {"prices": [_price_row(1)]})])
    prices = client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert len(prices) == 1
    assert len(calls) == 1


def test_mid_walk_404_keeps_accumulated_rows(client):
    """A 404 on page 2+ ends the stream; rows already fetched are kept."""
    _stub(client, [
        _FakeResponse(200, {
            "prices": [_price_row(1)],
            "next_page_url": "https://api.financialdatasets.ai/prices/?cursor=page2",
        }),
        _FakeResponse(404),
    ])
    prices = client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert len(prices) == 1


def test_mid_walk_500_still_fails_loud(client):
    """The fail-loud contract survives pagination: a real failure on any
    page raises instead of silently returning a partial series."""
    _stub(client, [
        _FakeResponse(200, {
            "prices": [_price_row(1)],
            "next_page_url": "https://api.financialdatasets.ai/prices/?cursor=page2",
        }),
        _FakeResponse(500, text="internal error"),
    ])
    with pytest.raises(FDClientError):
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")


# ---------------------------------------------------------------------------
# Auth / quota vs empty payload (especially news)
# ---------------------------------------------------------------------------

def _news_row():
    return {
        "ticker": "AAPL",
        "title": "Apple ships a phone",
        "source": "Reuters",
        "date": "2024-06-03",
        "url": "https://example.test/aapl",
    }


def test_get_news_empty_list_is_no_data(client):
    """200 + empty `news` list is genuine no-articles, not a failure."""
    _stub(client, [_FakeResponse(200, {"news": []})])
    assert client.get_news("AAPL", "2024-12-31") == []


def test_get_news_missing_key_is_no_data(client):
    """200 with the `news` key omitted is no-data (empty list)."""
    _stub(client, [_FakeResponse(200, {"next_page_url": None})])
    assert client.get_news("AAPL", "2024-12-31") == []


def test_get_news_bare_json_list_is_no_data(client):
    """A 200 whose body is a bare empty JSON list is no-data, not a crash."""
    _stub(client, [_FakeResponse(200, [])])
    assert client.get_news("AAPL", "2024-12-31") == []


def test_get_news_401_is_auth_failure_not_empty(client):
    _stub(client, [_FakeResponse(401, text="invalid api key")])
    with pytest.raises(FDClientError) as exc_info:
        client.get_news("AAPL", "2024-12-31")
    err = exc_info.value
    assert err.status_code == 401
    assert err.path == "/news/"
    assert "FINANCIAL_DATASETS_API_KEY" in str(err)
    assert "not missing data" in str(err)


def test_get_news_403_is_auth_failure_not_empty(client):
    _stub(client, [_FakeResponse(403, text="forbidden")])
    with pytest.raises(FDClientError) as exc_info:
        client.get_news("AAPL", "2024-12-31")
    assert exc_info.value.status_code == 403
    assert exc_info.value.path == "/news/"
    assert "FINANCIAL_DATASETS_API_KEY" in str(exc_info.value)


def test_get_news_429_exhausted_is_quota_failure_not_empty(client, monkeypatch):
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    _stub(client, [_FakeResponse(429, text="rate limited")] * (len(FDClient._RETRY_DELAYS) + 1))
    with pytest.raises(FDClientError) as exc_info:
        client.get_news("AAPL", "2024-12-31")
    err = exc_info.value
    assert err.status_code == 429
    assert err.path == "/news/"
    assert "quota" in str(err).lower()


def test_get_news_populated_still_parses(client):
    _stub(client, [_FakeResponse(200, {"news": [_news_row()]})])
    news = client.get_news("AAPL", "2024-12-31")
    assert len(news) == 1
    assert news[0].title == "Apple ships a phone"


def test_empty_prices_payload_is_no_data_not_auth(client):
    """Same no-data contract on another list endpoint: empty != 401."""
    _stub(client, [_FakeResponse(200, {"prices": []})])
    assert client.get_prices("AAPL", "2024-01-01", "2024-12-31") == []


def test_financial_metrics_parses_filing_metadata(client):
    _stub(client, [_FakeResponse(200, {"financial_metrics": [{
        "ticker": "AAPL",
        "report_period": "2024-03-30",
        "period": "quarterly",
        "filing_date": "2024-05-02",
        "filing_datetime": "2024-05-02T16:31:00-04:00",
        "market_cap": 3.0e12,
    }]})])

    m = client.get_financial_metrics("AAPL", "2024-06-30")[0]

    assert m.filing_date == "2024-05-02"
    assert m.filing_datetime == "2024-05-02T16:31:00-04:00"
    assert m.report_period == "2024-03-30"
