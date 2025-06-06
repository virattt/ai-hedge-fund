"""
Example script demonstrating MOEX/SPB stock analysis functionality.
"""

import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

from src.data.moex import MOEXClient
from src.data.spb import SPBDataProvider
from src.analysis.technical import analyze_stock

# Load environment variables
load_dotenv()

def analyze_moex_stock(ticker: str):
    """Analyze a MOEX stock."""
    print(f"\nAnalyzing MOEX stock: {ticker}")
    
    # Initialize MOEX client
    client = MOEXClient()
    
    try:
        # Get security info
        info = client.get_security_info(ticker)
        print("\nSecurity Info:")
        for key, value in info.items():
            print(f"{key}: {value}")
        
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=100)
        
        historical_data = client.get_historical_data(ticker, start_date, end_date)
        print(f"\nHistorical Data Shape: {historical_data.shape}")
        
        # Get current market data
        market_data = client.get_market_data(ticker)
        if not market_data.empty:
            print("\nCurrent Market Data:")
            print(market_data.iloc[0])
        
        # Perform technical analysis
        analysis = analyze_stock(historical_data)
        
        print("\nTechnical Analysis Results:")
        print(f"Recommendation: {analysis['recommendation']}")
        print(f"Confidence: {analysis['confidence']:.2%}")
        
        print("\nTrend Analysis:")
        print(f"Short-term: {analysis['trend']['short_term']}")
        print(f"Medium-term: {analysis['trend']['medium_term']}")
        print(f"Long-term: {analysis['trend']['long_term']}")
        
        print("\nMomentum Analysis:")
        print(f"RSI: {analysis['momentum']['rsi']['value']:.2f} ({analysis['momentum']['rsi']['signal']})")
        print(f"Stochastic: %K={analysis['momentum']['stochastic']['k']:.2f}, %D={analysis['momentum']['stochastic']['d']:.2f}")
        
        print("\nVolatility Analysis:")
        print(f"State: {analysis['volatility']['state']}")
        print(f"Bollinger Bandwidth: {analysis['volatility']['bandwidth']:.2%}")
        
        print("\nTrading Signals:")
        for signal in analysis['signals']:
            print(f"- {signal['type']}: {signal['signal']} ({signal['reason']}, strength: {signal['strength']:.2%})")
            
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")

def analyze_spb_stock(ticker: str):
    """Analyze an SPB Exchange stock."""
    print(f"\nAnalyzing SPB stock: {ticker}")
    
    # Check for Tinkoff token
    tinkoff_token = os.getenv('TINKOFF_TOKEN')
    if not tinkoff_token:
        print("Error: TINKOFF_TOKEN environment variable not set")
        return
    
    # Initialize SPB data provider
    provider = SPBDataProvider('tinkoff', token=tinkoff_token)
    
    try:
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=100)
        
        historical_data = provider.get_historical_data(ticker, start_date, end_date)
        print(f"\nHistorical Data Shape: {historical_data.shape}")
        
        # Get current market data
        market_data = provider.get_market_data(ticker)
        if market_data:
            print("\nCurrent Market Data:")
            print(market_data)
        
        # Perform technical analysis
        analysis = analyze_stock(historical_data)
        
        print("\nTechnical Analysis Results:")
        print(f"Recommendation: {analysis['recommendation']}")
        print(f"Confidence: {analysis['confidence']:.2%}")
        
        print("\nTrend Analysis:")
        print(f"Short-term: {analysis['trend']['short_term']}")
        print(f"Medium-term: {analysis['trend']['medium_term']}")
        print(f"Long-term: {analysis['trend']['long_term']}")
        
        print("\nMomentum Analysis:")
        print(f"RSI: {analysis['momentum']['rsi']['value']:.2f} ({analysis['momentum']['rsi']['signal']})")
        print(f"Stochastic: %K={analysis['momentum']['stochastic']['k']:.2f}, %D={analysis['momentum']['stochastic']['d']:.2f}")
        
        print("\nVolatility Analysis:")
        print(f"State: {analysis['volatility']['state']}")
        print(f"Bollinger Bandwidth: {analysis['volatility']['bandwidth']:.2%}")
        
        print("\nTrading Signals:")
        for signal in analysis['signals']:
            print(f"- {signal['type']}: {signal['signal']} ({signal['reason']}, strength: {signal['strength']:.2%})")
            
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")

if __name__ == "__main__":
    # Example usage
    print("MOEX/SPB Stock Analysis Example")
    print("===============================")
    
    # Analyze MOEX stocks
    moex_tickers = ['SBER', 'GAZP', 'LKOH']
    for ticker in moex_tickers:
        analyze_moex_stock(ticker)
    
    # Analyze SPB stocks (requires Tinkoff token)
    spb_tickers = ['AAPL', 'MSFT', 'GOOGL']
    for ticker in spb_tickers:
        analyze_spb_stock(ticker) 