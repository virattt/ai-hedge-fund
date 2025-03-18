from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
import json
from enum import Enum
from typing import List, Optional
import base64

from tools.chart_api import get_trading_chart
from data.models import EntrySignal, EntrySignalResponse
from utils.llm import call_llm


class ChartStrategy(str, Enum):
    SMI_CROSSOVER = "smi_crossover"
    # Add more strategies here as needed


def chart_analysis_agent(state: AgentState):
    """Analyzes trading charts using vision models to identify entry signals based on technical patterns."""
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    strategy = state.get("metadata", {}).get("chart_strategy", ChartStrategy.SMI_CROSSOVER)
    
    # Add debug logging
    print(f"Debug: Analyzing charts for tickers: {tickers}")
    print(f"Debug: Using end date: {end_date}")
    print(f"Debug: Using strategy: {strategy}")
    
    model_name = state.get("metadata", {}).get("model_name", "gpt-4o")
    model_provider = state.get("metadata", {}).get("model_provider", "OpenAI")

    # Initialize entry signals analysis for each ticker
    entry_signals_analysis = {}

    for ticker in tickers:
        print(f"Debug: Processing ticker {ticker}")
        progress.update_status("chart_analysis_agent", ticker, "Fetching trading chart")

        try:
            # Get the trading chart with SMI indicator
            trading_chart = get_trading_chart(
                ticker=ticker,
                end_date=end_date,
                timeframe="1D",  # Daily timeframe
                indicators=["smi", "smi_signal"],  # SMI and its signal line
            )
            print(f"Debug: Successfully fetched chart for {ticker}")
            
            progress.update_status("chart_analysis_agent", ticker, "Analyzing chart patterns")
            
            # Analyze the chart using the selected strategy
            entry_signal = analyze_chart_with_strategy(
                trading_chart=trading_chart,
                ticker=ticker,
                strategy=strategy,
                model_name=model_name,
                model_provider=model_provider,
            )
            
            # Store the analysis results
            entry_signals_analysis[ticker] = {
                "signal": entry_signal.signal,
                "confidence": entry_signal.confidence,
                "reasoning": entry_signal.reasoning,
                "pattern": entry_signal.pattern,
                "image_path": entry_signal.image_path,  # Changed from chart_url to image_path
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
                "image_path": None,  # Changed from chart_url to image_path
            }

        progress.update_status("chart_analysis_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(entry_signals_analysis),
        name="chart_analysis_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(entry_signals_analysis, "Chart Analysis Agent")

    state["data"]["analyst_signals"]["chart_analysis_agent"] = entry_signals_analysis

    return {
        "messages": [message],
        "data": data,
    }


def analyze_chart_with_strategy(
    trading_chart, 
    ticker: str, 
    strategy: ChartStrategy,
    model_name: str,
    model_provider: str
) -> EntrySignal:
    """Analyze a trading chart using the specified strategy."""
    
    if strategy == ChartStrategy.SMI_CROSSOVER:
        return analyze_smi_crossover(
            trading_chart=trading_chart,
            ticker=ticker,
            model_name=model_name,
            model_provider=model_provider,
        )
    
    # Add more strategy handlers here
    
    raise ValueError(f"Unknown strategy: {strategy}")


def analyze_smi_crossover(trading_chart, ticker: str, model_name: str, model_provider: str) -> EntrySignal:
    """Analyze SMI crossover signals for entry opportunities."""
    
    # Read and encode the image
    try:
        with open(trading_chart.image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Debug: Error reading image file: {str(e)}")
        return EntrySignal(
            ticker=ticker,
            signal="neutral",
            confidence=0,
            pattern="No valid SMI signal",
            reasoning=f"Error reading chart image: {str(e)}",
            image_path=trading_chart.image_path
        )
    
    system_message = {
        "role": "system",
        "content": """You are a technical analysis expert specializing in SMI (Stochastic Momentum Index) analysis.
Focus specifically on identifying bullish entry signals where:
1. The SMI line is below the oversold level (-40)
2. The SMI line is showing upward momentum
3. The SMI line is about to cross or has recently crossed above its signal line

Return your analysis in JSON format with all required fields."""
    }
    
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"""Analyze this chart for {ticker} focusing on SMI crossover signals.

Key criteria:
- SMI position relative to -40 oversold level
- SMI line slope and momentum
- SMI crossover with signal line
- Confirmation from price action

Return JSON in this exact format:
{{
    "ticker": "{ticker}",
    "signal": "bullish" if entry criteria met, else "neutral",
    "confidence": <number between 0-100>,
    "pattern": "SMI bullish crossover" or "No valid SMI signal",
    "reasoning": "<detailed explanation of SMI analysis>",
    "image_path": "{trading_chart.image_path}"
}}"""
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_data}"
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
        return EntrySignal(
            ticker=ticker,
            signal="neutral",
            confidence=0,
            pattern="No valid SMI signal",
            reasoning=f"Error analyzing SMI signals: {str(e)}",
            image_path=trading_chart.image_path
        )
