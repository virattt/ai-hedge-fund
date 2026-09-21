"""News sentiment alpha model — FinBERT over recent company headlines.

Forms a view from the tone of the last few days of news: bullish when
headlines skew positive, bearish when they skew negative. Each headline is
scored in [-1, +1] as P(positive) - P(negative) by a finance-tuned
classifier (ProsusAI/finbert by default) and the view is the mean score.

Like every quant model it only forms a *view*; sizing and timing belong to
portfolio construction.

Design notes:
- Point-in-time: only articles dated on or before `date`, inside the
  lookback window, are used. Undated articles are dropped (can't prove they
  were public).
- Too little news abstains (value 0.0, metadata.abstained=True) — the same
  convention as LLMAgent. An empty feed is "no view", never "neutral view".
- Data-layer errors propagate (fail loud); a missing FinBERT dependency
  raises ImportError with the install command instead of silently abstaining.
- FinBERT (`transformers` + `torch`) is an optional, lazily imported
  dependency:  pip install transformers torch
"""

from __future__ import annotations

from typing import Callable

from hedge_fund.data.protocol import DataClient
from hedge_fund.features.news import recent_headlines
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

# Scores a batch of headlines -> one score in [-1, +1] per headline.
Scorer = Callable[[list[str]], list[float]]

_DEFAULT_MODEL = "ProsusAI/finbert"


class NewsSentimentModel(QuantModel):
    """Long on positive news flow, short on negative.

    `predict(ticker, date)` averages FinBERT scores over the unique headlines
    published in the `lookback_days` up to and including `date`. Fewer than
    `min_articles` headlines -> abstain.

    `scorer` lets callers (and tests) inject any headline scorer; by default
    FinBERT is loaded lazily on first use.
    """

    def __init__(
        self,
        *,
        lookback_days: int = 7,
        min_articles: int = 3,
        news_limit: int = 100,
        hf_model: str = _DEFAULT_MODEL,
        scorer: Scorer | None = None,
    ) -> None:
        self._lookback_days = lookback_days
        self._min_articles = min_articles
        self._news_limit = news_limit
        self._hf_model = hf_model
        self._scorer = scorer
        # Headline -> score. predict runs once per trading day in a backtest
        # and windows overlap, so each headline is only scored once.
        self._scores: dict[str, float] = {}

    @property
    def name(self) -> str:
        return "news_sentiment"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        titles = [
            h.title for h in recent_headlines(
                ticker, date, data_client, self._lookback_days, self._news_limit,
            )
        ]

        if len(titles) < self._min_articles:
            return self._abstain(
                ticker, date,
                f"only {len(titles)} headline(s) in the last "
                f"{self._lookback_days}d (need {self._min_articles})",
            )

        scores = self._score(titles)
        mean = sum(scores) / len(scores)
        positive = sum(1 for s in scores if s > 0.1)
        negative = sum(1 for s in scores if s < -0.1)
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=self._normalize_to_signal(mean),
            reasoning=(
                f"{len(scores)} headlines over {self._lookback_days}d: "
                f"{positive} positive, {negative} negative, "
                f"mean sentiment {mean:+.2f}"
            ),
            components={"mean_sentiment": mean},
            metadata={
                "articles": len(scores),
                "positive": positive,
                "negative": negative,
                "lookback_days": self._lookback_days,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _abstain(self, ticker: str, date: str, why: str) -> Signal:
        return Signal(
            model_name=self.name, ticker=ticker, date=date, value=0.0,
            reasoning=f"abstained: {why}", metadata={"abstained": True},
        )

    def _score(self, titles: list[str]) -> list[float]:
        fresh = [t for t in titles if t not in self._scores]
        if fresh:
            if self._scorer is None:
                self._scorer = _finbert_scorer(self._hf_model)
            for title, score in zip(fresh, self._scorer(fresh)):
                self._scores[title] = self._safe_float(score)
        return [self._scores[t] for t in titles]


def _finbert_scorer(hf_model: str) -> Scorer:
    """Build a FinBERT headline scorer. Imports lazily — heavy optional deps."""
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "NewsSentimentModel needs FinBERT's optional dependencies: "
            "pip install transformers torch"
        ) from exc

    classifier = pipeline("text-classification", model=hf_model, top_k=None)

    def score(titles: list[str]) -> list[float]:
        out = classifier(titles, truncation=True)
        # top_k=None -> per headline, a list of {label, score} over all classes
        return [_label_score(probs) for probs in out]

    return score


def _label_score(probs: list[dict]) -> float:
    """P(positive) - P(negative) from a per-class probability list."""
    by_label = {p["label"].lower(): p["score"] for p in probs}
    return by_label.get("positive", 0.0) - by_label.get("negative", 0.0)

