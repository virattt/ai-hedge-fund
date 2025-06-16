"""
Integration tests for AI Hedge Fund Stock Screening System

Tests the complete end-to-end workflow including:
- Integration with existing hedge fund infrastructure
- Real API calls (mocked for testing)
- Complete screening pipeline
- Result processing and output
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.screening.stock_screener import StockScreener, ScreeningResult


class TestEndToEndScreening(unittest.TestCase):
    """Integration tests for complete screening workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.screener = StockScreener(
            start_date="2024-01-01",
            end_date="2024-12-31",
            show_reasoning=False
        )
        
        # Mock comprehensive agent signals for realistic testing
        self.mock_agent_signals = {
            "warren_buffett": {
                "signal": "bullish",
                "reasoning": "Strong competitive moat and consistent earnings growth",
                "confidence": 0.85
            },
            "charlie_munger": {
                "signal": "bullish", 
                "reasoning": "Excellent management team with long-term vision",
                "confidence": 0.80
            },
            "peter_lynch": {
                "signal": "neutral",
                "reasoning": "Fair valuation but limited growth catalysts",
                "confidence": 0.70
            },
            "ray_dalio": {
                "signal": "bearish",
                "reasoning": "Macroeconomic headwinds affecting sector",
                "confidence": 0.75
            },
            "george_soros": {
                "signal": "bullish",
                "reasoning": "Strong momentum and institutional buying",
                "confidence": 0.90
            },
            "benjamin_graham": {
                "signal": "neutral",
                "reasoning": "Adequate margin of safety but not deeply undervalued",
                "confidence": 0.65
            },
            "joel_greenblatt": {
                "signal": "bullish",
                "reasoning": "High return on invested capital and earnings yield",
                "confidence": 0.88
            },
            "jim_simons": {
                "signal": "bullish",
                "reasoning": "Positive technical indicators and price momentum",
                "confidence": 0.82
            },
            "ken_griffin": {
                "signal": "neutral",
                "reasoning": "Mixed signals from quantitative models",
                "confidence": 0.60
            },
            "david_tepper": {
                "signal": "bullish",
                "reasoning": "Undervalued relative to distressed asset opportunities",
                "confidence": 0.78
            }
        }
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    @patch('src.screening.stock_screener.get_company_facts')
    def test_complete_screening_workflow(self, mock_get_facts, mock_run_hedge_fund):
        """Test complete end-to-end screening workflow."""
        
        # Mock hedge fund analysis with realistic data
        def mock_hedge_fund_analysis(tickers, **kwargs):
            # Verify correct parameters passed
            self.assertEqual(kwargs['start_date'], "2024-01-01")
            self.assertEqual(kwargs['end_date'], "2024-12-31")
            self.assertEqual(kwargs['model_name'], "claude-sonnet-4-20250514")
            self.assertEqual(kwargs['model_provider'], "Anthropic")
            self.assertIsNone(kwargs['selected_analysts'])  # Should use all analysts
            
            return {
                "analyst_signals": self.mock_agent_signals,
                "portfolio": kwargs['portfolio'],
                "performance_metrics": {
                    "total_return": 0.15,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": -0.08
                }
            }
        
        mock_run_hedge_fund.side_effect = mock_hedge_fund_analysis
        
        # Mock company facts with realistic data
        def mock_company_facts(ticker):
            company_data = {
                "AAPL": {
                    "market_cap": 2800000000000,  # $2.8T
                    "sector": "Technology",
                    "industry": "Consumer Electronics"
                },
                "MSFT": {
                    "market_cap": 2500000000000,  # $2.5T
                    "sector": "Technology", 
                    "industry": "Software"
                },
                "GOOGL": {
                    "market_cap": 1600000000000,  # $1.6T
                    "sector": "Communication Services",
                    "industry": "Internet Content & Information"
                }
            }
            
            if ticker in company_data:
                mock_company = MagicMock()
                mock_company.market_cap = company_data[ticker]["market_cap"]
                mock_company.sector = company_data[ticker]["sector"]
                mock_company.industry = company_data[ticker]["industry"]
                return mock_company
            return None
        
        mock_get_facts.side_effect = mock_company_facts
        
        # Test screening multiple stocks
        test_tickers = ["AAPL", "MSFT", "GOOGL"]
        results = self.screener.screen_stocks(test_tickers)
        
        # Verify results structure
        self.assertEqual(len(results), 3)
        self.assertIsInstance(results, list)
        
        # Verify all results are ScreeningResult objects
        for result in results:
            self.assertIsInstance(result, ScreeningResult)
            self.assertIn(result.ticker, test_tickers)
            self.assertIsNone(result.error)
        
        # Verify signal counting (6 bullish, 3 neutral, 1 bearish)
        expected_signal_counts = {"bullish": 6, "neutral": 3, "bearish": 1}
        for result in results:
            self.assertEqual(result.signal_counts, expected_signal_counts)
        
        # Verify score calculation: (6 + 0.5*3) / 10 = 0.75
        expected_score = 0.75
        for result in results:
            self.assertEqual(result.overall_score, expected_score)
        
        # Verify results are sorted by score (all equal in this case)
        scores = [r.overall_score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Verify company information is populated
        aapl_result = next(r for r in results if r.ticker == "AAPL")
        self.assertEqual(aapl_result.market_cap, 2800000000000)
        self.assertEqual(aapl_result.sector, "Technology")
        self.assertEqual(aapl_result.industry, "Consumer Electronics")
        
        # Verify agent signals are preserved
        for result in results:
            self.assertEqual(result.agent_signals, self.mock_agent_signals)
        
        # Verify screener state is updated
        self.assertEqual(self.screener.results, results)
        
        # Verify hedge fund was called correctly for each ticker
        self.assertEqual(mock_run_hedge_fund.call_count, 3)
        
        # Verify company facts was called for each ticker
        self.assertEqual(mock_get_facts.call_count, 3)
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_error_handling_in_workflow(self, mock_run_hedge_fund):
        """Test error handling during screening workflow."""
        
        # Mock mixed success/failure scenario
        def mock_hedge_fund_with_errors(tickers, **kwargs):
            ticker = tickers[0]
            if ticker == "FAIL":
                raise Exception("API rate limit exceeded")
            elif ticker == "TIMEOUT":
                raise TimeoutError("Request timeout")
            else:
                return {"analyst_signals": self.mock_agent_signals}
        
        mock_run_hedge_fund.side_effect = mock_hedge_fund_with_errors
        
        # Test screening with some failures
        test_tickers = ["AAPL", "FAIL", "MSFT", "TIMEOUT"]
        results = self.screener.screen_stocks(test_tickers)
        
        # Verify all tickers processed (with errors recorded)
        self.assertEqual(len(results), 4)
        
        # Verify successful results
        successful_results = [r for r in results if not r.error]
        self.assertEqual(len(successful_results), 2)
        
        for result in successful_results:
            self.assertIn(result.ticker, ["AAPL", "MSFT"])
            self.assertEqual(result.overall_score, 0.75)
        
        # Verify error results
        error_results = [r for r in results if r.error]
        self.assertEqual(len(error_results), 2)
        
        fail_result = next(r for r in error_results if r.ticker == "FAIL")
        self.assertEqual(fail_result.overall_score, 0.0)
        self.assertEqual(fail_result.error, "API rate limit exceeded")
        
        timeout_result = next(r for r in error_results if r.ticker == "TIMEOUT")
        self.assertEqual(timeout_result.overall_score, 0.0)
        self.assertEqual(timeout_result.error, "Request timeout")
    
    def test_sp500_sample_integration(self):
        """Test integration with S&P 500 sample data."""
        tickers = self.screener.get_sp500_sample()
        
        # Verify sample size and diversity
        self.assertGreater(len(tickers), 150)  # Should have substantial coverage
        self.assertLess(len(tickers), 200)     # But not too many for testing
        
        # Verify sector diversity by checking for major sector representatives
        tech_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        finance_stocks = ["JPM", "BAC", "WFC", "GS"]
        healthcare_stocks = ["JNJ", "PFE", "UNH", "ABBV"]
        
        for stock_list in [tech_stocks, finance_stocks, healthcare_stocks]:
            found_stocks = [s for s in stock_list if s in tickers]
            self.assertGreater(len(found_stocks), 0, f"No stocks found from {stock_list}")
    
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_top_picks_filtering(self, mock_run_hedge_fund):
        """Test top picks filtering and ranking."""
        
        # Mock different scores for different stocks
        def mock_varied_signals(tickers, **kwargs):
            ticker = tickers[0]
            signal_variations = {
                "HIGH": {"bullish": 8, "neutral": 2, "bearish": 0},    # Score: 0.9
                "MED": {"bullish": 5, "neutral": 3, "bearish": 2},     # Score: 0.65
                "LOW": {"bullish": 2, "neutral": 3, "bearish": 5},     # Score: 0.35
                "ZERO": {"bullish": 0, "neutral": 0, "bearish": 10}    # Score: 0.0
            }
            
            if ticker in signal_variations:
                # Create agent signals based on the variation
                agent_signals = {}
                counts = signal_variations[ticker]
                signal_types = (["bullish"] * counts["bullish"] + 
                              ["neutral"] * counts["neutral"] + 
                              ["bearish"] * counts["bearish"])
                
                agent_names = list(self.mock_agent_signals.keys())
                for i, signal_type in enumerate(signal_types):
                    if i < len(agent_names):
                        agent_signals[agent_names[i]] = {
                            "signal": signal_type,
                            "reasoning": f"Test {signal_type} signal"
                        }
                
                return {"analyst_signals": agent_signals}
            else:
                return {"analyst_signals": self.mock_agent_signals}
        
        mock_run_hedge_fund.side_effect = mock_varied_signals
        
        # Screen stocks with varied performance
        test_tickers = ["HIGH", "MED", "LOW", "ZERO"]
        results = self.screener.screen_stocks(test_tickers)
        
        # Verify results are sorted by score
        self.assertEqual(results[0].ticker, "HIGH")
        self.assertEqual(results[1].ticker, "MED") 
        self.assertEqual(results[2].ticker, "LOW")
        self.assertEqual(results[3].ticker, "ZERO")
        
        # Test top picks filtering
        top_picks = self.screener.get_top_picks(n=2, min_score=0.6)
        self.assertEqual(len(top_picks), 2)
        self.assertEqual(top_picks[0].ticker, "HIGH")
        self.assertEqual(top_picks[1].ticker, "MED")
        
        # Verify scores
        self.assertGreaterEqual(top_picks[0].overall_score, 0.8)
        self.assertGreaterEqual(top_picks[1].overall_score, 0.6)
    
    @patch('pandas.DataFrame.to_csv')
    @patch('src.screening.stock_screener.run_hedge_fund')
    def test_results_export_integration(self, mock_run_hedge_fund, mock_to_csv):
        """Test results export functionality."""
        
        # Mock successful analysis
        mock_run_hedge_fund.return_value = {
            "analyst_signals": self.mock_agent_signals
        }
        
        # Screen some stocks
        test_tickers = ["AAPL", "MSFT"]
        results = self.screener.screen_stocks(test_tickers)
        
        # Test CSV export
        self.screener.save_results("integration_test_results.csv")
        
        # Verify CSV export was called
        mock_to_csv.assert_called_once_with("integration_test_results.csv", index=False)
        
        # Verify data structure passed to CSV
        call_args = mock_to_csv.call_args
        df_data = call_args[1] if len(call_args) > 1 else {}
        
        # The DataFrame should have been created with proper structure
        self.assertTrue(mock_to_csv.called)
    
    def test_configuration_parameter_passing(self):
        """Test that configuration parameters are properly passed through."""
        
        # Test custom configuration
        custom_screener = StockScreener(
            start_date="2023-06-01",
            end_date="2023-12-31", 
            model_name="custom-model",
            model_provider="CustomProvider",
            show_reasoning=True
        )
        
        # Verify configuration
        self.assertEqual(custom_screener.start_date, "2023-06-01")
        self.assertEqual(custom_screener.end_date, "2023-12-31")
        self.assertEqual(custom_screener.model_name, "custom-model")
        self.assertEqual(custom_screener.model_provider, "CustomProvider")
        self.assertTrue(custom_screener.show_reasoning)
    
    def test_date_validation_integration(self):
        """Test date handling in integration context."""
        
        # Test with various date formats and edge cases
        today = datetime.now().strftime("%Y-%m-%d")
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # Default dates
        default_screener = StockScreener()
        self.assertEqual(default_screener.end_date, today)
        self.assertEqual(default_screener.start_date, ninety_days_ago)
        
        # Custom dates
        custom_screener = StockScreener(
            start_date="2024-01-01",
            end_date="2024-06-30"
        )
        self.assertEqual(custom_screener.start_date, "2024-01-01")
        self.assertEqual(custom_screener.end_date, "2024-06-30")


if __name__ == '__main__':
    unittest.main() 