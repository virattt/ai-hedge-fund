import datetime
from unittest.mock import Mock, patch

from src.tools.api import get_company_news


def _news_payload(ticker: str = "ENDPOINTTEST") -> dict:
    return {
        "news": [
            {
                "ticker": ticker,
                "title": "Company reports quarterly results",
                "author": "Reporter",
                "source": "Example News",
                "date": f"{datetime.date.today().isoformat()}T12:00:00Z",
                "url": "https://example.com/article",
                "sentiment": None,
            }
        ]
    }


@patch("src.tools.api._make_api_request")
def test_company_news_uses_supported_latest_news_parameters(mock_request):
    response = Mock(status_code=200)
    response.json.return_value = _news_payload()
    mock_request.return_value = response

    result = get_company_news(
        ticker="ENDPOINTTEST",
        end_date=datetime.date.today().isoformat(),
        limit=1000,
        api_key="test-key",
    )

    assert len(result) == 1
    mock_request.assert_called_once_with(
        "https://api.financialdatasets.ai/news?ticker=ENDPOINTTEST&limit=10",
        {"X-API-KEY": "test-key"},
    )


@patch("src.tools.api._make_api_request")
def test_company_news_does_not_use_latest_news_for_historical_request(mock_request):
    result = get_company_news(
        ticker="HISTORICALTEST",
        start_date="2024-01-01",
        end_date="2024-01-31",
        limit=10,
        api_key="test-key",
    )

    assert result == []
    mock_request.assert_not_called()


@patch("src.tools.api._make_api_request")
def test_company_news_encodes_ticker_and_enforces_minimum_limit(mock_request):
    response = Mock(status_code=200)
    response.json.return_value = _news_payload("BRK B")
    mock_request.return_value = response

    result = get_company_news(
        ticker="BRK B",
        end_date=datetime.date.today().isoformat(),
        limit=0,
    )

    assert len(result) == 1
    mock_request.assert_called_once_with(
        "https://api.financialdatasets.ai/news?ticker=BRK+B&limit=1",
        {},
    )
