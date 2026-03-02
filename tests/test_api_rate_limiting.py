import os
import pytest
from unittest.mock import Mock, patch, call

from src.tools.api import _make_api_request, get_prices

class TestRateLimiting:
    """Test suite for API rate limiting functionality (FMP adapter)."""

    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_handles_single_rate_limit(self, mock_get, mock_sleep):
        """Test that API retries once after a 429 and succeeds."""
        mock_429_response = Mock()
        mock_429_response.status_code = 429
        
        mock_200_response = Mock()
        mock_200_response.status_code = 200
        mock_200_response.text = "Success"
        
        mock_get.side_effect = [mock_429_response, mock_200_response]
        
        url = "https://financialmodelingprep.com/stable/test"
        params = {"apikey": "test-key"}
        
        result = _make_api_request(url, params)
        
        assert result.status_code == 200
        assert result.text == "Success"
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(60)

    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_handles_multiple_rate_limits(self, mock_get, mock_sleep):
        """Test that API retries multiple times after 429s."""
        mock_429_response = Mock()
        mock_429_response.status_code = 429
        
        mock_200_response = Mock()
        mock_200_response.status_code = 200
        mock_200_response.text = "Success"
        
        mock_get.side_effect = [
            mock_429_response, 
            mock_429_response, 
            mock_429_response, 
            mock_200_response
        ]
        
        url = "https://financialmodelingprep.com/stable/test"
        params = {"apikey": "test-key"}
        
        result = _make_api_request(url, params)
        
        assert result.status_code == 200
        assert result.text == "Success"
        assert mock_get.call_count == 4
        assert mock_sleep.call_count == 3
        expected_calls = [call(60), call(90), call(120)]
        mock_sleep.assert_has_calls(expected_calls)

    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_ignores_other_errors(self, mock_get, mock_sleep):
        """Test that non-429 errors are returned without retrying."""
        mock_500_response = Mock()
        mock_500_response.status_code = 500
        mock_500_response.text = "Internal Server Error"
        
        mock_get.return_value = mock_500_response
        
        url = "https://financialmodelingprep.com/stable/test"
        params = {"apikey": "test-key"}
        
        result = _make_api_request(url, params)
        
        assert result.status_code == 500
        assert result.text == "Internal Server Error"
        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()

    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_normal_success_requests(self, mock_get, mock_sleep):
        """Test that successful requests return immediately without retry."""
        mock_200_response = Mock()
        mock_200_response.status_code = 200
        mock_200_response.text = "Success"
        
        mock_get.return_value = mock_200_response
        
        url = "https://financialmodelingprep.com/stable/test"
        params = {"apikey": "test-key"}
        
        result = _make_api_request(url, params)
        
        assert result.status_code == 200
        assert result.text == "Success"
        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()

    @patch('src.tools.api._cache')
    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_full_integration(self, mock_get, mock_sleep, mock_cache):
        """Test that get_prices function properly handles rate limiting."""
        mock_cache.get_prices.return_value = None
        
        mock_429_response = Mock()
        mock_429_response.status_code = 429
        
        mock_200_response = Mock()
        mock_200_response.status_code = 200
        mock_200_response.json.return_value = [
            {
                "date": "2024-01-01",
                "open": 100.0,
                "close": 101.0,
                "high": 102.0,
                "low": 99.0,
                "volume": 1000
            }
        ]
        
        mock_get.side_effect = [mock_429_response, mock_200_response]
        
        with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
            result = get_prices("AAPL", "2024-01-01", "2024-01-02")
        
        assert len(result) == 1
        assert result[0].open == 100.0
        assert result[0].close == 101.0
        
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(60)
        
        mock_cache.get_prices.assert_called_once()
        mock_cache.set_prices.assert_called_once()

    @patch('src.tools.api.time.sleep')
    @patch('src.tools.api.requests.get')
    def test_max_retries_exceeded(self, mock_get, mock_sleep):
        """Test that function stops retrying after max_retries and returns final 429."""
        mock_429_response = Mock()
        mock_429_response.status_code = 429
        mock_429_response.text = "Too Many Requests"
        
        mock_get.return_value = mock_429_response
        
        url = "https://financialmodelingprep.com/stable/test"
        params = {"apikey": "test-key"}
        
        result = _make_api_request(url, params, max_retries=2)
        
        assert result.status_code == 429
        assert result.text == "Too Many Requests"
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
        expected_calls = [call(60), call(90)]
        mock_sleep.assert_has_calls(expected_calls)


if __name__ == "__main__":
    pytest.main([__file__])
