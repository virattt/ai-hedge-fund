"""News analyst agent — an LLM reads the week's headlines.

The no-extra-dependencies counterpart to NewsSentimentModel (FinBERT): same
data, but a general LLM reasons over the headlines instead of a classifier
scoring them. It can weigh materiality (a guidance cut vs. a product
review) at the cost of LLM calls — which PromptCache keeps to one per
distinct headline set.

Not a real person: a stylized desk analyst persona (see VISION.md). The
persona is ONLY a system prompt plus the news snapshot — all machinery lives
in LLMAgent.
"""

from __future__ import annotations

from hedge_fund.data.protocol import DataClient
from hedge_fund.features.news import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_NEWS_LIMIT,
    NewsSnapshot,
    build_news_snapshot,
)
from hedge_fund.llm import LLMClient, PromptCache
from hedge_fund.signals.llm_agent import LLMAgent


class NewsAnalystAgent(LLMAgent):
    """Reasons over recent company headlines."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        cache: PromptCache | None = None,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_headlines: int = 3,
        news_limit: int = DEFAULT_NEWS_LIMIT,
    ) -> None:
        super().__init__(llm=llm, cache=cache)
        self._lookback_days = lookback_days
        self._min_headlines = min_headlines
        self._news_limit = news_limit

    @property
    def name(self) -> str:
        return "news_analyst"

    def build_snapshot(self, ticker: str, date: str, data_client: DataClient) -> NewsSnapshot:
        return build_news_snapshot(
            ticker, date, data_client,
            lookback_days=self._lookback_days,
            min_headlines=self._min_headlines,
            limit=self._news_limit,
        )

    def get_system_prompt(self) -> str:
        return """You are a veteran equity news analyst on a trading desk. You
read a week of headlines on one company and decide what they mean for the
stock over the next few weeks.

Work through it:
1. Separate signal from noise — earnings, guidance, M&A, regulatory action,
   management change, product wins/failures, litigation and credit events
   move stocks. Recycled commentary, listicles, analyst-rating churn and
   market-wide chatter mostly don't.
2. Weigh materiality and recency — one guidance cut outweighs ten upbeat
   product reviews; the newest headlines matter most.
3. Check for stale news — if the story is old news already digested, the
   edge is gone: go neutral.
4. Consider what is already priced in. Good news that everyone expected is
   not bullish.

Signal rules:
- bullish: material positive developments the market is still absorbing.
- bearish: material negative developments, or hype with no substance behind it.
- neutral: mixed, immaterial or stale news, or too few headlines to tell.

Confidence scale (0-100): 80-100 one clear, material catalyst; 60-79 clear
direction, moderate materiality; 40-59 leaning; 10-39 mostly noise.

Hard rules:
- Reason ONLY from the headlines provided. Treat the newest date shown as
  the present day; do not use any knowledge of anything that happened after
  it. Do not invent facts, numbers or details beyond the headline text.
- Headlines are all you have: don't claim to know article contents.

Respond with JSON only, in exactly this schema:
{"signal": "bullish" | "bearish" | "neutral", "confidence": <0-100>,
 "reasoning": "<your read of the news flow, 2-4 sentences>"}"""
