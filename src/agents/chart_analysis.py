from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
import json
import base64
from typing import List

from tools.chart_api import get_trading_chart
from data.models import EntrySignal, EntrySignalResponse
from utils.llm import call_llm


##### Chart Analysis Agent #####
def chart_analysis_agent(state: AgentState):
    """Analyzes trading charts using vision models to identify entry signals based on technical patterns."""
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    
    # Add debug logging
    print(f"Debug: Analyzing charts for tickers: {tickers}")
    print(f"Debug: Using end date: {end_date}")
    
    model_name = state.get("metadata", {}).get("model_name", "gpt-4o")
    model_provider = state.get("metadata", {}).get("model_provider", "OpenAI")

    # Initialize entry signals analysis for each ticker
    entry_signals_analysis = {}

    for ticker in tickers:
        print(f"Debug: Processing ticker {ticker}")
        progress.update_status("chart_analysis_agent", ticker, "Fetching trading chart")

        # Get the trading chart
        try:
            trading_chart = get_trading_chart(
                ticker=ticker,
                end_date=end_date,
                timeframe="1D",  # Daily timeframe
                indicators=["ema(20)", "ema(50)", "rsi", "macd", "volume"],
            )
            print(f"Debug: Successfully fetched chart for {ticker}")
            
            progress.update_status("chart_analysis_agent", ticker, "Analyzing chart patterns")
            
            # Analyze the chart using vision model
            entry_signal = analyze_chart_with_vision(
                trading_chart=trading_chart,
                ticker=ticker,
                model_name=model_name,
                model_provider=model_provider,
            )
            
            # Store the analysis results
            entry_signals_analysis[ticker] = {
                "signal": entry_signal.signal,
                "confidence": entry_signal.confidence,
                "reasoning": entry_signal.reasoning,
                "pattern": entry_signal.pattern,
                "chart_url": entry_signal.chart_url,
            }
            print(f"Debug: Analysis completed for {ticker}: {entry_signals_analysis[ticker]}")
            
        except Exception as e:
            print(f"Debug: Error processing {ticker}: {str(e)}")
            progress.update_status("chart_analysis_agent", ticker, f"Error: {str(e)}")
            entry_signals_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": f"Error analyzing chart: {str(e)}",
                "pattern": None,
                "chart_url": None,
            }

        progress.update_status("chart_analysis_agent", ticker, "Done")

    # Create the entry signals message
    message = HumanMessage(
        content=json.dumps(entry_signals_analysis),
        name="chart_analysis_agent",
    )

    # Print the reasoning if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(entry_signals_analysis, "Chart Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["chart_analysis_agent"] = entry_signals_analysis

    return {
        "messages": [message],
        "data": data,
    }


def analyze_chart_with_vision(trading_chart, ticker, model_name, model_provider) -> EntrySignal:
    """Analyze a trading chart using a vision model to identify entry signals."""
    
    system_message = {
        "role": "system",
        "content": """You are a technical analysis expert. Analyze the chart and return your analysis in JSON format.
Your response must include all required fields: ticker, signal, confidence, pattern, reasoning, and chart_url."""
    }
    
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"""Please analyze this trading chart for {ticker} and provide your analysis in JSON format.

Focus on:
- Trend direction
- Support/resistance levels
- Chart patterns
- Technical indicators (MACD, RSI, EMAs)
- Volume patterns

Return JSON in this exact format:
{{
    "ticker": "{ticker}",
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": <number between 0-100>,
    "pattern": "<main technical pattern identified>",
    "reasoning": "<detailed explanation>",
    "chart_url": "{trading_chart.chart_url}"
}}"""
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{trading_chart.image_data}"
                }
            }
        ]
    }
    
    try:
        result = call_llm(
            prompt=[system_message, user_message],
            model_name=model_name,
            model_provider=model_provider,
            pydantic_model=EntrySignal,
            agent_name="chart_analysis_agent",
        )
        return result
    except Exception as e:
        print(f"Debug: LLM analysis error: {str(e)}")
        # Return a default signal if analysis fails
        return EntrySignal(
            ticker=ticker,
            signal="neutral",
            confidence=0,
            pattern="No pattern identified",
            reasoning=f"Error analyzing chart: {str(e)}",
            chart_url=trading_chart.chart_url
        )
