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

from v2.data import FDClient, FDClientError


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def client():
    c = FDClient(api_key="test-key")
    yield c
    c.close()


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


def test_network_error_raises(client):
    _stub(client, [requests.ConnectionError("boom")])
    with pytest.raises(FDClientError):
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")


def test_404_means_no_data_not_failure(client):
    """404 is 'this data does not exist' — a data fact, not a failure."""
    _stub(client, [_FakeResponse(404)])
    assert client.get_financial_metrics("ZZZZ", "2024-12-31") == []


def test_429_retries_then_raises_when_exhausted(client, monkeypatch):
    monkeypatch.setattr("v2.data.client.time.sleep", lambda s: None)
    _stub(client, [_FakeResponse(429)] * (len(FDClient._RETRY_DELAYS) + 1))
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 429


def test_429_then_success_recovers(client, monkeypatch):
    monkeypatch.setattr("v2.data.client.time.sleep", lambda s: None)
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
