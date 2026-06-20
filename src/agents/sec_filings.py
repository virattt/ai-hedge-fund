import json

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.sec_api import get_filing_excerpts
from src.utils.llm import call_llm
from src.utils.progress import progress


class SecFilingsSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="2-3 key findings from the filings")


_SYSTEM = (
    "You are a qualitative analyst reading SEC filings for investment signals. "
    "You receive excerpts from a company's most recent 10-K (MD&A + Risk Factors), "
    "10-Q (MD&A), and 8-K (material events). Assess:\n"
    "1. Management tone — optimistic, cautious, or defensive?\n"
    "2. New or escalating risk factors vs. prior disclosures?\n"
    "3. Forward guidance language — specific and confident, or vague and hedged?\n"
    "4. Material events from 8-K that alter the investment thesis.\n"
    "Return a signal (bullish/bearish/neutral), confidence 0-100, and 2-3 concise findings."
)


def sec_filings_agent(state: AgentState, agent_id: str = "sec_filings_agent"):
    """Analyzes SEC filings (10-K, 10-Q, 8-K) for each ticker using EDGAR."""
    tickers = state["data"]["tickers"]
    sec_analysis = {}

    template = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            ("human", "Ticker: {ticker}\n\n{excerpts}\n\nReturn JSON only."),
        ]
    )

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching SEC filings")

        try:
            excerpts = get_filing_excerpts(ticker)
        except Exception as e:
            progress.update_status(agent_id, ticker, f"EDGAR fetch failed: {e}")
            sec_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "SEC filings unavailable",
            }
            continue

        if not any(excerpts.values()):
            sec_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "No SEC filings found for this ticker",
            }
            continue

        progress.update_status(agent_id, ticker, "Analyzing filings with LLM")

        excerpt_text = "\n\n".join(
            f"=== {form} ===\n{text}"
            for form, text in excerpts.items()
            if text
        )

        prompt = template.invoke({"ticker": ticker, "excerpts": excerpt_text})

        def _default():
            return SecFilingsSignal(
                signal="neutral",
                confidence=0,
                reasoning="LLM analysis failed — defaulting to neutral",
            )

        result = call_llm(
            prompt=prompt,
            pydantic_model=SecFilingsSignal,
            agent_name=agent_id,
            state=state,
            default_factory=_default,
        )

        sec_analysis[ticker] = result.model_dump()
        progress.update_status(agent_id, ticker, f"Signal: {result.signal} ({result.confidence}%)")

    state["data"]["analyst_signals"][agent_id] = sec_analysis

    message = HumanMessage(content=json.dumps(sec_analysis), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(sec_analysis, "SEC Filings Analyst")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
