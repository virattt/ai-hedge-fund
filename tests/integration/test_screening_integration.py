import unittest
from unittest.mock import patch, Mock

class TestScreeningIntegration(unittest.TestCase):
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_end_to_end_screening_workflow(self, mock_run_hedge_fund):
        from src.screening.stock_screener import StockScreener
        
        # Mock successful hedge fund analysis
        mock_run_hedge_fund.return_value = {
            'analyst_signals': {
                'warren_buffett': {'signal': 'bullish', 'confidence': 85},
                'peter_lynch': {'signal': 'neutral', 'confidence': 70}
            }
        }
        
        screener = StockScreener()
        result = screener.analyze_single_stock('AAPL')
        
        self.assertEqual(result.ticker, 'AAPL')
        self.assertEqual(result.signal_counts['bullish'], 1)
        self.assertEqual(result.signal_counts['neutral'], 1)
        self.assertAlmostEqual(result.overall_score, 0.75, places=2)

if __name__ == '__main__':
    unittest.main()
