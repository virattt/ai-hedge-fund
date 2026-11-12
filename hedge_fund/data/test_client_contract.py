"""FDClient contract tests — mocked HTTP, no API key required.

Pins the two Phase 0 guarantees:

1. Fail-loud: infrastructure failures RAISE FDClientError instead of
   silently returning empty (silent empties poison backtests — missing
   data reads as "no signal").
2. Point-in-time: get_financial_metrics filters on filing_date (when the
   data became public), not report_period (which leaks 3-6 weeks of
   future into a backtest).
"""

import base64
import json

import pytest
import requests

from hedge_fund.data import FDClient, FDClientError, has_data_credential
from hedge_fund.data import client as client_module
from hedge_fund.data.wallet import PaymentFailed


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

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
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    _stub(client, [_FakeResponse(429)] * (len(FDClient._RETRY_DELAYS) + 1))
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 429


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


def test_503_retries_like_429(client, monkeypatch):
    """x402's facilitator answers 503 with Retry-After when it is briefly
    down and charges nothing for it; the client waits and asks again."""
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    _stub(client, [_FakeResponse(503), _FakeResponse(200, {"prices": []})])
    assert client.get_prices("AAPL", "2024-01-01", "2024-12-31") == []
    _stub(client, [_FakeResponse(503)] * (len(FDClient._RETRY_DELAYS) + 1))
    with pytest.raises(FDClientError) as exc_info:
        client.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Credentials: an API key, or a wallet that pays per call with x402
# ---------------------------------------------------------------------------

def _plain_session(private_key):
    session = requests.Session()
    session.wallet = private_key
    return session


@pytest.fixture
def no_env_credentials(monkeypatch):
    """conftest loads .env, so a developer's real key is in the environment;
    these tests must see only what they pass in."""
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    monkeypatch.delenv("X402_WALLET_PRIVATE_KEY", raising=False)


def test_wallet_alone_pays_per_call_and_sends_no_key(monkeypatch, no_env_credentials):
    monkeypatch.setattr(client_module, "payment_session", _plain_session)
    with FDClient(api_key="", wallet_key="0xabc") as c:
        assert c.pays_per_call()
        assert c._session.wallet == "0xabc"
        assert "X-API-Key" not in c._session.headers


def test_api_key_wins_over_a_wallet(monkeypatch, no_env_credentials):
    """The API's own rule: a request carrying X-API-KEY bills the account,
    never the wallet. So the client never pays when it has a key."""
    monkeypatch.setattr(client_module, "payment_session", lambda key: pytest.fail("built a paying session"))
    with FDClient(api_key="test-key", wallet_key="0xabc") as c:
        assert not c.pays_per_call()
        assert c._session.headers["X-API-Key"] == "test-key"


def test_credentials_come_from_the_environment(monkeypatch, no_env_credentials):
    monkeypatch.setattr(client_module, "payment_session", _plain_session)
    assert not has_data_credential()
    with FDClient() as c:
        assert not c.pays_per_call() and c._session.headers["X-API-Key"] == ""
    monkeypatch.setenv("X402_WALLET_PRIVATE_KEY", "0xenv")
    assert has_data_credential()
    with FDClient() as c:
        assert c.pays_per_call() and c._session.wallet == "0xenv"
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "env-key")
    assert has_data_credential()
    with FDClient() as c:
        assert not c.pays_per_call()


def test_missing_x402_package_fails_with_the_install_command(monkeypatch, no_env_credentials):
    def no_package(private_key):
        raise ImportError("X402_WALLET_PRIVATE_KEY is set but the x402 package is not installed: pip install 'aihf[x402]'")
    monkeypatch.setattr(client_module, "payment_session", no_package)
    with pytest.raises(FDClientError, match=r"pip install 'aihf\[x402\]'"):
        FDClient(api_key="", wallet_key="0xabc")


def test_payment_failure_fails_loud(monkeypatch, no_env_credentials):
    monkeypatch.setattr(client_module, "payment_session", _plain_session)
    with FDClient(api_key="", wallet_key="0xabc") as c:
        _stub(c, [PaymentFailed("insufficient USDC")])
        with pytest.raises(FDClientError, match="insufficient USDC"):
            c.get_prices("AAPL", "2024-01-01", "2024-12-31")


def test_402_on_a_wallet_names_the_reason_from_the_payment_header(monkeypatch, no_env_credentials):
    """After the adapter pays, a 402 means the payment was refused. The body
    says only "Payment required"; the reason is in the PAYMENT-REQUIRED
    header, so the error names it."""
    monkeypatch.setattr(client_module, "payment_session", _plain_session)
    terms = base64.b64encode(json.dumps({"x402Version": 2, "error": "payer_blocked", "accepts": []}).encode()).decode()
    with FDClient(api_key="", wallet_key="0xabc") as c:
        _stub(c, [_FakeResponse(402, text='{"error": "Payment required"}', headers={"PAYMENT-REQUIRED": terms})])
        with pytest.raises(FDClientError, match="payment from the wallet failed: payer_blocked") as exc_info:
            c.get_snapshot("AAPL")
    assert exc_info.value.status_code == 402
    with FDClient(api_key="", wallet_key="0xabc") as c:
        _stub(c, [_FakeResponse(402, text="Payment required")])
        with pytest.raises(FDClientError, match="no payment terms in the response"):
            c.get_snapshot("AAPL")


def test_403_on_a_wallet_explains_the_history_window(monkeypatch, no_env_credentials):
    """x402 serves the last 365 days; the API's 403 names the window start,
    and the client adds what to do about it. A keyed client gets a 403 for
    other reasons, so it gets no such hint."""
    monkeypatch.setattr(client_module, "payment_session", _plain_session)
    with FDClient(api_key="", wallet_key="0xabc") as c:
        _stub(c, [_FakeResponse(403, text="window starts 2025-01-01")])
        with pytest.raises(FDClientError) as exc_info:
            c.get_prices("AAPL", "2024-01-01", "2024-12-31")
    message = str(exc_info.value)
    assert "window starts 2025-01-01" in message and "last 365 days" in message
    assert "FINANCIAL_DATASETS_API_KEY" in message
    with FDClient(api_key="test-key") as c:
        _stub(c, [_FakeResponse(403, text="forbidden")])
        with pytest.raises(FDClientError) as exc_info:
            c.get_prices("AAPL", "2024-01-01", "2024-12-31")
    assert "last 365 days" not in str(exc_info.value)


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


def test_snapshot_is_a_single_quote_not_a_list(client):
    calls = _stub(client, [_FakeResponse(200, {"snapshot": {
        "ticker": "BRK.A", "price": 756000.0, "day_change": 1210.0,
        "day_change_percent": 0.16, "time": "2026-10-05T14:28:39Z",
        "time_milliseconds": 1791210519441,
    }})])

    snap = client.get_snapshot("BRK.A")

    assert calls[0]["url"].endswith("/prices/snapshot/")
    assert calls[0]["params"] == {"ticker": "BRK.A"}
    assert snap.price == 756000.0
    assert snap.time == "2026-10-05T14:28:39Z"


def test_snapshot_404_means_unknown_ticker(client):
    _stub(client, [_FakeResponse(404)])
    assert client.get_snapshot("ZZZZ") is None


def test_snapshot_500_fails_loud(client):
    _stub(client, [_FakeResponse(500, text="internal error")])
    with pytest.raises(FDClientError):
        client.get_snapshot("AAPL")


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


# ---------------------------------------------------------------------------
# Screener: point-in-time by construction, 404 is a failure
# ---------------------------------------------------------------------------

from hedge_fund.data import CallMeter, OrderBy, ScreenFilter  # noqa: E402


def _screen_row(ticker, **values):
    return {"ticker": ticker, "filing_date": "2026-07-31", "report_period": "2026-06-30",
            "currency": "USD", "sector": "Financials", "industry": "Banks", **values}


def test_screen_posts_the_date_the_filters_and_the_full_limit(client):
    calls = _stub(client, [_FakeResponse(200, {"results": [_screen_row("JPM", market_cap=8e11)], "as_of": "2026-08-06"})])
    rows = client.screen("2026-08-06", [ScreenFilter(field="market_cap", operator="gt", value=1e9)])
    assert [r.ticker for r in rows] == ["JPM"] and rows[0].values == {"market_cap": 8e11}
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://api.financialdatasets.ai/financials/search/screener"
    assert calls[0]["json"] == {
        "as_of": "2026-08-06",
        "filters": [{"field": "market_cap", "operator": "gt", "value": 1e9}],
        "limit": 20_000,
    }


def test_screen_sends_order_by_only_when_asked(client):
    calls = _stub(client, [_FakeResponse(200, {"results": []})])
    client.screen("2026-08-06", [ScreenFilter(field="market_cap", operator="gt", value=1e9)],
                  order_by=OrderBy(field="revenue_growth", direction="asc"), limit=40)
    assert calls[0]["json"]["order_by"] == {"field": "revenue_growth", "direction": "asc"}
    assert calls[0]["json"]["limit"] == 40


def test_screen_refuses_to_run_without_a_date_or_a_filter(client):
    calls = _stub(client, [])
    with pytest.raises(ValueError, match="as_of"):
        client.screen("", [ScreenFilter(field="market_cap", operator="gt", value=1e9)])
    with pytest.raises(ValueError, match="filter"):
        client.screen("2026-08-06", [])
    assert calls == []


def test_screen_404_is_a_failure_and_empty_results_are_an_answer(client):
    _stub(client, [_FakeResponse(404)])
    with pytest.raises(FDClientError, match="404") as exc_info:
        client.screen("2026-08-06", [ScreenFilter(field="market_cap", operator="gt", value=1e9)])
    assert exc_info.value.status_code == 404
    _stub(client, [_FakeResponse(200, {"results": []})])
    assert client.screen("2026-08-06", [ScreenFilter(field="market_cap", operator="gt", value=1e9)]) == []


def test_screener_fields_parses_the_vocabulary_and_404_fails_loud(client):
    calls = _stub(client, [_FakeResponse(200, {
        "metrics": {"financial_metrics": ["market_cap", "stock_price"], "company": {"sector": ["Energy"], "industry": []}},
        "aliases": {}, "company_filters": {"values": {"sector": ["Energy"], "industry": []}},
        "operators": ["gt", "eq", "in"],
    })])
    fields = client.screener_fields()
    assert calls[0]["url"] == "https://api.financialdatasets.ai/financials/search/screener/filters"
    assert fields.numeric == {"market_cap", "stock_price"} and fields.sectors == {"Energy"}
    _stub(client, [_FakeResponse(404)])
    with pytest.raises(FDClientError, match="404"):
        client.screener_fields()


# ---------------------------------------------------------------------------
# Call meter: every attempt that reaches the wire counts
# ---------------------------------------------------------------------------

def test_the_meter_counts_retries_and_pages_by_bare_path(monkeypatch):
    monkeypatch.setattr("hedge_fund.data.client.time.sleep", lambda s: None)
    meter = CallMeter()
    with FDClient(api_key="test-key", meter=meter) as c:
        _stub(c, [
            _FakeResponse(503),
            _FakeResponse(200, {"prices": [_price_row(1)], "next_page_url": "https://api.financialdatasets.ai/prices/?cursor=page2"}),
            _FakeResponse(200, {"prices": [_price_row(2)]}),
            _FakeResponse(200, {"company_facts": {"ticker": "AAPL"}}),
        ])
        c.get_prices("AAPL", "2024-01-01", "2024-01-02")
        c.get_company_facts("AAPL")
    assert meter.calls == 4
    assert meter.by_path == {"/prices/": 3, "/company/facts/": 1}


def test_one_meter_sums_across_clients_and_each_client_has_its_own_by_default():
    shared = CallMeter()
    with FDClient(api_key="k", meter=shared) as a, FDClient(api_key="k", meter=shared) as b:
        _stub(a, [_FakeResponse(200, {"company_facts": {"ticker": "AAPL"}})])
        _stub(b, [_FakeResponse(200, {"company_facts": {"ticker": "MSFT"}})])
        a.get_company_facts("AAPL")
        b.get_company_facts("MSFT")
    assert shared.calls == 2
    with FDClient(api_key="k") as c:
        _stub(c, [_FakeResponse(404)])
        c.get_company_facts("NOPE")
        assert c.meter.calls == 1
    assert shared.calls == 2
