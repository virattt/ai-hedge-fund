from datetime import date, timedelta

import httpx
import pytest

from hedge_fund.data import fxmacrodata


def _rows(total):
    # Newest first, like the API.
    start = date(2024, 1, 1)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "val": float(i)}
        for i in reversed(range(total))
    ]


@pytest.fixture
def fake_api(monkeypatch):
    for name in fxmacrodata.FXMACRODATA_API_KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    requests = []
    rows = _rows(250)

    def handler(request):
        requests.append(request)
        limit = int(request.url.params.get("limit", "20"))
        offset = int(request.url.params.get("offset", "0"))
        page = rows[offset : offset + limit]
        has_more = offset + len(page) < len(rows)
        return httpx.Response(
            200,
            json={
                "data": page,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned_count": len(page),
                    "total_count": len(rows),
                    "has_more": has_more,
                    "next_offset": offset + len(page) if has_more else None,
                },
            },
        )

    real_client = httpx.Client

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(fxmacrodata.httpx, "Client", client_factory)
    return requests


def test_api_key_is_sent_as_header(fake_api):
    with fxmacrodata.FXMacroDataClient(api_key="test-key") as client:
        client.fetch_dataset("forex", base="eur", quote="usd", limit=5)
    request = fake_api[0]
    assert request.headers["X-API-Key"] == "test-key"
    assert "test-key" not in str(request.url)
    assert "api_key" not in request.url.params


def test_no_api_key_header_without_key(fake_api):
    with fxmacrodata.FXMacroDataClient() as client:
        client.fetch_dataset("announcements", currency="usd", indicator="inflation")
    request = fake_api[0]
    assert "X-API-Key" not in request.headers
    assert "api_key" not in request.url.params


def test_fetch_rows_pages_through_window(fake_api):
    with fxmacrodata.FXMacroDataClient(api_key="test-key") as client:
        rows = client.fetch_rows(
            "forex",
            base="eur",
            quote="usd",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
    assert len(rows) == 250
    assert [r.url.params["offset"] for r in fake_api] == ["0", "100", "200"]
    assert all(r.url.params["limit"] == "100" for r in fake_api)
    assert all("api_key" not in r.url.params for r in fake_api)


def test_fetch_rows_limit_caps_rows_and_page_size(fake_api):
    with fxmacrodata.FXMacroDataClient() as client:
        rows = client.fetch_rows("cot", currency="eur", limit=150)
    assert len(rows) == 150
    assert [(r.url.params["limit"], r.url.params["offset"]) for r in fake_api] == [
        ("100", "0"),
        ("50", "100"),
    ]
    assert rows[0]["date"] == "2024-09-06"


def test_fetch_dataset_never_sends_limit_above_100(fake_api):
    with fxmacrodata.FXMacroDataClient() as client:
        client.fetch_dataset("commodity", indicator="gold", limit=500)
    assert fake_api[0].url.params["limit"] == "100"
