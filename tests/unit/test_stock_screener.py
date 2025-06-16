"""
Unit tests for StockScreener class

Tests all functionality of the stock screening system including:
- Initialization and configuration
- Date handling
- Ticker sources (S&P 500 sample, custom files)
- Single stock analysis
- Batch screening
- Result processing and scoring
- Error handling
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import tempfile
import os
from datetime import datetime, timedelta
import sys

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.screening.stock_screener import StockScreener, ScreeningResult


class TestStockScreener(unittest.TestCase):
    """Test cases for StockScreener class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.screener = StockScreener()
        self.sample_agent_signals = {
            "warren_buffett": {"signal": "bullish", "reasoning": "Strong fundamentals"},
            "charlie_munger": {"signal": "bullish", "reasoning": "Great management"},
            "peter_lynch": {"signal": "neutral", "reasoning": "Fair valuation"},
            "ray_dalio": {"signal": "bearish", "reasoning": "Economic headwinds"},
            "george_soros": {"signal": "bullish", "reasoning": "Market momentum"},
            "benjamin_graham": {"signal": "neutral", "reasoning": "Adequate margin of safety"},
            "joel_greenblatt": {"signal": "bullish", "reasoning": "High ROIC"},
            "jim_simons": {"signal": "bullish", "reasoning": "Positive technical signals"},
            "ken_griffin": {"signal": "neutral", "reasoning": "Mixed indicators"},
            "david_tepper": {"signal": "bullish", "reasoning": "Undervalued opportunity"}
        }
    
    def test_initialization_defaults(self):
        """Test StockScreener initializes with correct defaults."""
        screener = StockScreener()
        
        # Test default model configuration
        self.assertEqual(screener.model_name, "claude-sonnet-4-20250514")
        self.assertEqual(screener.model_provider, "Anthropic")

        # Test default date configuration (90 days)
        expected_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        expected_end = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(screener.start_date, expected_start)
        self.assertEqual(screener.end_date, expected_end)
        
        # Test other defaults
        self.assertEqual(screener.max_workers, 2)
        self.assertFalse(screener.show_reasoning)
        self.assertEqual(screener.results, [])
    
    def test_initialization_custom_parameters(self):
        """Test StockScreener initializes with custom parameters."""
        custom_start = "2024-01-01"
        custom_end = "2024-12-31"
        custom_model = "gpt-4"
        custom_provider = "OpenAI"
        
        screener = StockScreener(
            start_date=custom_start,
            end_date=custom_end,
            model_name=custom_model,
            model_provider=custom_provider,
            max_workers=4,
            show_reasoning=True
        )
        
        self.assertEqual(screener.start_date, custom_start)
        self.assertEqual(screener.end_date, custom_end)
        self.assertEqual(screener.model_name, custom_model)
        self.assertEqual(screener.model_provider, custom_provider)
        self.assertEqual(screener.max_workers, 4)
        self.assertTrue(screener.show_reasoning)
    
    def test_get_sp500_sample(self):
        """Test S&P 500 sample ticker generation."""
        tickers = self.screener.get_sp500_sample()
        
        # Test basic properties
        self.assertIsInstance(tickers, list)
        self.assertGreater(len(tickers), 100)  # Should have substantial number of stocks
        
        # Test all tickers are strings and uppercase
        for ticker in tickers:
            self.assertIsInstance(ticker, str)
            self.assertEqual(ticker, ticker.upper())
            self.assertLessEqual(len(ticker), 5)  # Valid ticker length
        
        # Test no duplicates
        self.assertEqual(len(tickers), len(set(tickers)))
        
        # Test contains major stocks
        major_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        for stock in major_stocks:
            self.assertIn(stock, tickers)
    
    def test_load_custom_tickers_text_file(self):
        """Test loading tickers from text file."""
        test_tickers = ["AAPL", "MSFT", "GOOGL", "amzn", "  tsla  ", ""]
        expected_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for ticker in test_tickers:
                f.write(f"{ticker}\n")
            temp_file = f.name
        
        try:
            result = self.screener.load_custom_tickers(temp_file)
            self.assertEqual(result, expected_tickers)
        finally:
            os.unlink(temp_file)
    
    def test_load_custom_tickers_csv_file(self):
        """Test loading tickers from CSV file."""
        csv_content = "ticker,name\nAAPL,Apple Inc\nMSFT,Microsoft\nGOOGL,Alphabet"
        expected_tickers = ["AAPL", "MSFT", "GOOGL"]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            result = self.screener.load_custom_tickers(temp_file)
            self.assertEqual(result, expected_tickers)
        finally:
            os.unlink(temp_file)
    
    def test_load_custom_tickers_invalid_file(self):
        """Test loading tickers from non-existent file."""
        result = self.screener.load_custom_tickers("nonexistent_file.txt")
        self.assertEqual(result, [])
    
    def test_load_custom_tickers_filters_invalid(self):
        """Test that invalid tickers are filtered out."""
        test_tickers = ["AAPL", "TOOLONG", "", "123", "MSFT"]
        expected_tickers = ["AAPL", "MSFT"]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for ticker in test_tickers:
                f.write(f"{ticker}\n")
            temp_file = f.name
        
        try:
            result = self.screener.load_custom_tickers(temp_file)
            self.assertEqual(result, expected_tickers)
        finally:
            os.unlink(temp_file)
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    @patch('src.screening.stock_screener.get_company_facts')
    def test_analyze_single_stock_success(self, mock_get_facts, mock_run_hedge_fund):
        """Test successful single stock analysis."""
        # Mock the hedge fund analysis
        mock_run_hedge_fund.return_value = {
            "analyst_signals": self.sample_agent_signals
        }
        
        # Mock company facts
        mock_company = MagicMock()
        mock_company.market_cap = 2500000000000  # $2.5T
        mock_company.sector = "Technology"
        mock_company.industry = "Consumer Electronics"
        mock_get_facts.return_value = mock_company
        
        result = self.screener.analyze_single_stock("AAPL")
        
        # Test result structure
        self.assertIsInstance(result, ScreeningResult)
        self.assertEqual(result.ticker, "AAPL")
        self.assertIsNone(result.error)
        
        # Test signal counting (6 bullish, 3 neutral, 1 bearish)
        expected_counts = {"bullish": 6, "neutral": 3, "bearish": 1}
        self.assertEqual(result.signal_counts, expected_counts)
        
        # Test score calculation: (6 + 0.5*3) / 10 = 0.75
        expected_score = 0.75
        self.assertEqual(result.overall_score, expected_score)
        
        # Test company info
        self.assertEqual(result.market_cap, 2500000000000)
        self.assertEqual(result.sector, "Technology")
        self.assertEqual(result.industry, "Consumer Electronics")
        
        # Test agent signals preserved
        self.assertEqual(result.agent_signals, self.sample_agent_signals)
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_analyze_single_stock_error_handling(self, mock_run_hedge_fund):
        """Test error handling in single stock analysis."""
        # Mock an exception
        mock_run_hedge_fund.side_effect = Exception("API Error")
        
        result = self.screener.analyze_single_stock("INVALID")
        
        # Test error result
        self.assertIsInstance(result, ScreeningResult)
        self.assertEqual(result.ticker, "INVALID")
        self.assertEqual(result.overall_score, 0.0)
        self.assertEqual(result.signal_counts, {"bullish": 0, "neutral": 0, "bearish": 0})
        self.assertEqual(result.agent_signals, {})
        self.assertEqual(result.error, "API Error")
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_analyze_single_stock_no_signals(self, mock_run_hedge_fund):
        """Test analysis with no agent signals."""
        mock_run_hedge_fund.return_value = {"analyst_signals": {}}
        
        result = self.screener.analyze_single_stock("TEST")
        
        # Test default score when no signals
        self.assertEqual(result.overall_score, 0.5)
        self.assertEqual(result.signal_counts, {"bullish": 0, "neutral": 0, "bearish": 0})
    
    @patch('src.screening.stock_screener.StockScreener.analyze_single_stock')
    def test_screen_stocks_batch_processing(self, mock_analyze):
        """Test batch stock screening."""
        # Mock individual stock analysis
        def mock_analysis(ticker):
            scores = {"AAPL": 0.8, "MSFT": 0.7, "GOOGL": 0.6}
            return ScreeningResult(
                ticker=ticker,
                overall_score=scores.get(ticker, 0.5),
                signal_counts={"bullish": 5, "neutral": 3, "bearish": 2},
                agent_signals={}
            )
        
        mock_analyze.side_effect = mock_analysis
        
        tickers = ["AAPL", "MSFT", "GOOGL"]
        results = self.screener.screen_stocks(tickers)
        
        # Test results are sorted by score (highest first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].ticker, "AAPL")
        self.assertEqual(results[0].overall_score, 0.8)
        self.assertEqual(results[1].ticker, "MSFT")
        self.assertEqual(results[1].overall_score, 0.7)
        self.assertEqual(results[2].ticker, "GOOGL")
        self.assertEqual(results[2].overall_score, 0.6)
        
        # Test results stored in screener
        self.assertEqual(self.screener.results, results)
    
    def test_get_top_picks(self):
        """Test getting top stock picks with filtering."""
        # Set up mock results
        self.screener.results = [
            ScreeningResult("AAPL", 0.8, {}, {}),
            ScreeningResult("MSFT", 0.7, {}, {}),
            ScreeningResult("GOOGL", 0.6, {}, {}),
            ScreeningResult("AMZN", 0.5, {}, {}),
            ScreeningResult("TSLA", 0.4, {}, {}),
            ScreeningResult("ERROR", 0.0, {}, {}, error="Failed")
        ]
        
        # Test top picks with minimum score
        top_picks = self.screener.get_top_picks(n=3, min_score=0.6)
        
        self.assertEqual(len(top_picks), 3)
        self.assertEqual(top_picks[0].ticker, "AAPL")
        self.assertEqual(top_picks[1].ticker, "MSFT")
        self.assertEqual(top_picks[2].ticker, "GOOGL")
        
        # Test filtering out errors and low scores
        for pick in top_picks:
            self.assertIsNone(pick.error)
            self.assertGreaterEqual(pick.overall_score, 0.6)
    
    def test_get_top_picks_empty_results(self):
        """Test getting top picks with no results."""
        self.screener.results = []
        top_picks = self.screener.get_top_picks()
        self.assertEqual(top_picks, [])
    
    @patch('pandas.DataFrame.to_csv')
    def test_save_results(self, mock_to_csv):
        """Test saving results to CSV."""
        # Set up mock results
        self.screener.results = [
            ScreeningResult(
                ticker="AAPL",
                overall_score=0.8,
                signal_counts={"bullish": 6, "neutral": 3, "bearish": 1},
                agent_signals={},
                market_cap=2500000000000,
                sector="Technology",
                industry="Consumer Electronics"
            )
        ]
        
        # Test save with custom filename
        self.screener.save_results("test_results.csv")
        mock_to_csv.assert_called_once_with("test_results.csv", index=False)
        
        # Test auto-generated filename
        mock_to_csv.reset_mock()
        self.screener.save_results()
        
        # Should be called with auto-generated filename
        self.assertTrue(mock_to_csv.called)
        call_args = mock_to_csv.call_args[0]
        self.assertTrue(call_args[0].startswith("ai_hedge_fund_screening_"))
        self.assertTrue(call_args[0].endswith(".csv"))
    
    def test_save_results_no_results(self):
        """Test saving when no results exist."""
        self.screener.results = []
        
        # Should not raise exception
        self.screener.save_results("test.csv")
    
    def test_print_results_no_results(self):
        """Test printing when no results exist."""
        self.screener.results = []
        
        # Should not raise exception
        self.screener.print_results()
    
    def test_screening_result_dataclass(self):
        """Test ScreeningResult dataclass functionality."""
        result = ScreeningResult(
            ticker="TEST",
            overall_score=0.75,
            signal_counts={"bullish": 6, "neutral": 2, "bearish": 2},
            agent_signals={"agent1": {"signal": "bullish"}},
            market_cap=1000000000,
            sector="Technology",
            industry="Software",
            error=None
        )
        
        # Test all fields accessible
        self.assertEqual(result.ticker, "TEST")
        self.assertEqual(result.overall_score, 0.75)
        self.assertEqual(result.signal_counts["bullish"], 6)
        self.assertEqual(result.agent_signals["agent1"]["signal"], "bullish")
        self.assertEqual(result.market_cap, 1000000000)
        self.assertEqual(result.sector, "Technology")
        self.assertEqual(result.industry, "Software")
        self.assertIsNone(result.error)
    
    def test_screening_result_with_error(self):
        """Test ScreeningResult with error condition."""
        result = ScreeningResult(
            ticker="ERROR",
            overall_score=0.0,
            signal_counts={"bullish": 0, "neutral": 0, "bearish": 0},
            agent_signals={},
            error="Analysis failed"
        )
        
        self.assertEqual(result.error, "Analysis failed")
        self.assertEqual(result.overall_score, 0.0)
        self.assertIsNone(result.market_cap)
        self.assertIsNone(result.sector)
        self.assertIsNone(result.industry)


if __name__ == '__main__':
    unittest.main()
