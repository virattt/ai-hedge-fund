"""What has happened since the previous close — the block a minute fund's
analysts read under the fundamentals.

The fundamentals snapshot is filed data and moves a few times a year. An
analyst asked every bar needs the day: what the stock has done, whether
results landed, what has been written. `IntradayContext` gathers those
three for one (ticker, bar) and renders them so that two quiet bars render
*identically*: the move is bucketed, headlines are listed by the minute
they landed, and the bar's own time never appears. An unchanged block means
an unchanged prompt, which means the prompt cache answers and no model is
called. A new headline, a filing, or the price crossing a band changes the
block, and only then is the analyst asked again.

Everything is point-in-time by construction: the price is the quote the
data client gives at the bar (the engine pins it to the clock's print, so it
is the bar's own and never the wire's), headlines are dated up to the bar,
filings time-stamped up to the bar. A backtest at a bar in 2024 sees exactly
what the day had shown by then. No minute history is read here: Financial
Datasets has none, and a live fund needs none.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from hedge_fund.data.bars import bar_time, is_intraday, session_date
from hedge_fund.data.models import EarningsRecord
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import NEW_YORK

MARKET = "SPY"           # the market the move is read against
_CLOSE = time(16, 0)     # the previous close, for "since the previous close"
_HEADLINES = 10          # the most recent this many headlines are asked for and shown

# Move bands, in percent. The edges are where the prompt changes.
_BANDS = [0.5, 1.0, 2.0, 3.0, 5.0]


@dataclass(frozen=True)
class Headline:
    when: datetime      # aware, New York
    source: str
    title: str


@dataclass(frozen=True)
class IntradayContext:
    ticker: str
    as_of: str                       # the bar; never rendered
    move_pct: float | None           # since the previous close, in percent
    market_pct: float | None         # the market's, same basis
    earnings: EarningsRecord | None  # released since the previous close
    headlines: list[Headline] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.render().encode()).hexdigest()[:16]

    def render(self, blind: bool = False) -> str:
        """The block. Blind prompts keep the bands and the surprise, which
        name no company and no date, and drop the headlines and the clock."""
        lines = ["Since the previous close:"]
        lines.append(f"  Price: {_move_phrase(self.move_pct)}{_relative_phrase(self.move_pct, self.market_pct)}")
        lines.append(f"  Earnings: {_earnings_phrase(self.earnings, blind)}")
        if blind:
            return "\n".join(lines)
        if not self.headlines:
            lines.append("  Headlines: none")
        else:
            lines.append(f"  Headlines ({len(self.headlines)}, newest last):")
            day = session_date(self.as_of)
            for h in self.headlines[-_HEADLINES:]:
                stamp = h.when.strftime("%H:%M") if h.when.date().isoformat() == day else h.when.strftime("%b %-d %H:%M")
                lines.append(f"    {stamp} ET  {h.source}: {h.title}")
        return "\n".join(lines)


def build_intraday_context(ticker: str, as_of: str, data_client: DataClient,
                           *, market: str = MARKET) -> IntradayContext:
    """Gather the day for one ticker at one bar. Data-layer errors propagate."""
    if not is_intraday(as_of):
        raise ValueError(f"{as_of} is a daily session; intraday context is for bars")
    at = bar_time(as_of)
    since = _previous_close(at)
    day = session_date(as_of)
    return IntradayContext(
        ticker=ticker,
        as_of=as_of,
        move_pct=_move(data_client, ticker, at, since),
        market_pct=_move(data_client, market, at, since),
        earnings=_released(data_client, ticker, since, at),
        headlines=_headlines(data_client, ticker, since, at, day),
    )


# ---------------------------------------------------------------------------
# Gathering
# ---------------------------------------------------------------------------

def _previous_close(at: datetime) -> datetime:
    """4pm New York on the last weekday before *at*'s day. Holidays are not
    consulted: a close that did not happen only widens the window."""
    day = at.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return datetime.combine(day, _CLOSE, tzinfo=NEW_YORK)


def _move(data: DataClient, ticker: str, at: datetime, since: datetime) -> float | None:
    """Percent change from the close before *since*'s day ended to the quote
    at the bar. None until the day has printed: a quote from an earlier day
    is the previous session's last trade, not today's."""
    quote = data.get_snapshot(ticker)
    if quote is None or _aware(quote.time).date() < at.date():
        return None
    now = quote.price
    closes = data.get_prices(ticker, (since.date() - timedelta(days=7)).isoformat(), since.date().isoformat())
    before = [b for b in closes if b.time[:10] <= since.date().isoformat()]
    if not before:
        return None
    last = max(before, key=lambda b: b.time).close
    if not last or last <= 0:
        return None
    return (now / last - 1) * 100


def _released(data: DataClient, ticker: str, since: datetime, at: datetime) -> EarningsRecord | None:
    """The newest filing time-stamped in (since, at]; the 8-K is what lands
    first, so the 8-K is what the analyst hears about."""
    hits = []
    for record in data.get_earnings_history(ticker, limit=6):
        stamp = record.filing_datetime or record.filing_date
        if stamp is None:
            continue
        when = _aware(stamp)
        if since < when <= at:
            hits.append((when, record))
    if not hits:
        return None
    return max(hits, key=lambda pair: pair[0])[1]


def _headlines(data: DataClient, ticker: str, since: datetime, at: datetime, day: str) -> list[Headline]:
    """The newest headlines, kept to those that landed in (since, at]."""
    items = data.get_news(ticker, end_date=day, start_date=since.date().isoformat(), limit=_HEADLINES)
    out = []
    for item in items:
        if item.date is None:
            continue
        when = _aware(item.date)
        if since < when <= at:
            out.append(Headline(when=when, source=item.source, title=item.title.strip()))
    return sorted(out, key=lambda h: (h.when, h.title))


def _aware(stamp: str) -> datetime:
    """Any timestamp the API returns, as an aware New York datetime. A bare
    date is taken as that day's close (the earliest a filing dated by day
    can be known not to have moved the session yet is unknowable; the close
    is the conservative reading)."""
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        if len(stamp) == 10:
            moment = datetime.combine(moment.date(), _CLOSE)
        moment = moment.replace(tzinfo=NEW_YORK)
    return moment.astimezone(NEW_YORK)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _band(pct: float) -> str:
    size = abs(pct)
    low = 0.0
    for edge in _BANDS:
        if size < edge:
            return f"{_edge(low)}–{_edge(edge)}%" if low else f"under {_edge(edge)}%"
        low = edge
    return f"more than {_edge(low)}%"


def _edge(value: float) -> str:
    return f"{value:g}"


def _move_phrase(pct: float | None) -> str:
    if pct is None:
        return "no print yet today"
    if abs(pct) < _BANDS[0]:
        return f"flat (within {_edge(_BANDS[0])}%)"
    return f"{'up' if pct > 0 else 'down'} {_band(pct)}"


def _relative_phrase(pct: float | None, market: float | None) -> str:
    if pct is None or market is None:
        return ""
    gap = pct - market
    if abs(gap) < _BANDS[0]:
        return "; in line with the market"
    return f"; {'ahead of' if gap > 0 else 'behind'} the market by {_band(gap)}"


def _earnings_phrase(record: EarningsRecord | None, blind: bool) -> str:
    if record is None:
        return "none released"
    data = record.quarterly or record.annual
    parts = []
    if data is not None:
        if data.revenue_surprise:
            parts.append(f"revenue {data.revenue_surprise}")
        if data.eps_surprise:
            parts.append(f"EPS {data.eps_surprise}")
    surprise = ", ".join(parts) if parts else "results released; no estimate to compare against"
    if blind:
        return f"released ({surprise})"
    window = f", {record.filing_window.lower().replace('_', ' ')}" if record.filing_window else ""
    when = _aware(record.filing_datetime or record.filing_date).strftime("%H:%M ET")
    period = record.fiscal_period or record.report_period
    return f"{period} results filed at {when}{window} ({record.source_type}): {surprise}"
