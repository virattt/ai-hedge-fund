"""
AI Hedge Fund Stock Screener

This module provides comprehensive stock screening functionality that leverages
all 10 AI agents to analyze and rank stocks by investment attractiveness.
Designed with Claude Sonnet 4 as the default model as requested.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional, List
import pandas as pd
import time
import requests
import os
import sys
from src.main import run_hedge_fund
from src.data.models import CompanyFactsResponse


def validate_api_keys(model_provider: str = "Anthropic") -> bool:
    """
    Simple validation that required API keys are present.
    
    Args:
        model_provider: The LLM provider being used
        
    Returns:
        True if all required keys present, False otherwise
    """
    missing_keys = []
    
    # Check financial data API key
    if not os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        missing_keys.append("FINANCIAL_DATASETS_API_KEY")
    
    # Check LLM API key based on provider
    llm_key_map = {
        "Anthropic": "ANTHROPIC_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Groq": "GROQ_API_KEY"
    }
    
    if model_provider in llm_key_map:
        key_name = llm_key_map[model_provider]
        if not os.environ.get(key_name):
            missing_keys.append(key_name)
    
    # Print results
    if missing_keys:
        print(f"❌ Missing required API keys: {', '.join(missing_keys)}")
        print(f"💡 Please add these to your .env file:")
        for key in missing_keys:
            print(f"   {key}=your_api_key_here")
        return False
    else:
        print(f"✅ API keys validated successfully")
        return True


def get_company_facts(ticker: str) -> Optional[object]:
    """
    Get company facts including sector and industry information.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Company facts object with sector, industry, market_cap attributes or None
    """
    try:
        headers = {}
        if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
            headers["X-API-KEY"] = api_key
        
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            response_model = CompanyFactsResponse(**data)
            return response_model.company_facts
        else:
            return None
    except Exception:
        return None


@dataclass
class ScreeningResult:
    """Results from screening a single stock"""
    ticker: str
    overall_score: float
    signal_counts: Dict[str, int]  # {'bullish': 6, 'neutral': 3, 'bearish': 1} - counts of agent signals
    agent_signals: Dict[str, Dict]  # Full agent analysis
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    error: Optional[str] = None


class StockScreener:
    """
    Main stock screening class that leverages all AI agents to analyze and rank stocks.
    Defaults to Claude Sonnet 4 as requested.
    """
    
    def __init__(self, 
                 start_date: str = None, 
                 end_date: str = None,
                 model_name: str = "claude-sonnet-4-20250514",  # Default to Claude Sonnet 4
                 model_provider: str = "Anthropic",              # Default to Anthropic
                 max_workers: int = 2,  # Conservative for API rate limits
                 show_reasoning: bool = False,
                 delay_between_stocks: int = 2):  # Delay in seconds between stock analyses
        """
        Initialize the stock screener with Claude Sonnet 4 as default.
        
        Args:
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD) 
            model_name: LLM model to use (defaults to Claude Sonnet 4)
            model_provider: LLM provider (defaults to Anthropic)
            max_workers: Number of parallel workers (keep low for API limits)
            show_reasoning: Whether to show detailed reasoning
            delay_between_stocks: Delay in seconds between stock analyses (default: 2)
        """
        # Validate API keys before proceeding
        if not validate_api_keys(model_provider):
            print(f"\n🚫 Cannot proceed without required API keys. Exiting...")
            sys.exit(1)
            
        self.end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        self.start_date = start_date or (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        self.model_name = model_name
        self.model_provider = model_provider
        self.max_workers = max_workers
        self.show_reasoning = show_reasoning
        self.delay_between_stocks = delay_between_stocks
        self.results: List[ScreeningResult] = []

    def get_sp500_sample(self) -> List[str]:
        """
        Get a representative sample of S&P 500 stocks across all sectors.
        Returns a diverse mix of large-cap stocks for screening.
        """
        return [
            # Technology (20 stocks)
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "ADBE", "CRM",
            "ORCL", "IBM", "INTC", "AMD", "QCOM", "AVGO", "TXN", "AMAT", "LRCX", "KLAC",
            
            # Healthcare (20 stocks)
            "JNJ", "PFE", "UNH", "ABBV", "TMO", "DHR", "BMY", "AMGN", "GILD", "VRTX",
            "REGN", "ISRG", "DXCM", "ILMN", "BIIB", "MRNA", "ZTS", "CVS", "CI", "HUM",
            
            # Financial Services (20 stocks)
            "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW", "USB",
            "PNC", "TFC", "COF", "BK", "STT", "NTRS", "RF", "CFG", "KEY", "FITB",
            
            # Consumer Discretionary (20 stocks)
            "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "MAR", "GM", "F",
            "APTV", "YUM", "CMG", "ORLY", "AZO", "ULTA", "RCL", "CCL", "EBAY", "ETSY",
            
            # Consumer Staples (15 stocks)
            "PG", "KO", "PEP", "WMT", "COST", "MDLZ", "CL", "KMB", "GIS", "K",
            "HSY", "MKC", "CPB", "CAG", "SJM",
            
            # Energy (15 stocks)
            "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "OXY", "BKR",
            "HAL", "DVN", "FANG", "EQT", "CTRA",
            
            # Industrials (20 stocks)
            "BA", "CAT", "HON", "UPS", "RTX", "LMT", "GE", "MMM", "DE", "UNP",
            "CSX", "NSC", "FDX", "WM", "EMR", "ETN", "PH", "CMI", "ITW", "GWW",
            
            # Materials (15 stocks)
            "LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF",
            "ALB", "CE", "VMC", "MLM", "PKG",
            
            # Real Estate (10 stocks)
            "AMT", "PLD", "CCI", "EQIX", "PSA", "WELL", "DLR", "O", "SBAC", "EXR",
            
            # Utilities (10 stocks)
            "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "ED",
            
            # Communication Services (10 stocks)
            "DIS", "CMCSA", "VZ", "T", "CHTR", "TMUS", "ATVI", "EA", "TTWO", "NWSA"
        ]
    
    def load_custom_tickers(self, file_path: str) -> List[str]:
        """
        Load ticker symbols from a CSV or text file.
        
        Args:
            file_path: Path to file containing ticker symbols
            
        Returns:
            List of ticker symbols
        """
        tickers = []
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                # Assume first column contains tickers
                tickers = df.iloc[:, 0].str.upper().str.strip().tolist()
            else:
                # Assume text file with one ticker per line
                with open(file_path, 'r') as f:
                    tickers = [line.strip().upper() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading tickers from {file_path}: {e}")
            return []
        
        # Filter valid tickers: non-empty, 1-5 chars, alphabetic only
        return [t for t in tickers if t and len(t) <= 5 and t.isalpha()]

    def analyze_single_stock(self, ticker: str) -> ScreeningResult:
        """
        Analyze a single stock using all AI agents.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            ScreeningResult with analysis data
        """
        try:
            print(f"📊 Analyzing {ticker} with Claude Sonnet 4...")
            
            # Create minimal portfolio for analysis
            portfolio = {
                "cash": 100000.0,
                "margin_requirement": 0.0,
                "margin_used": 0.0,
                "positions": {ticker: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}},
                "realized_gains": {ticker: {"long": 0.0, "short": 0.0}}
            }
            
            # Run analysis with all agents using Claude Sonnet 4
            result = run_hedge_fund(
                tickers=[ticker],
                start_date=self.start_date,
                end_date=self.end_date,
                portfolio=portfolio,
                show_reasoning=self.show_reasoning,
                selected_analysts=None,  # Use all analysts
                model_name=self.model_name,
                model_provider=self.model_provider,
            )
            
            # Extract agent signals
            agent_signals = result.get("analyst_signals", {})
            
            # Debug: Print the structure of agent_signals
            print(f"🔍 DEBUG - Agent signals structure for {ticker}:")
            for agent_name, agent_data in agent_signals.items():
                if ticker in agent_data:
                    ticker_data = agent_data[ticker]
                    signal = ticker_data.get("signal", "neutral")
                    print(f"  {agent_name}: {signal}")
                else:
                    print(f"  {agent_name}: Missing ticker data")
            
            # Count signal types
            signal_counts = {"bullish": 0, "neutral": 0, "bearish": 0}
            for agent_name, agent_data in agent_signals.items():
                if ticker in agent_data:
                    ticker_data = agent_data[ticker]
                    signal = ticker_data.get("signal", "neutral").lower()
                    if signal in signal_counts:
                        signal_counts[signal] += 1
                        print(f"  Counted {signal} from {agent_name}")
            
            print(f"🔍 DEBUG - Final signal counts: {signal_counts}")
            
            # Calculate overall score (bullish=1, neutral=0.5, bearish=0)
            total_agents = sum(signal_counts.values())
            if total_agents > 0:
                overall_score = (signal_counts["bullish"] + 0.5 * signal_counts["neutral"]) / total_agents
            else:
                overall_score = 0.5
            
            # Try to get company info
            market_cap = None
            sector = None
            industry = None
            try:
                company_facts = get_company_facts(ticker)
                if company_facts:
                    market_cap = getattr(company_facts, 'market_cap', None)
                    sector = getattr(company_facts, 'sector', None)
                    industry = getattr(company_facts, 'industry', None)
            except:
                pass  # Continue without company info
            
            return ScreeningResult(
                ticker=ticker,
                overall_score=overall_score,
                signal_counts=signal_counts,
                agent_signals=agent_signals,
                market_cap=market_cap,
                sector=sector,
                industry=industry
            )
            
        except Exception as e:
            print(f"❌ Error analyzing {ticker}: {str(e)}")
            return ScreeningResult(
                ticker=ticker,
                overall_score=0.0,
                signal_counts={"bullish": 0, "neutral": 0, "bearish": 0},
                agent_signals={},
                error=str(e)
            )
    
    def screen_stocks(self, tickers: List[str]) -> List[ScreeningResult]:
        """
        Screen multiple stocks using all AI agents with Claude Sonnet 4.
        
        Args:
            tickers: List of ticker symbols to analyze
            
        Returns:
            List of ScreeningResult objects sorted by overall score
        """
        print(f"\n🚀 Starting AI Hedge Fund Stock Screening")
        print(f"📈 Analyzing {len(tickers)} stocks")
        print(f"📅 Date range: {self.start_date} to {self.end_date}")
        print(f"🤖 Using Claude Sonnet 4 with all 10 AI agents")
        print(f"{'='*60}\n")
        
        results = []
        start_time = time.time()
        
        # Sequential processing to respect API rate limits
        for i, ticker in enumerate(tickers, 1):
            result = self.analyze_single_stock(ticker)
            results.append(result)
            
            # Progress update
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (len(tickers) - i) * avg_time
            
            print(f"Progress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%) | "
                  f"Elapsed: {elapsed/60:.1f}m | ETA: {remaining/60:.1f}m")
            
            # Delay to respect API rate limits and user preference
            if i < len(tickers):  # Don't delay after the last stock
                print(f"⏳ Waiting {self.delay_between_stocks} seconds before next analysis...")
                time.sleep(self.delay_between_stocks)
        
        # Sort by score (best first)
        results.sort(key=lambda x: x.overall_score, reverse=True)
        self.results = results
        
        print(f"\n✅ Screening completed in {(time.time()-start_time)/60:.1f} minutes!\n")
        return results
    
    def get_top_picks(self, n: int = 10, min_score: float = 0.6) -> List[ScreeningResult]:
        """
        Get top stock picks based on screening results.
        
        Args:
            n: Number of top picks to return
            min_score: Minimum overall score threshold
            
        Returns:
            List of top ScreeningResult objects
        """
        filtered_results = [r for r in self.results if r.overall_score >= min_score and not r.error]
        return filtered_results[:n]
    
    def save_results(self, filename: str = None):
        """
        Save screening results to CSV file.
        
        Args:
            filename: Output filename (auto-generated if None)
        """
        if not self.results:
            print("No results to save.")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ai_hedge_fund_screening_{timestamp}.csv"
        
        # Prepare data for CSV
        csv_data = []
        for i, result in enumerate(self.results, 1):
            row = {
                "rank": i,
                "ticker": result.ticker,
                "overall_score": round(result.overall_score, 3),
                "bullish_signals": result.signal_counts["bullish"],
                "neutral_signals": result.signal_counts["neutral"],
                "bearish_signals": result.signal_counts["bearish"],
                "market_cap": result.market_cap,
                "sector": result.sector,
                "industry": result.industry,
                "error": result.error
            }
            csv_data.append(row)
        
        # Save to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False)
        print(f"💾 Results saved to: {filename}")
    
    def print_results(self, top_n: int = 25):
        """
        Print a summary of screening results.
        
        Args:
            top_n: Number of top results to display
        """
        if not self.results:
            print("No results to display.")
            return
        
        print(f"\n{'='*80}")
        print(f"🏆 AI HEDGE FUND STOCK SCREENING RESULTS - TOP {top_n}")
        print(f"{'='*80}")
        print(f"📊 Analysis Period: {self.start_date} to {self.end_date}")
        print(f"📈 Total Stocks Analyzed: {len(self.results)}")
        print(f"🤖 Model Used: {self.model_name} ({self.model_provider})")
        
        # Summary statistics
        successful_results = [r for r in self.results if not r.error]
        if successful_results:
            avg_score = sum(r.overall_score for r in successful_results) / len(successful_results)
            print(f"📊 Average Score: {avg_score:.3f}")
            print(f"✅ Successful Analyses: {len(successful_results)}/{len(self.results)}")
        
        print(f"\n{'Rank':<4} | {'Ticker':<6} | {'Score':<5} | {'Bull':<4} | {'Neut':<4} | {'Bear':<4} | {'Sector':<15}")
        print("-" * 75)
        
        for i, result in enumerate(self.results[:top_n], 1):
            if result.error:
                print(f"{i:<4} | {result.ticker:<6} | ERROR | {result.error[:40]}")
                continue
            
            # Color coding for terminal output
            score_indicator = "🟢" if result.overall_score >= 0.7 else "🟡" if result.overall_score >= 0.5 else "🔴"
            
            print(f"{i:<4} | {result.ticker:<6} | {result.overall_score:.3f} | "
                  f"{result.signal_counts['bullish']:<4} | {result.signal_counts['neutral']:<4} | "
                  f"{result.signal_counts['bearish']:<4} | {(result.sector or 'Unknown')[:15]}")
        
        # Top picks summary
        top_picks = self.get_top_picks(10, 0.6)
        if top_picks:
            print(f"\n🎯 TOP INVESTMENT PICKS (Score ≥ 0.6):")
            for i, pick in enumerate(top_picks, 1):
                print(f"  {i}. {pick.ticker} - Score: {pick.overall_score:.3f} "
                      f"({pick.signal_counts['bullish']} bullish, {pick.signal_counts['neutral']} neutral, {pick.signal_counts['bearish']} bearish)")
        else:
            print(f"\n⚠️  No stocks met the minimum score threshold of 0.6")
