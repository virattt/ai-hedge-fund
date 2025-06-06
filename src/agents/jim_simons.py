from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
import numpy as np
import pandas as pd
from typing_extensions import Literal
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.llm import call_llm
from src.utils.progress import progress

class JimSimonsSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str

def jim_simons_agent(state: AgentState):
    """Analyzes stocks using Jim Simons' quantitative principles and systematic approach."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Collect all analysis for systematic processing
    analysis_data = {}
    simons_analysis = {}

    for ticker in tickers:

        # Core Data Collection
        progress.update_status("jim_simons_agent", ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=10)  # More historical data for patterns

        progress.update_status("jim_simons_agent", ticker, "Fetching financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "net_income",
                "earnings_per_share",
                "revenue",
                "operating_income",
                "total_assets",
                "total_liabilities",
                "current_assets",
                "current_liabilities",
                "free_cash_flow",
                "research_and_development",
                "capital_expenditure",
                "working_capital"
            ],
            end_date,
        )

        progress.update_status("jim_simons_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)

        # ─── Quantitative Analyses ─────────────────────────────────────────────
        progress.update_status("jim_simons_agent", ticker, "Analyzing statistical patterns")
        pattern_analysis = analyze_statistical_patterns(financial_line_items)

        progress.update_status("jim_simons_agent", ticker, "Analyzing mean reversion signals")
        mean_reversion_analysis = analyze_mean_reversion(financial_line_items)
        
        progress.update_status("jim_simons_agent", ticker, "Analyzing momentum indicators")
        momentum_analysis = analyze_momentum_indicators(financial_line_items)
        
        progress.update_status("jim_simons_agent", ticker, "Analyzing anomaly detection")
        anomaly_analysis = analyze_anomalies(financial_line_items)
        
        progress.update_status("jim_simons_agent", ticker, "Analyzing cross-sectional factors")
        cross_sectional_analysis = analyze_cross_sectional_factors(financial_line_items)
        
        progress.update_status("jim_simons_agent", ticker, "Computing risk metrics")
        risk_analysis = compute_risk_metrics(financial_line_items)

        # ─── Systematic Scoring ────────────────────────────────────────────────
        # Calculate composite score based on multiple quantitative factors
        factor_scores = {
            'pattern_score': pattern_analysis["score"],
            'mean_reversion_score': mean_reversion_analysis["score"],
            'momentum_score': momentum_analysis["score"],
            'anomaly_score': anomaly_analysis["score"],
            'cross_sectional_score': cross_sectional_analysis["score"],
            'risk_adjusted_score': risk_analysis["score"]
        }

        # Weighted composite score (Simons-style multi-factor approach)
        weights = {
            'pattern_score': 0.20,           # Highest - Simons' core strength
            'mean_reversion_score': 0.18,    # Statistical arbitrage focus
            'momentum_score': 0.17,          # Short-term trend capture
            'anomaly_score': 0.15,           # Statistical outlier detection
            'cross_sectional_score': 0.15,   # Relative factor analysis
            'risk_adjusted_score': 0.15      # Risk management priority
        }

        composite_score = sum(factor_scores[factor] * weights[factor] for factor in weights)
        max_composite_score = sum(weights.values()) * 10  # Assuming max individual score is 10

        # Statistical significance test
        signal_strength = calculate_signal_strength(factor_scores)
        
        # Decision rules based on quantitative thresholds
        if composite_score >= max_composite_score * 0.7 and signal_strength > 0.6:
            signal = "bullish"
        elif composite_score <= max_composite_score * 0.3 and signal_strength > 0.6:
            signal = "bearish"
        else:
            signal = "neutral"

        # Confidence based on signal strength and consistency
        confidence = min(max(signal_strength * 100, 15), 95)

        # Comprehensive analysis summary
        quantitative_summary = create_quantitative_summary(
            financial_line_items,
            factor_scores,
            composite_score,
            signal_strength
        )

        analysis_data[ticker] = {
            "signal": signal,
            "composite_score": composite_score,
            "max_composite_score": max_composite_score,
            "signal_strength": signal_strength,
            "factor_scores": factor_scores,
            "pattern_analysis": pattern_analysis,
            "mean_reversion_analysis": mean_reversion_analysis,
            "momentum_analysis": momentum_analysis,
            "anomaly_analysis": anomaly_analysis,
            "cross_sectional_analysis": cross_sectional_analysis,
            "risk_analysis": risk_analysis,
            "quantitative_summary": quantitative_summary,
            "market_cap": market_cap,
        }

        # ─── LLM: Generate Simons-style systematic narrative ──────────────────
        progress.update_status("jim_simons_agent", ticker, "Generating Simons analysis")
        simons_output = generate_simons_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )

        simons_analysis[ticker] = simons_output.model_dump()

        progress.update_status("jim_simons_agent", ticker, "Done", analysis=simons_output.reasoning)

    # ─── Push message back to graph state ──────────────────────────────────────
    message = HumanMessage(content=json.dumps(simons_analysis), name="jim_simons_agent")

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(simons_analysis, "Jim Simons Agent")

    state["data"]["analyst_signals"]["jim_simons_agent"] = simons_analysis
    progress.update_status("jim_simons_agent", None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_statistical_patterns(financial_line_items: list) -> dict[str, any]:
    """
    Identify statistical patterns in financial data using time series analysis.
    Simons looked for repeatable patterns in data.
    """
    if len(financial_line_items) < 5:
        return {"score": 0, "details": "Insufficient data for pattern analysis"}

    score = 0
    reasoning = []

    # Extract time series data
    revenues = [getattr(item, "revenue", 0) for item in financial_line_items if getattr(item, "revenue", None)]
    earnings = [getattr(item, "net_income", 0) for item in financial_line_items if getattr(item, "net_income", None)]

    if len(revenues) >= 5:
        # Calculate autocorrelation (pattern persistence)
        revenue_changes = [revenues[i] - revenues[i+1] for i in range(len(revenues)-1)]
        if len(revenue_changes) >= 3:
            autocorr = np.corrcoef(revenue_changes[:-1], revenue_changes[1:])[0,1] if len(revenue_changes) > 2 else 0
            
            if abs(autocorr) > 0.3:  # Strong pattern
                score += 3
                reasoning.append(f"Strong revenue pattern detected (autocorr: {autocorr:.3f})")
            elif abs(autocorr) > 0.1:  # Moderate pattern
                score += 1
                reasoning.append(f"Moderate revenue pattern (autocorr: {autocorr:.3f})")

        # Volatility analysis
        revenue_volatility = np.std(revenues) / np.mean(revenues) if np.mean(revenues) > 0 else float('inf')
        if revenue_volatility < 0.2:  # Low volatility is predictable
            score += 2
            reasoning.append(f"Low revenue volatility: {revenue_volatility:.3f}")
        elif revenue_volatility < 0.4:
            score += 1
            reasoning.append(f"Moderate revenue volatility: {revenue_volatility:.3f}")

    if len(earnings) >= 5:
        # Earnings predictability
        earnings_trend = np.polyfit(range(len(earnings)), earnings, 1)[0]  # Linear trend
        earnings_r2 = np.corrcoef(range(len(earnings)), earnings)[0,1]**2
        
        if earnings_r2 > 0.7:  # Strong trend
            score += 2
            reasoning.append(f"Strong earnings trend (R²: {earnings_r2:.3f})")
        elif earnings_r2 > 0.4:
            score += 1
            reasoning.append(f"Moderate earnings trend (R²: {earnings_r2:.3f})")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_mean_reversion(financial_line_items: list) -> dict[str, any]:
    """
    Analyze mean reversion patterns in financial metrics.
    Simons exploited mean reversion in various financial ratios.
    """
    if len(financial_line_items) < 4:
        return {"score": 0, "details": "Insufficient data for mean reversion analysis"}

    score = 0
    reasoning = []

    # Calculate key ratios over time
    profit_margins = []
    roe_values = []
    
    for item in financial_line_items:
        # Profit margin
        if getattr(item, "net_income", None) and getattr(item, "revenue", None) and item.revenue > 0:
            margin = item.net_income / item.revenue
            profit_margins.append(margin)
        
        # ROE
        if (getattr(item, "net_income", None) and getattr(item, "total_assets", None) and 
            getattr(item, "total_liabilities", None) and item.total_assets > item.total_liabilities):
            equity = item.total_assets - item.total_liabilities
            if equity > 0:
                roe = item.net_income / equity
                roe_values.append(roe)

    # Mean reversion in profit margins
    if len(profit_margins) >= 4:
        mean_margin = np.mean(profit_margins)
        current_deviation = abs(profit_margins[0] - mean_margin) / (np.std(profit_margins) + 1e-6)
        
        if current_deviation > 1.5:  # Significant deviation suggests reversion opportunity
            score += 3
            direction = "above" if profit_margins[0] > mean_margin else "below"
            reasoning.append(f"Profit margin significantly {direction} historical mean (z-score: {current_deviation:.2f})")
        elif current_deviation > 1.0:
            score += 2
            reasoning.append(f"Moderate profit margin deviation (z-score: {current_deviation:.2f})")

    # Mean reversion in ROE
    if len(roe_values) >= 4:
        mean_roe = np.mean(roe_values)
        current_roe_deviation = abs(roe_values[0] - mean_roe) / (np.std(roe_values) + 1e-6)
        
        if current_roe_deviation > 1.5:
            score += 2
            direction = "above" if roe_values[0] > mean_roe else "below"
            reasoning.append(f"ROE significantly {direction} historical mean (z-score: {current_roe_deviation:.2f})")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_momentum_indicators(financial_line_items: list) -> dict[str, any]:
    """
    Analyze momentum in financial performance.
    Simons used momentum signals across different timeframes.
    """
    if len(financial_line_items) < 3:
        return {"score": 0, "details": "Insufficient data for momentum analysis"}

    score = 0
    reasoning = []

    # Revenue momentum
    revenues = [getattr(item, "revenue", 0) for item in financial_line_items[:6] if getattr(item, "revenue", None)]
    if len(revenues) >= 3:
        recent_growth = (revenues[0] - revenues[1]) / revenues[1] if revenues[1] > 0 else 0
        longer_growth = (revenues[1] - revenues[2]) / revenues[2] if revenues[2] > 0 else 0
        
        # Accelerating growth
        if recent_growth > longer_growth and recent_growth > 0.05:
            score += 3
            reasoning.append(f"Accelerating revenue growth: {recent_growth:.1%} vs {longer_growth:.1%}")
        elif recent_growth > 0.10:
            score += 2
            reasoning.append(f"Strong recent revenue growth: {recent_growth:.1%}")

    # Earnings momentum
    earnings = [getattr(item, "net_income", 0) for item in financial_line_items[:6] if getattr(item, "net_income", None)]
    if len(earnings) >= 3:
        recent_earnings_growth = (earnings[0] - earnings[1]) / abs(earnings[1]) if earnings[1] != 0 else 0
        longer_earnings_growth = (earnings[1] - earnings[2]) / abs(earnings[2]) if earnings[2] != 0 else 0
        
        if recent_earnings_growth > longer_earnings_growth and recent_earnings_growth > 0.10:
            score += 3
            reasoning.append(f"Accelerating earnings growth: {recent_earnings_growth:.1%} vs {longer_earnings_growth:.1%}")
        elif recent_earnings_growth > 0.15:
            score += 2
            reasoning.append(f"Strong recent earnings growth: {recent_earnings_growth:.1%}")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_anomalies(financial_line_items: list) -> dict[str, any]:
    """
    Detect anomalies that might indicate opportunities or risks.
    Simons looked for statistical anomalies in data.
    """
    if len(financial_line_items) < 4:
        return {"score": 0, "details": "Insufficient data for anomaly detection"}

    score = 0
    reasoning = []

    # Working capital anomalies
    working_capitals = []
    for item in financial_line_items:
        if (getattr(item, "current_assets", None) and getattr(item, "current_liabilities", None)):
            wc = item.current_assets - item.current_liabilities
            working_capitals.append(wc)

    if len(working_capitals) >= 4:
        wc_changes = [working_capitals[i] - working_capitals[i+1] for i in range(len(working_capitals)-1)]
        if wc_changes:
            mean_change = np.mean(wc_changes)
            std_change = np.std(wc_changes)
            recent_change = wc_changes[0]
            
            if abs(recent_change - mean_change) > 2 * std_change:
                score += 2
                direction = "increase" if recent_change > mean_change else "decrease"
                reasoning.append(f"Anomalous working capital {direction} detected")

    # Cash flow vs earnings anomalies
    if len(financial_line_items) >= 3:
        latest = financial_line_items[0]
        if (getattr(latest, "free_cash_flow", None) and getattr(latest, "net_income", None) and 
            latest.net_income > 0):
            
            cash_to_earnings = latest.free_cash_flow / latest.net_income
            if cash_to_earnings > 1.5:  # Much higher cash flow than earnings
                score += 3
                reasoning.append(f"Positive cash flow anomaly: FCF/Earnings = {cash_to_earnings:.2f}")
            elif cash_to_earnings < 0.5:  # Much lower cash flow
                score -= 1
                reasoning.append(f"Negative cash flow anomaly: FCF/Earnings = {cash_to_earnings:.2f}")

    return {"score": score, "details": "; ".join(reasoning)}


def analyze_cross_sectional_factors(financial_line_items: list) -> dict[str, any]:
    """
    Analyze factors that work across different stocks.
    Simons used cross-sectional factor models.
    """
    if not financial_line_items:
        return {"score": 0, "details": "No data for cross-sectional analysis"}

    score = 0
    reasoning = []
    latest = financial_line_items[0]

    # Quality factor
    if (getattr(latest, "net_income", None) and getattr(latest, "total_assets", None) and 
        getattr(latest, "total_liabilities", None) and latest.total_assets > latest.total_liabilities):
        
        equity = latest.total_assets - latest.total_liabilities
        if equity > 0:
            roe = latest.net_income / equity
            if roe > 0.15:  # High ROE companies tend to outperform
                score += 2
                reasoning.append(f"High quality factor: ROE = {roe:.1%}")

    # Profitability factor
    if (getattr(latest, "operating_income", None) and getattr(latest, "total_assets", None) and 
        latest.total_assets > 0):
        roa = latest.operating_income / latest.total_assets
        if roa > 0.08:  # High asset efficiency
            score += 2
            reasoning.append(f"Strong profitability factor: ROA = {roa:.1%}")

    # Investment factor (low capex relative to assets can be positive)
    if (getattr(latest, "capital_expenditure", None) and getattr(latest, "total_assets", None) and 
        latest.total_assets > 0):
        capex_ratio = latest.capital_expenditure / latest.total_assets
        if capex_ratio < 0.05:  # Low capital intensity
            score += 1
            reasoning.append(f"Low investment factor: CapEx/Assets = {capex_ratio:.1%}")

    return {"score": score, "details": "; ".join(reasoning)}


def compute_risk_metrics(financial_line_items: list) -> dict[str, any]:
    """
    Compute risk-adjusted metrics.
    Simons was very focused on risk management.
    """
    if len(financial_line_items) < 3:
        return {"score": 0, "details": "Insufficient data for risk analysis"}

    score = 0
    reasoning = []

    # Earnings volatility
    earnings = [getattr(item, "net_income", 0) for item in financial_line_items if getattr(item, "net_income", None)]
    if len(earnings) >= 4:
        earnings_volatility = np.std(earnings) / (abs(np.mean(earnings)) + 1e-6)
        if earnings_volatility < 0.3:  # Low volatility
            score += 3
            reasoning.append(f"Low earnings volatility: {earnings_volatility:.3f}")
        elif earnings_volatility < 0.6:
            score += 1
            reasoning.append(f"Moderate earnings volatility: {earnings_volatility:.3f}")

    # Balance sheet stability
    latest = financial_line_items[0]
    if (getattr(latest, "total_assets", None) and getattr(latest, "total_liabilities", None) and 
        latest.total_assets > 0):
        debt_ratio = latest.total_liabilities / latest.total_assets
        if debt_ratio < 0.4:  # Conservative debt levels
            score += 2
            reasoning.append(f"Conservative debt ratio: {debt_ratio:.2f}")
        elif debt_ratio > 0.7:  # High debt is risky
            score -= 1
            reasoning.append(f"High debt ratio: {debt_ratio:.2f}")

    return {"score": score, "details": "; ".join(reasoning)}


def calculate_signal_strength(factor_scores: dict) -> float:
    """
    Calculate overall signal strength based on factor consistency.
    """
    scores = list(factor_scores.values())
    if not scores:
        return 0.0
    
    # Normalize scores to 0-1 range
    normalized_scores = [max(0, min(10, score)) / 10 for score in scores]
    
    # Signal strength is based on both magnitude and consistency
    mean_score = np.mean(normalized_scores)
    consistency = 1 - (np.std(normalized_scores) / (mean_score + 1e-6))
    
    # Combine magnitude and consistency
    signal_strength = (mean_score * 0.7) + (consistency * 0.3)
    
    return max(0, min(1, signal_strength))


def create_quantitative_summary(
    financial_line_items: list,
    factor_scores: dict,
    composite_score: float,
    signal_strength: float
) -> dict[str, any]:
    """
    Create a comprehensive quantitative summary.
    """
    return {
        "composite_score": composite_score,
        "signal_strength": signal_strength,
        "factor_breakdown": factor_scores,
        "data_quality": len(financial_line_items),
        "key_metrics": extract_key_metrics(financial_line_items)
    }


def extract_key_metrics(financial_line_items: list) -> dict:
    """Extract key financial metrics for analysis."""
    if not financial_line_items:
        return {}
    
    latest = financial_line_items[0]
    metrics = {}
    
    # Revenue and growth
    if getattr(latest, "revenue", None):
        metrics["revenue"] = latest.revenue
        if len(financial_line_items) > 1 and getattr(financial_line_items[1], "revenue", None):
            revenue_growth = (latest.revenue - financial_line_items[1].revenue) / financial_line_items[1].revenue
            metrics["revenue_growth"] = revenue_growth
    
    # Profitability
    if getattr(latest, "net_income", None):
        metrics["net_income"] = latest.net_income
        if getattr(latest, "revenue", None) and latest.revenue > 0:
            metrics["profit_margin"] = latest.net_income / latest.revenue
    
    return metrics


# ────────────────────────────────────────────────────────────────────────────────
# LLM generation
# ────────────────────────────────────────────────────────────────────────────────
def generate_simons_output(
    ticker: str,
    analysis_data: dict[str, any],
    model_name: str,
    model_provider: str,
) -> JimSimonsSignal:
    """Get investment decision from LLM with Jim Simons' systematic principles"""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Jim Simons AI agent. Make systematic trading decisions based on Jim Simons' quantitative principles:
                - Data-Driven Decisions: Rely on statistical evidence, not opinions or stories
                - Pattern Recognition: Look for repeatable patterns in financial data
                - Mean Reversion: Exploit temporary price and ratio deviations from historical norms
                - Short-term Systematic Signals: Focus on quantifiable, systematic factors
                - Risk Management: Always consider risk-adjusted returns and position sizing
                - Statistical Significance: Only act on signals with strong statistical evidence
                - Multi-Factor Models: Combine multiple quantitative factors for robust signals
                - Anomaly Detection: Identify and exploit statistical anomalies in financial data
                - Cross-Sectional Analysis: Use factors that work across different securities
                - No Fundamental Stories: Avoid narrative-based reasoning, stick to numbers

                When providing your reasoning, be quantitative and systematic by:
                1. Highlighting the specific statistical patterns or anomalies that drove your decision
                2. Referencing concrete numerical evidence (correlations, z-scores, factor loadings)
                3. Explaining the statistical significance of the signals
                4. Discussing risk-adjusted metrics and signal strength
                5. Using Simons' systematic, mathematical approach in your explanation
                6. Avoiding fundamental analysis or storytelling

                For example, if bullish: "The quantitative signals show strong statistical significance with a z-score of 2.3 in mean reversion factors, combined with momentum indicators at the 85th percentile..."
                For example, if bearish: "Multiple factor models indicate negative expected returns with 73% confidence, driven by anomalous cash flow patterns and risk-adjusted momentum below the 25th percentile..."

                Maintain Jim Simons' systematic, mathematical mindset throughout.
                """,
            ),
            (
                "human",
                """Based on the following quantitative analysis, create the systematic trading signal as Jim Simons would:

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
    def create_default_simons_signal():
        return JimSimonsSignal(signal="neutral", confidence=0.0, reasoning="Error in quantitative analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=JimSimonsSignal,
        agent_name="jim_simons_agent",
        default_factory=create_default_simons_signal,
    )