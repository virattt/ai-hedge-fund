import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pandas as pd
from src.tools import CMCClient, get_prices, get_market_data, get_financial_metrics, prices_to_df

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Automatically mock environment variables for all tests."""
    with patch.dict(os.environ, {'COINMARKETCAP_API_KEY': 'test_key'}):
        yield

def test_cmc_client_initialization():
    """Test CMC client initialization and authentication."""
    client = CMCClient()
    assert client.base_url == "https://pro-api.coinmarketcap.com/v1"
    assert client.session.headers['X-CMC_PRO_API_KEY'] == 'test_key'
    assert client.session.headers['Accept'] == 'application/json'

def test_cmc_client_missing_key():
    """Test CMC client handles missing API key."""
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="COINMARKETCAP_API_KEY.*not set"):
            CMCClient()

@pytest.fixture
def mock_cmc_response():
    """Mock CMC API response fixture."""
    return {
        'data': {
            'BTC': {
                'quotes': [
                    {
                        'timestamp': '2024-01-01T00:00:00Z',
                        'quote': {
                            'USD': {
                                'price': 42000.0,
                                'volume_24h': 25000000000,
                                'market_cap': 820000000000,
                                'open': 41000.0,
                                'high': 43000.0,
                                'low': 40000.0,
                                'close': 42000.0
                            }
                        }
                    }
                ]
            }
        }
    }

def test_get_prices(mock_cmc_response):
    """Test cryptocurrency price data retrieval."""
    with patch('src.tools.CMCClient._make_request', return_value=mock_cmc_response):
        prices = get_prices('BTC', '2024-01-01', '2024-01-02')
        assert isinstance(prices, dict)
        assert 'data' in prices
        assert 'BTC' in prices['data']
        assert 'quotes' in prices['data']['BTC']

def test_prices_to_df(mock_cmc_response):
    """Test conversion of CMC price data to DataFrame."""
    df = prices_to_df(mock_cmc_response)
    assert isinstance(df, pd.DataFrame)
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    assert all(col in df.columns for col in required_columns)
    assert df.index.name == 'Date'
    assert not df.empty

def test_get_market_data():
    """Test current market data retrieval."""
    mock_data = {
        'data': {
            'BTC': {
                'quote': {
                    'USD': {
                        'price': 42000.0,
                        'volume_24h': 25000000000,
                        'market_cap': 820000000000
                    }
                }
            }
        }
    }
    with patch('src.tools.CMCClient._make_request', return_value=mock_data):
        data = get_market_data('BTC')
        assert isinstance(data, dict)
        assert 'data' in data
        assert 'BTC' in data['data']

def test_rate_limit_handling():
    """Test rate limit handling with retry logic."""
    client = CMCClient()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {'Retry-After': '1'}

    with patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test
        assert client._handle_rate_limit(mock_response) == True
        mock_sleep.assert_called_once_with(1)

def test_error_handling():
    """Test error handling in API requests."""
    with patch('src.tools.CMCClient._make_request') as mock_request:
        mock_request.side_effect = Exception("API Error")
        with pytest.raises(Exception) as exc_info:
            get_market_data('BTC')
        assert "API Error" in str(exc_info.value)
