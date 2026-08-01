import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agents.sentiment import sentiment_analyst_agent
from src.data.models import AdanosSentiment
from src.tools.api import get_adanos_market_sentiment


def _response(status_code: int, payload: dict | None = None):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    return response


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_fetches_available_sources(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = None
    mock_get.side_effect = [
        _response(
            200,
            {
                "found": True,
                "buzz_score": 72.5,
                "sentiment_score": 0.42,
                "bullish_pct": 61,
                "bearish_pct": 18,
                "trend": "rising",
                "mentions": 120,
            },
        ),
        _response(200, {"found": False}),
        _response(500),
        _response(
            200,
            {
                "found": True,
                "buzz_score": 48.0,
                "sentiment_score": -0.25,
                "bullish_pct": 30,
                "bearish_pct": 55,
                "trend": "falling",
                "trade_count": 12,
            },
        ),
    ]

    results = get_adanos_market_sentiment("TSLA", "2026-05-01", "2026-05-07", api_key="test-key")

    assert [result.source for result in results] == ["reddit", "polymarket"]
    assert results[0].activity_count == 120
    assert results[1].activity_count == 12
    assert mock_get.call_count == 4
    first_url = mock_get.call_args_list[0].args[0]
    assert first_url == "https://api.adanos.org/reddit/stocks/v1/stock/TSLA?from=2026-05-01&to=2026-05-07"
    assert mock_get.call_args_list[0].kwargs["headers"] == {"X-API-Key": "test-key"}
    assert mock_get.call_args_list[0].kwargs["timeout"] == 5
    mock_cache.set_adanos_sentiment.assert_not_called()


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_caches_complete_source_fetch(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = None
    mock_get.side_effect = [
        _response(
            200,
            {
                "found": True,
                "buzz_score": 72.5,
                "sentiment_score": 0.42,
                "bullish_pct": 61,
                "bearish_pct": 18,
                "trend": "rising",
                "mentions": 120,
            },
        ),
        _response(200, {"found": False}),
        _response(200, {"found": False}),
        _response(200, {"found": False}),
    ]

    results = get_adanos_market_sentiment("TSLA", "2026-05-01", "2026-05-07", api_key="test-key")

    assert [result.source for result in results] == ["reddit"]
    mock_cache.set_adanos_sentiment.assert_called_once()


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_caches_404_no_data_sources(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = None
    mock_get.side_effect = [
        _response(
            200,
            {
                "found": True,
                "buzz_score": 72.5,
                "sentiment_score": 0.42,
                "bullish_pct": 61,
                "bearish_pct": 18,
                "trend": "rising",
                "mentions": 120,
            },
        ),
        _response(404),
        _response(404),
        _response(404),
    ]

    results = get_adanos_market_sentiment("TSLA", "2026-05-01", "2026-05-07", api_key="test-key")

    assert [result.source for result in results] == ["reddit"]
    mock_cache.set_adanos_sentiment.assert_called_once()


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_encodes_ticker_path_segment(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = None
    mock_get.side_effect = [_response(404), _response(404), _response(404), _response(404)]

    get_adanos_market_sentiment("BRK/B", "2026-05-01", "2026-05-07", api_key="test-key")

    first_url = mock_get.call_args_list[0].args[0]
    assert first_url == "https://api.adanos.org/reddit/stocks/v1/stock/BRK%2FB?from=2026-05-01&to=2026-05-07"


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_skips_malformed_source_payloads(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = None
    mock_get.side_effect = [
        _response(200, ["not", "an", "object"]),
        _response(
            200,
            {
                "found": True,
                "buzz_score": {"bad": "shape"},
                "sentiment_score": 0.2,
            },
        ),
        _response(200, {"found": False}),
        _response(200, {"found": False}),
    ]

    assert get_adanos_market_sentiment("TSLA", "2026-05-01", "2026-05-07", api_key="test-key") == []
    mock_cache.set_adanos_sentiment.assert_not_called()


@patch("src.tools.api.requests.get")
@patch("src.tools.api._cache")
def test_get_adanos_market_sentiment_uses_cache(mock_cache, mock_get):
    mock_cache.get_adanos_sentiment.return_value = [
        {
            "source": "reddit",
            "found": True,
            "buzz_score": 72.5,
            "sentiment_score": 0.42,
            "bullish_pct": 61,
            "bearish_pct": 18,
            "trend": "rising",
            "activity_count": 120,
        }
    ]

    results = get_adanos_market_sentiment("TSLA", "2026-05-01", "2026-05-07", api_key="test-key")

    assert [result.source for result in results] == ["reddit"]
    assert results[0].sentiment_score == 0.42
    mock_get.assert_not_called()
    mock_cache.set_adanos_sentiment.assert_not_called()


@patch.dict("os.environ", {}, clear=True)
@patch("src.tools.api.requests.get")
def test_get_adanos_market_sentiment_skips_without_api_key(mock_get):
    assert get_adanos_market_sentiment("TSLA") == []
    mock_get.assert_not_called()


@patch.dict("os.environ", {}, clear=True)
@patch("src.agents.sentiment.get_adanos_market_sentiment")
@patch("src.agents.sentiment.get_company_news")
@patch("src.agents.sentiment.get_insider_trades")
def test_sentiment_agent_keeps_adanos_optional(mock_insider_trades, mock_company_news, mock_adanos):
    mock_insider_trades.return_value = []
    mock_company_news.return_value = []

    state = {
        "messages": [],
        "data": {
            "tickers": ["TSLA"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-07",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False},
    }

    sentiment_analyst_agent(state)

    mock_adanos.assert_not_called()
    reasoning = state["data"]["analyst_signals"]["sentiment_analyst_agent"]["TSLA"]["reasoning"]
    assert "adanos_market_sentiment" not in reasoning


@patch("src.agents.sentiment.get_adanos_market_sentiment")
@patch("src.agents.sentiment.get_company_news")
@patch("src.agents.sentiment.get_insider_trades")
def test_sentiment_agent_uses_adanos_market_sentiment(mock_insider_trades, mock_company_news, mock_adanos):
    mock_insider_trades.return_value = []
    mock_company_news.return_value = []
    mock_adanos.return_value = [
        AdanosSentiment(source="reddit", found=True, buzz_score=80.0, sentiment_score=0.6, bullish_pct=70, bearish_pct=10, trend="rising", activity_count=42),
        AdanosSentiment(source="x", found=True, buzz_score=55.0, sentiment_score=0.2, bullish_pct=55, bearish_pct=20, trend="stable", activity_count=18),
    ]
    request = SimpleNamespace(api_keys={"ADANOS_API_KEY": "test-adanos-key"})
    state = {
        "messages": [],
        "data": {
            "tickers": ["TSLA"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-07",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False, "request": request},
    }

    result = sentiment_analyst_agent(state)
    sentiment_payload = json.loads(result["messages"][0].content)["TSLA"]

    mock_adanos.assert_called_once_with(
        ticker="TSLA",
        start_date="2026-05-01",
        end_date="2026-05-07",
        api_key="test-adanos-key",
    )
    assert sentiment_payload["signal"] == "bullish"
    assert sentiment_payload["confidence"] == 100.0
    adanos_reasoning = sentiment_payload["reasoning"]["adanos_market_sentiment"]
    assert adanos_reasoning["signal"] == "bullish"
    assert adanos_reasoning["metrics"]["source_count"] == 2
    assert adanos_reasoning["metrics"]["sources"][0]["source"] == "reddit"
