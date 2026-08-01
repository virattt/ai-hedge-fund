from unittest.mock import Mock, call, patch

import requests

from src.tools import api as api_module


def test_shared_session_is_requests_session():
    assert isinstance(api_module._session, requests.Session)


def test_make_api_request_get_uses_timeout():
    response = Mock(status_code=200)

    with patch.object(api_module._session, "get", return_value=response) as mock_get:
        result = api_module._make_api_request("https://example.com/test", {"X-Test": "1"})

    assert result is response
    mock_get.assert_called_once_with(
        "https://example.com/test",
        headers={"X-Test": "1"},
        timeout=(5, 30),
    )


def test_make_api_request_post_uses_timeout():
    response = Mock(status_code=200)
    payload = {"ticker": "AAPL"}

    with patch.object(api_module._session, "post", return_value=response) as mock_post:
        result = api_module._make_api_request(
            "https://example.com/test",
            {"X-Test": "1"},
            method="POST",
            json_data=payload,
        )

    assert result is response
    mock_post.assert_called_once_with(
        "https://example.com/test",
        headers={"X-Test": "1"},
        json=payload,
        timeout=(5, 30),
    )


@patch("src.tools.api.time.sleep")
def test_make_api_request_retries_after_429(mock_sleep):
    first = Mock(status_code=429)
    second = Mock(status_code=200)

    with patch.object(api_module._session, "get", side_effect=[first, second]) as mock_get:
        result = api_module._make_api_request("https://example.com/test", {"X-Test": "1"})

    assert result is second
    assert mock_get.call_count == 2
    mock_get.assert_has_calls(
        [
            call("https://example.com/test", headers={"X-Test": "1"}, timeout=(5, 30)),
            call("https://example.com/test", headers={"X-Test": "1"}, timeout=(5, 30)),
        ]
    )
    mock_sleep.assert_called_once_with(60)
