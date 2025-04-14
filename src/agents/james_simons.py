from graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from tools.api import get_financial_metrics, get_market_cap, get_technical_indicators, get_historical_prices
from utils.llm import call_llm
from utils.progress import progress
import numpy as np
from datetime import datetime, timedelta


class JamesSimonsSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def james_simons_agent(state: AgentState):
    """Analyzes stocks using James Simons' quantitative approach and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for LLM reasoning
    analysis_data = {}
    simons_analysis = {}

    for ticker in tickers:
        progress.update_status("james_simons_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("james_simons_agent", ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date)

        progress.update_status("james_simons_agent", ticker, "Getting technical indicators")
        # Get technical indicators
        technical_indicators = get_technical_indicators(ticker, end_date)

        progress.update_status("james_simons_agent", ticker, "Getting historical prices")
        # Get historical prices for statistical analysis
        # Calculate start date (90 days before end date)
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
        historical_prices = get_historical_prices(ticker, start_date, end_date)

        progress.update_status("james_simons_agent", ticker, "Analyzing technical features")
        # Analyze technical features
        technical_analysis = analyze_technical_features(technical_indicators)

        progress.update_status("james_simons_agent", ticker, "Analyzing statistical patterns")
        # Analyze statistical patterns
        statistical_analysis = analyze_statistical_patterns(historical_prices)

        progress.update_status("james_simons_agent", ticker, "Analyzing market anomalies")
        # Analyze market anomalies
        anomaly_analysis = analyze_market_anomalies(historical_prices, technical_indicators)

        progress.update_status("james_simons_agent", ticker, "Analyzing momentum factors")
        # Analyze momentum factors
        momentum_analysis = analyze_momentum_factors(historical_prices)

        # Calculate total score
        total_score = (
            technical_analysis["score"] + 
            statistical_analysis["score"] + 
            anomaly_analysis["score"] + 
            momentum_analysis["score"]
        )
        
        max_possible_score = (
            technical_analysis["max_score"] + 
            statistical_analysis["max_score"] + 
            anomaly_analysis["max_score"] + 
            momentum_analysis["max_score"]
        )

        # Generate trading signal based on total score
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"

        # Combine all analysis results
        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "technical_analysis": technical_analysis,
            "statistical_analysis": statistical_analysis,
            "anomaly_analysis": anomaly_analysis,
            "momentum_analysis": momentum_analysis,
            "market_cap": market_cap,
        }

        progress.update_status("james_simons_agent", ticker, "Generating James Simons analysis")
        simons_output = generate_simons_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        # Store analysis in consistent format with other agents
        simons_analysis[ticker] = {
            "signal": simons_output.signal,
            "confidence": simons_output.confidence,
            "reasoning": simons_output.reasoning,
        }

        progress.update_status("james_simons_agent", ticker, "Done")

    # Create the message
    message = HumanMessage(content=json.dumps(simons_analysis), name="james_simons_agent")

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(simons_analysis, "James Simons Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["james_simons_agent"] = simons_analysis

    return {"messages": [message], "data": state["data"]}


def analyze_technical_features(technical_indicators: dict) -> dict:
    """Analyze technical indicators for quantitative signals."""
    if not technical_indicators:
        return {"score": 0, "max_score": 4, "details": "Insufficient technical indicator data"}
    
    score = 0
    reasoning = []
    
    # Check moving average relationships
    if "sma_50" in technical_indicators and "sma_200" in technical_indicators:
        sma_50 = technical_indicators["sma_50"]
        sma_200 = technical_indicators["sma_200"]
        
        if sma_50 > sma_200:
            score += 1
            reasoning.append(f"Bullish golden cross pattern (SMA50 {sma_50:.2f} > SMA200 {sma_200:.2f})")
        elif sma_50 < sma_200:
            reasoning.append(f"Bearish death cross pattern (SMA50 {sma_50:.2f} < SMA200 {sma_200:.2f})")
        else:
            reasoning.append(f"Neutral moving average relationship (SMA50 {sma_50:.2f} ≈ SMA200 {sma_200:.2f})")
    else:
        reasoning.append("Moving average data not available")
    
    # Check MACD signal
    if "macd" in technical_indicators and "macd_signal" in technical_indicators:
        macd = technical_indicators["macd"]
        macd_signal = technical_indicators["macd_signal"]
        
        if macd > macd_signal:
            score += 1
            reasoning.append(f"Bullish MACD signal (MACD {macd:.2f} > Signal {macd_signal:.2f})")
        elif macd < macd_signal:
            reasoning.append(f"Bearish MACD signal (MACD {macd:.2f} < Signal {macd_signal:.2f})")
        else:
            reasoning.append(f"Neutral MACD signal (MACD {macd:.2f} ≈ Signal {macd_signal:.2f})")
    else:
        reasoning.append("MACD data not available")
    
    # Check RSI
    if "rsi_14" in technical_indicators:
        rsi = technical_indicators["rsi_14"]
        
        if rsi < 30:
            score += 1
            reasoning.append(f"Oversold RSI ({rsi:.2f}) suggests potential reversal")
        elif rsi > 70:
            reasoning.append(f"Overbought RSI ({rsi:.2f}) suggests potential pullback")
        else:
            score += 0.5
            reasoning.append(f"Neutral RSI ({rsi:.2f})")
    else:
        reasoning.append("RSI data not available")
    
    # Check Bollinger Bands
    if all(k in technical_indicators for k in ["bollinger_upper", "bollinger_middle", "bollinger_lower"]):
        upper = technical_indicators["bollinger_upper"]
        middle = technical_indicators["bollinger_middle"]
        lower = technical_indicators["bollinger_lower"]
        current_price = technical_indicators.get("close", middle)
        
        # Calculate bandwidth and %B
        bandwidth = (upper - lower) / middle if middle else 0
        percent_b = (current_price - lower) / (upper - lower) if (upper - lower) else 0.5
        
        if percent_b < 0.1:
            score += 1
            reasoning.append(f"Price near lower Bollinger Band (%B: {percent_b:.2f}) suggests potential support")
        elif percent_b > 0.9:
            reasoning.append(f"Price near upper Bollinger Band (%B: {percent_b:.2f}) suggests potential resistance")
        
        if bandwidth > 0.2:
            score += 0.5
            reasoning.append(f"Wide Bollinger Band width ({bandwidth:.2f}) indicates high volatility")
        elif bandwidth < 0.1:
            score += 0.5
            reasoning.append(f"Narrow Bollinger Band width ({bandwidth:.2f}) suggests potential breakout")
    else:
        reasoning.append("Bollinger Bands data not available")
    
    return {
        "score": score,
        "max_score": 4,
        "details": "; ".join(reasoning),
    }


def analyze_statistical_patterns(historical_prices: list) -> dict:
    """Analyze statistical patterns in price data."""
    if not historical_prices or len(historical_prices) < 20:
        return {"score": 0, "max_score": 3, "details": "Insufficient historical price data"}
    
    score = 0
    reasoning = []
    
    # Extract close prices
    close_prices = [price["close"] for price in historical_prices if "close" in price]
    
    if len(close_prices) < 20:
        return {"score": 0, "max_score": 3, "details": "Insufficient close price data"}
    
    # Calculate returns
    returns = [close_prices[i] / close_prices[i-1] - 1 for i in range(1, len(close_prices))]
    
    # Check for mean reversion
    if len(returns) >= 20:
        # Calculate z-score of recent returns
        recent_returns = returns[-5:]
        historical_returns = returns[:-5]
        
        mean_hist = np.mean(historical_returns)
        std_hist = np.std(historical_returns)
        
        if std_hist > 0:
            recent_mean = np.mean(recent_returns)
            z_score = (recent_mean - mean_hist) / std_hist
            
            if z_score < -1.5:
                score += 1
                reasoning.append(f"Negative return z-score ({z_score:.2f}) suggests potential mean reversion upward")
            elif z_score > 1.5:
                reasoning.append(f"Positive return z-score ({z_score:.2f}) suggests potential mean reversion downward")
            else:
                reasoning.append(f"Neutral return z-score ({z_score:.2f})")
        else:
            reasoning.append("Insufficient return volatility for z-score calculation")
    else:
        reasoning.append("Insufficient return data for mean reversion analysis")
    
    # Check for volatility clustering
    if len(returns) >= 20:
        # Calculate absolute returns
        abs_returns = [abs(r) for r in returns]
        
        # Calculate autocorrelation of absolute returns
        if len(abs_returns) > 1:
            abs_returns_lag1 = abs_returns[:-1]
            abs_returns_current = abs_returns[1:]
            
            if len(abs_returns_lag1) > 0 and len(abs_returns_current) > 0:
                corr = np.corrcoef(abs_returns_lag1, abs_returns_current)[0, 1]
                
                if corr > 0.2:
                    score += 1
                    reasoning.append(f"Volatility clustering detected (autocorrelation: {corr:.2f})")
                else:
                    reasoning.append(f"No significant volatility clustering (autocorrelation: {corr:.2f})")
            else:
                reasoning.append("Insufficient data for volatility clustering analysis")
        else:
            reasoning.append("Insufficient data for volatility clustering analysis")
    else:
        reasoning.append("Insufficient return data for volatility clustering analysis")
    
    # Check for momentum effect
    if len(close_prices) >= 30:
        # Calculate 20-day momentum
        momentum_20d = close_prices[-1] / close_prices[-21] - 1
        
        if momentum_20d > 0.05:
            score += 1
            reasoning.append(f"Strong positive momentum ({momentum_20d:.1%} over 20 days)")
        elif momentum_20d < -0.05:
            reasoning.append(f"Strong negative momentum ({momentum_20d:.1%} over 20 days)")
        else:
            reasoning.append(f"Neutral momentum ({momentum_20d:.1%} over 20 days)")
    else:
        reasoning.append("Insufficient price data for momentum analysis")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_market_anomalies(historical_prices: list, technical_indicators: dict) -> dict:
    """Analyze market anomalies and inefficiencies."""
    if not historical_prices or len(historical_prices) < 20:
        return {"score": 0, "max_score": 3, "details": "Insufficient historical price data"}
    
    score = 0
    reasoning = []
    
    # Extract close prices and volumes
    close_prices = [price["close"] for price in historical_prices if "close" in price]
    volumes = [price["volume"] for price in historical_prices if "volume" in price]
    
    if len(close_prices) < 20 or len(volumes) < 20:
        return {"score": 0, "max_score": 3, "details": "Insufficient price or volume data"}
    
    # Check for price-volume divergence
    if len(close_prices) >= 10 and len(volumes) >= 10:
        price_change_5d = close_prices[-1] / close_prices[-6] - 1
        volume_change_5d = sum(volumes[-5:]) / sum(volumes[-10:-5]) - 1
        
        if price_change_5d > 0.03 and volume_change_5d > 0.5:
            score += 1
            reasoning.append(f"Bullish price-volume confirmation (price: {price_change_5d:.1%}, volume: {volume_change_5d:.1%})")
        elif price_change_5d < -0.03 and volume_change_5d > 0.5:
            reasoning.append(f"Bearish price-volume confirmation (price: {price_change_5d:.1%}, volume: {volume_change_5d:.1%})")
        elif price_change_5d > 0.03 and volume_change_5d < -0.3:
            reasoning.append(f"Price-volume divergence (price up, volume down)")
        elif price_change_5d < -0.03 and volume_change_5d < -0.3:
            score += 0.5
            reasoning.append(f"Potential bottoming (price down, volume down)")
    else:
        reasoning.append("Insufficient data for price-volume analysis")
    
    # Check for gap anomalies
    if len(close_prices) >= 20 and all("open" in price for price in historical_prices[-20:]):
        opens = [price["open"] for price in historical_prices[-20:]]
        gaps = [opens[i] / close_prices[i-1] - 1 for i in range(1, len(opens))]
        
        significant_gaps = [g for g in gaps if abs(g) > 0.02]
        
        if significant_gaps:
            recent_gap = gaps[-1]
            if recent_gap > 0.02:
                score += 1
                reasoning.append(f"Recent bullish gap of {recent_gap:.1%}")
            elif recent_gap < -0.02:
                reasoning.append(f"Recent bearish gap of {recent_gap:.1%}")
            
            reasoning.append(f"Found {len(significant_gaps)} significant gaps in recent trading")
        else:
            reasoning.append("No significant gaps detected")
    else:
        reasoning.append("Insufficient data for gap analysis")
    
    # Check for abnormal volume
    if len(volumes) >= 20:
        avg_volume = sum(volumes[-20:-1]) / 19
        latest_volume = volumes[-1]
        
        volume_ratio = latest_volume / avg_volume if avg_volume else 1
        
        if volume_ratio > 2:
            score += 1
            reasoning.append(f"Abnormally high volume ({volume_ratio:.1f}x average)")
        elif volume_ratio < 0.5:
            reasoning.append(f"Abnormally low volume ({volume_ratio:.1f}x average)")
        else:
            reasoning.append(f"Normal volume levels ({volume_ratio:.1f}x average)")
    else:
        reasoning.append("Insufficient volume data")
    
    return {
        "score": score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_momentum_factors(historical_prices: list) -> dict:
    """Analyze momentum factors in price data."""
    if not historical_prices or len(historical_prices) < 60:
        return {"score": 0, "max_score": 2, "details": "Insufficient historical price data"}
    
    score = 0
    reasoning = []
    
    # Extract close prices
    close_prices = [price["close"] for price in historical_prices if "close" in price]
    
    if len(close_prices) < 60:
        return {"score": 0, "max_score": 2, "details": "Insufficient close price data"}
    
    # Calculate short-term momentum (10-day)
    momentum_10d = close_prices[-1] / close_prices[-11] - 1
    
    # Calculate medium-term momentum (30-day)
    momentum_30d = close_prices[-1] / close_prices[-31] - 1
    
    # Calculate long-term momentum (60-day)
    momentum_60d = close_prices[-1] / close_prices[-61] - 1
    
    # Check for momentum alignment
    if momentum_10d > 0 and momentum_30d > 0 and momentum_60d > 0:
        score += 1
        reasoning.append(f"Strong positive momentum alignment across timeframes (10d: {momentum_10d:.1%}, 30d: {momentum_30d:.1%}, 60d: {momentum_60d:.1%})")
    elif momentum_10d < 0 and momentum_30d < 0 and momentum_60d < 0:
        reasoning.append(f"Strong negative momentum alignment across timeframes (10d: {momentum_10d:.1%}, 30d: {momentum_30d:.1%}, 60d: {momentum_60d:.1%})")
    elif momentum_10d > 0 and momentum_30d > 0:
        score += 0.5
        reasoning.append(f"Positive short and medium-term momentum (10d: {momentum_10d:.1%}, 30d: {momentum_30d:.1%})")
    elif momentum_10d < 0 and momentum_30d < 0:
        reasoning.append(f"Negative short and medium-term momentum (10d: {momentum_10d:.1%}, 30d: {momentum_30d:.1%})")
    else:
        reasoning.append(f"Mixed momentum signals (10d: {momentum_10d:.1%}, 30d: {momentum_30d:.1%}, 60d: {momentum_60d:.1%})")
    
    # Check for momentum acceleration
    if len(close_prices) >= 90:
        # Previous 30-day momentum
        prev_momentum_30d = close_prices[-31] / close_prices[-61] - 1
        
        # Momentum acceleration
        momentum_acceleration = momentum_30d - prev_momentum_30d
        
        if momentum_acceleration > 0.05:
            score += 1
            reasoning.append(f"Strong positive momentum acceleration ({momentum_acceleration:.1%})")
        elif momentum_acceleration < -0.05:
            reasoning.append(f"Strong negative momentum acceleration ({momentum_acceleration:.1%})")
        else:
            reasoning.append(f"Neutral momentum acceleration ({momentum_acceleration:.1%})")
    else:
        reasoning.append("Insufficient data for momentum acceleration analysis")
    
    return {
        "score": score,
        "max_score": 2,
        "details": "; ".join(reasoning),
    }


def generate_simons_output(
    ticker: str,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
) -> JamesSimonsSignal:
    """Get investment decision from LLM with James Simons' principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a James Simons AI agent. Decide on investment signals based on James Simons' quantitative principles:
                - Statistical Arbitrage: Identify and exploit statistical inefficiencies in markets
                - Pattern Recognition: Use mathematical models to identify non-random patterns
                - Quantitative Analysis: Focus on data-driven decisions rather than fundamental analysis
                - Short-term Trading: Capitalize on short to medium-term price movements
                - Market Anomalies: Identify and exploit market anomalies and inefficiencies
                - Momentum Factors: Consider price momentum across different timeframes
                - Technical Indicators: Analyze technical indicators for trading signals
                - Volatility Analysis: Understand and exploit volatility patterns

                When providing your reasoning, be thorough and specific by:
                1. Explaining the key statistical patterns and anomalies identified
                2. Highlighting the most significant technical indicators and their implications
                3. Analyzing momentum factors and their alignment across timeframes
                4. Providing quantitative evidence with specific numbers and percentages
                5. Concluding with a Simons-style assessment of the trading opportunity
                6. Using James Simons' analytical and mathematical voice in your explanation

                For example, if bullish: "The statistical analysis reveals [specific pattern] with a z-score of [value], combined with [technical indicator] at [value], suggesting a high-probability trading opportunity..."
                For example, if bearish: "The quantitative models indicate [specific issue] with a correlation of [value], while [technical indicator] shows [problem], creating a statistically significant selling signal..."

                Follow these guidelines strictly.
                """,
            ),
            (
                "human",
                """Based on the following data, create the investment signal as James Simons would:

                Analysis Data for {ticker}:
                {analysis_data}

                Return the trading signal in the following JSON format exactly:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": float between 0 and 100,
                  "reasoning": "string"
                }}
                """,
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    # Default fallback signal in case parsing fails
    def create_default_james_simons_signal():
        return JamesSimonsSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=JamesSimonsSignal,
        agent_name="james_simons_agent",
        default_factory=create_default_james_simons_signal,
    )
