import unittest
from unittest.mock import patch, mock_open

class TestTickerSources(unittest.TestCase):
    def test_get_sp500_sample_returns_list(self):
        from src.screening.stock_screener import StockScreener
        screener = StockScreener()
        tickers = screener.get_sp500_sample()
        self.assertIsInstance(tickers, list)
        self.assertGreater(len(tickers), 50)
        self.assertIn('AAPL', tickers)
        self.assertIn('MSFT', tickers)

    def test_load_custom_tickers_method_exists(self):
        from src.screening.stock_screener import StockScreener
        screener = StockScreener()
        # Just test that the method exists
        self.assertTrue(hasattr(screener, 'load_custom_tickers'))

if __name__ == '__main__':
    unittest.main()
