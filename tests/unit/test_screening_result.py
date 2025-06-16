import unittest
from dataclasses import dataclass
from typing import Dict, Optional

class TestScreeningResult(unittest.TestCase):
    def test_screening_result_creation(self):
        from src.screening.stock_screener import ScreeningResult
        result = ScreeningResult(
            ticker='AAPL',
            overall_score=0.85,
            signal_counts={'bullish': 7, 'neutral': 2, 'bearish': 1},
            agent_signals={'warren_buffett': {'signal': 'bullish', 'confidence': 85}}
        )
        self.assertEqual(result.ticker, 'AAPL')
        self.assertEqual(result.overall_score, 0.85)
        self.assertEqual(result.signal_counts['bullish'], 7)
        self.assertIsNone(result.error)

if __name__ == '__main__':
    unittest.main()
