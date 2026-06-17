"""Analysis mode definitions and agent tier routing.

Modes control how many LLM agents run per ticker:
- QUICK_SCAN: No LLM agents. Local indicators + provider data only.
- STANDARD: Technical + Sentiment + Risk agents (3 agents).
- DEEP_DIVE: All available agents (full multi-agent pipeline).
"""

from enum import Enum


class AnalysisMode(str, Enum):
    QUICK_SCAN = "quick_scan"
    STANDARD = "standard"
    DEEP_DIVE = "deep_dive"


# Agents to run per mode (for US tickers that go through the full pipeline)
TIER_AGENTS: dict[AnalysisMode, list[str]] = {
    AnalysisMode.QUICK_SCAN: [],  # No LLM agents — local computation only
    AnalysisMode.STANDARD: [
        "technical_analyst",
        "fundamentals_analyst",
        "sentiment_analyst",
        "valuation_analyst",
    ],
    AnalysisMode.DEEP_DIVE: [],  # Empty means ALL agents (default behavior)
}

# Models to use per mode (cheaper models for cheaper tiers)
TIER_MODELS: dict[AnalysisMode, dict[str, str]] = {
    AnalysisMode.QUICK_SCAN: {
        "model_name": "gpt-4o-mini",
        "model_provider": "OpenAI",
    },
    AnalysisMode.STANDARD: {
        "model_name": "gpt-4o-mini",
        "model_provider": "OpenAI",
    },
    AnalysisMode.DEEP_DIVE: {
        "model_name": "gpt-4.1",
        "model_provider": "OpenAI",
    },
}

# Estimated tokens per mode (for UI display / logging)
ESTIMATED_TOKENS: dict[AnalysisMode, int] = {
    AnalysisMode.QUICK_SCAN: 0,       # No LLM calls
    AnalysisMode.STANDARD: 8_000,     # ~2k per agent x 4 agents
    AnalysisMode.DEEP_DIVE: 50_000,   # ~2.5k per agent x 18+ agents
}

MODE_DESCRIPTIONS: dict[AnalysisMode, str] = {
    AnalysisMode.QUICK_SCAN: "Local indicators only. No AI agents. Zero token cost.",
    AnalysisMode.STANDARD: "Technical, Fundamental, Sentiment, Valuation agents. Low token cost.",
    AnalysisMode.DEEP_DIVE: "All AI agents including investor personas. High token cost.",
}
