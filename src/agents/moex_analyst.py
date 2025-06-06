"""
MOEX/SPB Exchange analyst agent that specializes in Russian market analysis.
"""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
import pandas as pd
import logging
from datetime import datetime, timedelta

from src.data.moex import MOEXClient
from src.data.spb import SPBDataProvider
from src.analysis.technical import analyze_stock
from src.utils.llm import get_llm
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Russian market analyst specializing in MOEX and SPB Exchange stocks.
Your role is to analyze Russian stocks and provide trading recommendations based on:
1. Technical analysis
2. Market conditions
3. Geopolitical factors
4. Currency risks

For each stock, provide:
1. A clear BUY/SELL/HOLD recommendation
2. Confidence level (0-100%)
3. Key reasons for the recommendation
4. Risk factors to consider

Format your response as a JSON object with the following structure:
{
    "ticker": {
        "recommendation": "BUY/SELL/HOLD",
        "confidence": 85,
        "reasons": ["reason1", "reason2", ...],
        "risks": ["risk1", "risk2", ...],
        "technical_signals": {...}
    }
}
"""

def moex_analysis_agent(state: AgentState) -> AgentState:
    """
    Agent that analyzes Russian stocks from MOEX and SPB Exchange
    """
    llm = get_llm(state.metadata.get("model_name", "gpt-4"), state.metadata.get("model_provider", "OpenAI"))
    show_reasoning = state.metadata.get("show_reasoning", False)
    
    try:
        # Initialize clients
        moex_client = MOEXClient()
        spb_provider = None
        if 'TINKOFF_TOKEN' in state.metadata:
            spb_provider = SPBDataProvider('tinkoff', token=state.metadata['TINKOFF_TOKEN'])
        
        analysis_results = {}
        
        for ticker in state.data["tickers"]:
            try:
                # Determine if this is a MOEX or SPB stock
                is_moex = True  # Default to MOEX
                try:
                    # Try to get MOEX security info
                    security_info = moex_client.get_security_info(ticker)
                except:
                    is_moex = False
                
                # Get historical data
                if is_moex:
                    historical_data = moex_client.get_historical_data(
                        ticker,
                        start_date=datetime.strptime(state.data["start_date"], "%Y-%m-%d"),
                        end_date=datetime.strptime(state.data["end_date"], "%Y-%m-%d")
                    )
                elif spb_provider:
                    historical_data = spb_provider.get_historical_data(
                        ticker,
                        start_date=datetime.strptime(state.data["start_date"], "%Y-%m-%d"),
                        end_date=datetime.strptime(state.data["end_date"], "%Y-%m-%d")
                    )
                else:
                    logger.warning(f"Cannot analyze SPB stock {ticker} - no data provider configured")
                    continue
                
                # Perform technical analysis
                technical_analysis = analyze_stock(historical_data)
                
                # Get current market data
                if is_moex:
                    market_data = moex_client.get_market_data(ticker)
                    current_price = market_data['LAST'].iloc[0] if not market_data.empty else None
                else:
                    current_price = None  # Would need to implement for SPB
                
                # Prepare context for LLM
                context = {
                    "ticker": ticker,
                    "exchange": "MOEX" if is_moex else "SPB",
                    "current_price": current_price,
                    "technical_analysis": technical_analysis,
                    "historical_data_summary": {
                        "start_date": state.data["start_date"],
                        "end_date": state.data["end_date"],
                        "price_change": (
                            (historical_data['CLOSE'].iloc[-1] / historical_data['CLOSE'].iloc[0] - 1) * 100
                            if not historical_data.empty else None
                        )
                    }
                }
                
                # Format price change string
                price_change_str = (
                    f"{context['historical_data_summary']['price_change']:.2f}%"
                    if context['historical_data_summary']['price_change'] is not None
                    else 'N/A'
                )
                
                # Get LLM analysis
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=f"""
                    Analyze the following Russian stock and provide a trading recommendation:
                    
                    Ticker: {context['ticker']}
                    Exchange: {context['exchange']}
                    Current Price: {context['current_price']}
                    
                    Technical Analysis:
                    - Recommendation: {technical_analysis['recommendation']}
                    - Confidence: {technical_analysis['confidence']:.2%}
                    - Signals: {', '.join(s['reason'] for s in technical_analysis['signals'])}
                    
                    Historical Performance:
                    - Period: {context['historical_data_summary']['start_date']} to {context['historical_data_summary']['end_date']}
                    - Price Change: {price_change_str}
                    """)
                ]
                
                response = llm.invoke(messages)
                
                if show_reasoning:
                    logger.info(f"\nMOEX Analyst reasoning for {ticker}:")
                    logger.info(response.content)
                
                # Parse response and store results
                try:
                    analysis = eval(response.content)  # Safe since we control the LLM prompt
                    analysis_results[ticker] = analysis[ticker]
                    analysis_results[ticker]['technical_analysis'] = technical_analysis
                except Exception as e:
                    logger.error(f"Error parsing LLM response for {ticker}: {e}")
                    analysis_results[ticker] = {
                        "recommendation": technical_analysis['recommendation'],
                        "confidence": technical_analysis['confidence'],
                        "reasons": [s['reason'] for s in technical_analysis['signals']],
                        "risks": ["Analysis based on technical indicators only"],
                        "technical_analysis": technical_analysis
                    }
                
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                continue
        
        # Store results in state
        state.data["analyst_signals"]["moex_analyst"] = analysis_results
        
        return state
        
    except Exception as e:
        logger.error(f"MOEX analyst agent error: {e}")
        state.data["analyst_signals"]["moex_analyst"] = {}
        return state 