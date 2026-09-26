"""Point-in-time news headlines — shared input for news-driven alpha models.

`recent_headlines` is the one place the point-in-time rules for news live:
only articles dated on or before `as_of`, inside the lookback window, with
a date (an undated article can't be proven public), deduped by title.
`NewsSnapshot` wraps those headlines for LLM analysts, mirroring
`FundamentalsSnapshot`: build once, hash it, render it into a prompt.

Like the fundamentals snapshot, `content_hash` and `render()` exclude
`as_of`: two dates that see the same headlines must produce the same prompt
(a cache hit), not two paid LLM calls.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from pydantic import BaseModel

from hedge_fund.data.protocol import DataClient
from hedge_fund.features.snapshot import InsufficientData

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_NEWS_LIMIT = 100


class Headline(BaseModel):
    title: str
    source: str
    date: str  # YYYY-MM-DD


def recent_headlines(
    ticker: str,
    as_of: str,
    data_client: DataClient,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    limit: int = DEFAULT_NEWS_LIMIT,
) -> list[Headline]:
    """Unique headlines public in the `lookback_days` up to `as_of`, newest first.

    Data-layer failures propagate (fail loud); an empty feed returns [].
    """
    end = _parse_date(as_of)
    start = end - timedelta(days=lookback_days)
    articles = data_client.get_news(
        ticker, as_of, start_date=start.isoformat(), limit=limit,
    )

    out: list[Headline] = []
    seen: set[str] = set()
    for a in articles:
        if not a.date or not a.title:
            continue
        published = _parse_date(a.date)
        if published > end or published < start:
            continue
        title = a.title.strip()
        if title and title not in seen:
            seen.add(title)
            out.append(Headline(title=title, source=a.source, date=published.isoformat()))
    out.sort(key=lambda h: h.date, reverse=True)
    return out


class NewsSnapshot(BaseModel):
    """What a news analyst may know about *ticker* as of *as_of*. Newest first."""

    ticker: str
    as_of: str
    lookback_days: int
    headlines: list[Headline]

    @property
    def content_hash(self) -> str:
        """Stable hash of the headlines — the LLM cache key. Excludes `as_of`."""
        canonical = self.model_dump_json(exclude={"as_of"})
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]

    def render(self) -> str:
        """Compact text block for the LLM prompt (no `as_of`, so cache-stable)."""
        lines = [
            f"Company: {self.ticker}",
            f"{len(self.headlines)} distinct headlines from the last "
            f"{self.lookback_days} days, newest first. All were public by their "
            "dates; treat the newest as the present.",
            "",
        ]
        lines.extend(f"{h.date} | {h.source} | {h.title}" for h in self.headlines)
        return "\n".join(lines)


def build_news_snapshot(
    ticker: str,
    as_of: str,
    data_client: DataClient,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    min_headlines: int = 3,
    limit: int = DEFAULT_NEWS_LIMIT,
) -> NewsSnapshot:
    """Build the point-in-time news snapshot for (ticker, as_of).

    Raises InsufficientData if fewer than `min_headlines` qualify — an empty
    feed is "no view", never a neutral one. Data-layer failures propagate.
    """
    headlines = recent_headlines(ticker, as_of, data_client, lookback_days, limit)
    if len(headlines) < min_headlines:
        raise InsufficientData(
            f"{ticker} as of {as_of}: only {len(headlines)} headline(s) in the "
            f"last {lookback_days}d (need {min_headlines})"
        )
    return NewsSnapshot(
        ticker=ticker, as_of=as_of, lookback_days=lookback_days, headlines=headlines,
    )


def _parse_date(s: str):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()
