#!/usr/bin/env python3
"""
AI Hedge Fund Stock Screening CLI

Command-line interface for screening stocks using all 10 AI agents
with Claude Sonnet 4 as the default analysis engine.

Usage:
    python screen_stocks.py --sample sp500          # Screen S&P 500 sample
    python screen_stocks.py --tickers AAPL MSFT     # Screen specific tickers
    python screen_stocks.py --file tickers.txt      # Screen from file
    python screen_stocks.py --top 10                # Show top 10 results only
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import List

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.screening.stock_screener import StockScreener


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Hedge Fund Stock Screening System - Analyze stocks using all 10 AI agents with Claude Sonnet 4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --sample sp500                    # Screen S&P 500 sample (175 stocks)
  %(prog)s --tickers AAPL MSFT GOOGL        # Screen specific stocks
  %(prog)s --file my_tickers.txt             # Screen stocks from file
  %(prog)s --sample sp500 --top 10           # Show only top 10 results
  %(prog)s --start-date 2024-01-01           # Custom analysis period
  %(prog)s --show-reasoning                  # Show detailed AI reasoning
  %(prog)s --save results.csv                # Save results to custom file
  %(prog)s --delay 60                        # Wait 60 seconds between analyses
  %(prog)s --delay 120 --sample sp500        # 2-minute delay for rate limiting

The system uses Claude Sonnet 4 by default and analyzes stocks using all 10 AI agents:
Warren Buffett, Charlie Munger, Peter Lynch, Ray Dalio, George Soros, 
Benjamin Graham, Joel Greenblatt, Jim Simons, Ken Griffin, and David Tepper.
        """
    )
    
    # Stock selection (mutually exclusive)
    stock_group = parser.add_mutually_exclusive_group(required=True)
    stock_group.add_argument(
        '--sample',
        choices=['sp500'],
        help='Use predefined stock sample (sp500 = 175 major stocks across all sectors)'
    )
    stock_group.add_argument(
        '--tickers',
        nargs='+',
        metavar='TICKER',
        help='Specific stock tickers to analyze (e.g., AAPL MSFT GOOGL)'
    )
    stock_group.add_argument(
        '--file',
        metavar='FILE',
        help='File containing stock tickers (one per line or CSV)'
    )
    
    # Analysis parameters
    parser.add_argument(
        '--start-date',
        metavar='YYYY-MM-DD',
        help='Analysis start date (default: 90 days ago)'
    )
    parser.add_argument(
        '--end-date',
        metavar='YYYY-MM-DD',
        help='Analysis end date (default: today)'
    )
    parser.add_argument(
        '--model',
        default='claude-sonnet-4-20250514',
        help='LLM model to use (default: claude-sonnet-4-20250514)'
    )
    parser.add_argument(
        '--provider',
        default='Anthropic',
        help='LLM provider (default: Anthropic)'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=60,
        metavar='SECONDS',
        help='Delay in seconds between stock analyses (default: 60, use 60+ for rate limiting)'
    )
    
    # Output options
    parser.add_argument(
        '--top',
        type=int,
        metavar='N',
        help='Show only top N results (default: show all)'
    )
    parser.add_argument(
        '--min-score',
        type=float,
        default=0.0,
        metavar='SCORE',
        help='Minimum score threshold (0.0-1.0, default: 0.0)'
    )
    parser.add_argument(
        '--save',
        metavar='FILE',
        help='Save results to CSV file (auto-generated if not specified)'
    )
    parser.add_argument(
        '--show-reasoning',
        action='store_true',
        help='Show detailed AI agent reasoning (slower but more informative)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress output (only show final results)'
    )
    
    return parser.parse_args()


def validate_date(date_str: str) -> str:
    """Validate date format and return normalized string."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def load_tickers_from_file(file_path: str) -> List[str]:
    """Load ticker symbols from file."""
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    
    try:
        screener = StockScreener()
        tickers = screener.load_custom_tickers(file_path)
        if not tickers:
            print(f"❌ Error: No valid tickers found in {file_path}")
            sys.exit(1)
        return tickers
    except Exception as e:
        print(f"❌ Error loading tickers from {file_path}: {e}")
        sys.exit(1)


def main():
    """Main CLI function."""
    args = parse_arguments()
    
    # Validate dates if provided
    start_date = args.start_date
    end_date = args.end_date
    
    if start_date:
        start_date = validate_date(start_date)
    if end_date:
        end_date = validate_date(end_date)
    
    # Determine tickers to analyze
    if args.sample == 'sp500':
        screener = StockScreener()
        tickers = screener.get_sp500_sample()
        source_desc = "S&P 500 sample (175 stocks)"
    elif args.tickers:
        tickers = [t.upper().strip() for t in args.tickers]
        source_desc = f"Custom tickers: {', '.join(tickers)}"
    elif args.file:
        tickers = load_tickers_from_file(args.file)
        source_desc = f"File: {args.file} ({len(tickers)} tickers)"
    
    # Validate tickers
    if not tickers:
        print("❌ Error: No tickers to analyze")
        sys.exit(1)
    
    if len(tickers) > 500:
        print(f"⚠️  Warning: Analyzing {len(tickers)} stocks will take a very long time.")
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    # Initialize screener
    screener = StockScreener(
        start_date=start_date,
        end_date=end_date,
        model_name=args.model,
        model_provider=args.provider,
        show_reasoning=args.show_reasoning,
        delay_between_stocks=args.delay
    )
    
    # Display configuration
    if not args.quiet:
        print(f"\n🚀 AI HEDGE FUND STOCK SCREENING")
        print(f"{'='*50}")
        print(f"📊 Source: {source_desc}")
        print(f"📅 Period: {screener.start_date} to {screener.end_date}")
        print(f"🤖 Model: {args.model} ({args.provider})")
        print(f"🔍 Agents: All 10 AI investment experts")
        print(f"⏱️  Delay: {args.delay} seconds between stocks")
        
        # Calculate more accurate time estimation
        analysis_time_per_stock = 30  # seconds for AI analysis
        total_delay_time = (len(tickers) - 1) * args.delay  # delay between stocks
        total_analysis_time = len(tickers) * analysis_time_per_stock
        estimated_total_minutes = (total_analysis_time + total_delay_time) / 60
        
        print(f"⏱️  Estimated time: {estimated_total_minutes:.1f} minutes")
        
        if len(tickers) > 20:
            print(f"\n⚠️  This will analyze {len(tickers)} stocks - grab a coffee! ☕")
        
        print(f"\n{'='*50}")
        
        # Confirmation for large batches
        if len(tickers) > 50:
            response = input(f"\nProceed with analyzing {len(tickers)} stocks? (y/N): ")
            if response.lower() != 'y':
                print("Cancelled.")
                sys.exit(0)
    
    try:
        # Run the screening
        results = screener.screen_stocks(tickers)
        
        # Filter results if needed
        if args.min_score > 0:
            results = [r for r in results if r.overall_score >= args.min_score and not r.error]
            if not args.quiet:
                print(f"🔍 Filtered to {len(results)} stocks with score ≥ {args.min_score}")
        
        # Limit results if requested
        display_results = results
        if args.top:
            display_results = results[:args.top]
        
        # Display results
        if not args.quiet:
            screener.print_results(len(display_results))
        else:
            # Quiet mode - just show top picks
            top_picks = screener.get_top_picks(min(10, len(results)), 0.6)
            if top_picks:
                print(f"\n🎯 TOP INVESTMENT PICKS:")
                for i, pick in enumerate(top_picks, 1):
                    print(f"  {i}. {pick.ticker} - Score: {pick.overall_score:.3f}")
            else:
                print(f"\n⚠️  No stocks met minimum score threshold")
        
        # Save results if requested
        if args.save or len(results) > 10:  # Auto-save for large batches
            filename = args.save
            screener.save_results(filename)
        
        # Summary
        successful = len([r for r in results if not r.error])
        if not args.quiet:
            print(f"\n✅ Analysis complete!")
            print(f"📊 Successfully analyzed: {successful}/{len(tickers)} stocks")
            if successful > 0:
                avg_score = sum(r.overall_score for r in results if not r.error) / successful
                print(f"📈 Average score: {avg_score:.3f}")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Analysis interrupted by user")
        if screener.results:
            print(f"📊 Partial results available for {len(screener.results)} stocks")
            save_partial = input("Save partial results? (y/N): ")
            if save_partial.lower() == 'y':
                screener.save_results("partial_screening_results.csv")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
