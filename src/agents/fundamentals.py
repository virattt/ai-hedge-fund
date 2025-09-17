from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.api_key import get_api_key_from_state
from src.utils.progress import progress
import json

from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
)
from src.utils.llm import call_llm

def _safe_first_metric(financial_metrics):
    """Return the first metric entry (object or dict), or None if unavailable."""
    if not financial_metrics:
        return None
    if isinstance(financial_metrics, list):
        return financial__safe_first_metric(metrics) if financial_metrics else None
    if isinstance(financial_metrics, dict):
        return next(iter(financial_metrics.values()), None)
    return None


def fundamentals_analyst_agent(state: AgentState, agent_id: str = "fundamentals_analyst_agent"):
    """Analyzes fundamental data and generates trading signals for multiple tickers."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    fundamental_analysis = {}

    for ticker in tickers:
        try:
            progress.update_status(agent_id, ticker, "Fetching financial metrics")

            financial_metrics = get_financial_metrics(
                symbol=ticker,
                end_date=end_date,
                period="ttm",
                limit=10,
                api_key=api_key,
            )

            metrics = _safe_first_metric(financial_metrics)

            if not metrics:
                progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
                fundamental_analysis[ticker] = {
                    "signal": "neutral",
                    "confidence": 0,
                    "reasoning": {"error": "No financial metrics available"},
                }
                continue

            # ------------------------------
            # Initialize signals & reasoning
            # ------------------------------
            signals = []
            reasoning = {}

            progress.update_status(agent_id, ticker, "Analyzing profitability")
            # 1. Profitability Analysis
            return_on_equity = getattr(metrics, "return_on_equity", None)
            net_margin = getattr(metrics, "net_margin", None)
            operating_margin = getattr(metrics, "operating_margin", None)

            thresholds = [
                (return_on_equity, 0.15),
                (net_margin, 0.20),
                (operating_margin, 0.15),
            ]
            profitability_score = sum(
                metric is not None and metric > threshold
                for metric, threshold in thresholds
            )

            signals.append(
                "bullish" if profitability_score >= 2 else
                "bearish" if profitability_score == 0 else
                "neutral"
            )
            reasoning["profitability_signal"] = {
                "signal": signals[0],
                "details": (
                    (f"ROE: {return_on_equity:.2%}" if return_on_equity is not None else "ROE: N/A")
                    + ", "
                    + (f"Net Margin: {net_margin:.2%}" if net_margin is not None else "Net Margin: N/A")
                    + ", "
                    + (f"Op Margin: {operating_margin:.2%}" if operating_margin is not None else "Op Margin: N/A")
                ),
            }

            progress.update_status(agent_id, ticker, "Analyzing growth")
            # 2. Growth Analysis
            revenue_growth = getattr(metrics, "revenue_growth", None)
            earnings_growth = getattr(metrics, "earnings_growth", None)
            book_value_growth = getattr(metrics, "book_value_growth", None)

            thresholds = [
                (revenue_growth, 0.10),
                (earnings_growth, 0.10),
                (book_value_growth, 0.10),
            ]
            growth_score = sum(
                metric is not None and metric > threshold
                for metric, threshold in thresholds
            )

            signals.append(
                "bullish" if growth_score >= 2 else
                "bearish" if growth_score == 0 else
                "neutral"
            )
            reasoning["growth_signal"] = {
                "signal": signals[1],
                "details": (
                    (f"Revenue Growth: {revenue_growth:.2%}" if revenue_growth is not None else "Revenue Growth: N/A")
                    + ", "
                    + (f"Earnings Growth: {earnings_growth:.2%}" if earnings_growth is not None else "Earnings Growth: N/A")
                ),
            }

            progress.update_status(agent_id, ticker, "Analyzing financial health")
            # 3. Financial Health
            current_ratio = getattr(metrics, "current_ratio", None)
            debt_to_equity = getattr(metrics, "debt_to_equity", None)
            free_cash_flow_per_share = getattr(metrics, "free_cash_flow_per_share", None)
            earnings_per_share = getattr(metrics, "earnings_per_share", None)

            health_score = 0
            if current_ratio is not None and current_ratio > 1.5:
                health_score += 1
            if debt_to_equity is not None and debt_to_equity < 0.5:
                health_score += 1
            if (
                free_cash_flow_per_share is not None
                and earnings_per_share is not None
                and free_cash_flow_per_share > earnings_per_share * 0.8
            ):
                health_score += 1

            signals.append(
                "bullish" if health_score >= 2 else
                "bearish" if health_score == 0 else
                "neutral"
            )
            reasoning["financial_health_signal"] = {
                "signal": signals[2],
                "details": (
                    (f"Current Ratio: {current_ratio:.2f}" if current_ratio is not None else "Current Ratio: N/A")
                    + ", "
                    + (f"D/E: {debt_to_equity:.2f}" if debt_to_equity is not None else "D/E: N/A")
                ),
            }

            progress.update_status(agent_id, ticker, "Analyzing valuation ratios")
            # 4. Valuation Ratios
            pe_ratio = getattr(metrics, "price_to_earnings_ratio", None)
            pb_ratio = getattr(metrics, "price_to_book_ratio", None)
            ps_ratio = getattr(metrics, "price_to_sales_ratio", None)

            thresholds = [
                (pe_ratio, 25),
                (pb_ratio, 3),
                (ps_ratio, 5),
            ]
            price_ratio_score = sum(
                metric is not None and metric > threshold
                for metric, threshold in thresholds
            )

            signals.append(
                "bearish" if price_ratio_score >= 2 else
                "bullish" if price_ratio_score == 0 else
                "neutral"
            )
            reasoning["price_ratios_signal"] = {
                "signal": signals[3],
                "details": (
                    (f"P/E: {pe_ratio:.2f}" if pe_ratio is not None else "P/E: N/A")
                    + ", "
                    + (f"P/B: {pb_ratio:.2f}" if pb_ratio is not None else "P/B: N/A")
                    + ", "
                    + (f"P/S: {ps_ratio:.2f}" if ps_ratio is not None else "P/S: N/A")
                ),
            }

            progress.update_status(agent_id, ticker, "Calculating final signal")
            # ------------------------------
            # Final aggregation
            # ------------------------------
            bullish_signals = signals.count("bullish")
            bearish_signals = signals.count("bearish")

            if bullish_signals > bearish_signals:
                overall_signal = "bullish"
            elif bearish_signals > bullish_signals:
                overall_signal = "bearish"
            else:
                overall_signal = "neutral"

            total_signals = len(signals)
            confidence = (
                round(max(bullish_signals, bearish_signals) / total_signals, 2) * 100
                if total_signals > 0 else 0
            )

            fundamental_analysis[ticker] = {
                "signal": overall_signal,
                "confidence": confidence,
                "reasoning": reasoning,
            }

            progress.update_status(
                agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4)
            )

        except Exception as e:
            fundamental_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": {"error": str(e)},
            }

    message = HumanMessage(
        content=json.dumps(fundamental_analysis),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(fundamental_analysis, "Fundamental Analysis Agent")

    state["data"]["analyst_signals"][agent_id] = fundamental_analysis
    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": data,
    }