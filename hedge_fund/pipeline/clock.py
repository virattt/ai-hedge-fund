"""The clock — what the engine must know about time, per cadence.

`advance` asks three things of time: whether a session may be looked at yet,
which session's information a decision executing now was made from, and
what everything is worth at a session. A daily fund answers with completed
New York dates and daily closes; a minute fund with bar boundaries and the
prices at them. The engine does not know which it is holding.

    DailyClock  completed dates, previous calendar day, exact daily closes
    LiveClock   real-time snapshots taken at the boundary — a minute fund's
                paper runner
    BarClock    historical minute bars, for a provider that serves them;
                backtests replay a minute fund at daily closes instead

`clock_for(spec, data, live)` picks one from the mandate.

`PinnedQuotes` hands the clock's print to the analysts: a data client whose
quote at a session is what the clock marks that session at, so an analyst
reads the same price the engine executes with and never the wire.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Callable, Protocol

from hedge_fund.data.bars import bar_time, current_bar, is_intraday, previous_bar, session_date
from hedge_fund.data.models import Price, PriceSnapshot
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import completed_through, NEW_YORK, previous_day
from hedge_fund.fund.spec import FundSpec, TradingWindow


@dataclass(frozen=True)
class Marked:
    """Prices at a session, and — when they came from live prints — the
    moment each print was, so a stale name is visible in the record."""

    prices: dict[str, float]
    times: dict[str, str] | None = None


class Clock(Protocol):
    def is_complete(self, session: str) -> bool:
        """May the engine look at *session* yet?"""
        ...

    def previous(self, session: str) -> str:
        """The information cutoff for a decision executing at *session*."""
        ...

    def marks(self, tickers: list[str], session: str) -> Marked:
        """A finite, positive price for every name at exactly *session*; raises otherwise."""
        ...

    def session_date(self, session: str) -> str:
        """The New York date *session* falls on."""
        ...


class DailyClock:
    """Today's behaviour, unchanged: sessions are completed NY dates."""

    def __init__(self, data: DataClient) -> None:
        self._data = data

    def is_complete(self, session: str) -> bool:
        return session <= completed_through()

    def previous(self, session: str) -> str:
        return previous_day(session)

    def marks(self, tickers: list[str], session: str) -> Marked:
        return Marked(prices=exact_marks(tickers, session, self._data))

    def session_date(self, session: str) -> str:
        return session


def exact_marks(tickers: list[str], session: str, data_client: DataClient) -> dict[str, float]:
    """Require a finite, positive close for every name on the exact session."""
    if session > completed_through():
        raise ValueError(f"{session}: daily prices are not yet complete")
    marks: dict[str, float] = {}
    for ticker in sorted(set(tickers)):
        bars = data_client.get_prices(ticker, session, session)
        matches = [bar for bar in bars if bar.time[:10] == session]
        if not matches:
            raise ValueError(f"{ticker}: missing close on {session}; cannot value the book or execute")
        close = max(matches, key=lambda bar: bar.time).close
        _positive(ticker, session, close)
        marks[ticker] = close
    return marks


class BarClock:
    """A minute fund over history: marks come from 1-minute bars. The price at
    a boundary is the close of the last minute bar that ended by then; at the
    first bar of a window with nothing before it, that bar's open. Bars are
    fetched once per (ticker, day) and kept."""

    def __init__(self, data: DataClient, interval_seconds: int, window: TradingWindow) -> None:
        self._data = data
        self._interval = interval_seconds
        self._window = window
        self._days: dict[tuple[str, str], list[tuple[str, Price]]] = {}

    def is_complete(self, session: str) -> bool:
        return session_date(session) <= completed_through()

    def previous(self, session: str) -> str:
        return previous_bar(session, self._interval, self._window)

    def session_date(self, session: str) -> str:
        return session_date(session)

    def marks(self, tickers: list[str], session: str) -> Marked:
        if not self.is_complete(session):
            raise ValueError(f"{session}: minute bars are not yet complete")
        prices: dict[str, float] = {}
        for ticker in sorted(set(tickers)):
            price = self._price_at(ticker, session)
            _positive(ticker, session, price)
            prices[ticker] = price
        return Marked(prices=prices)

    def _price_at(self, ticker: str, session: str) -> float:
        day = session_date(session)
        bars = self._day(ticker, day)
        before = [bar for key, bar in bars if key < session]
        if before:
            return before[-1].close
        at = [bar for key, bar in bars if key == session]
        if at:
            return at[0].open
        raise ValueError(f"{ticker}: no minute bar at or before {session}; cannot value the book or execute")

    def _day(self, ticker: str, day: str) -> list[tuple[str, Price]]:
        key = (ticker, day)
        if key not in self._days:
            bars = self._data.get_prices(ticker, day, day, interval="minute", interval_multiplier=1)
            keyed = sorted((bar_key(bar.time), bar) for bar in bars)
            self._days[key] = [(k, bar) for k, bar in keyed if k[:10] == day]
        return self._days[key]


def bar_key(time: str) -> str:
    """A bar's timestamp as a NY-local session key, whatever zone it came in."""
    moment = datetime.fromisoformat(time.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NEW_YORK)
    return moment.astimezone(NEW_YORK).strftime("%Y-%m-%dT%H:%M:%S")


class LiveClock:
    """A minute fund in the present: marks are the latest prints, taken once
    per boundary. The runner calls `observe` at the boundary with every name
    it will need; `marks` serves those and fetches any it did not foresee."""

    def __init__(
        self, data: DataClient, interval_seconds: int, window: TradingWindow,
        *, now: Callable[[], datetime] = lambda: datetime.now(NEW_YORK),
    ) -> None:
        self._data = data
        self._interval = interval_seconds
        self._window = window
        self._now = now
        self._session: str | None = None
        self._prints: dict[str, PriceSnapshot] = {}

    def is_complete(self, session: str) -> bool:
        return bar_time(session) <= self._now()

    def previous(self, session: str) -> str:
        return previous_bar(session, self._interval, self._window)

    def session_date(self, session: str) -> str:
        return session_date(session)

    def current(self) -> str | None:
        return current_bar(self._now(), self._interval, self._window)

    def observe(self, tickers: list[str], session: str) -> dict[str, PriceSnapshot]:
        """Take the prints for *session*: all names together, now."""
        if session != self._session:
            self._session, self._prints = session, {}
        missing = sorted(set(tickers) - set(self._prints))
        if missing:
            with ThreadPoolExecutor(max_workers=min(8, len(missing))) as pool:
                for ticker, snapshot in zip(missing, pool.map(self._data.get_snapshot, missing)):
                    if snapshot is None:
                        raise ValueError(f"{ticker}: no quote; cannot value the book or execute")
                    self._prints[ticker] = snapshot
        return {t: self._prints[t] for t in tickers}

    def marks(self, tickers: list[str], session: str) -> Marked:
        if not self.is_complete(session):
            raise ValueError(f"{session}: that bar has not closed yet")
        prints = self.observe(sorted(set(tickers)), session)
        for ticker, snapshot in prints.items():
            _positive(ticker, session, snapshot.price)
        return Marked(
            prices={t: s.price for t, s in prints.items()},
            times={t: s.time for t, s in prints.items()},
        )


def clock_for(spec: FundSpec, data: DataClient, *, live: bool = False) -> Clock:
    """The clock a mandate runs on: daily closes, or bars — historical for
    a backtest, live prints for the paper runner."""
    if not spec.is_intraday:
        return DailyClock(data)
    if live:
        return LiveClock(data, spec.interval_seconds, spec.window)
    return BarClock(data, spec.interval_seconds, spec.window)


class PinnedQuotes:
    """*data*, with its quote pinned to the clock's print at *session*.

    An analyst asked at a session is handed this instead of the wire. Whatever
    it asks the price of, it reads what the engine marks that session at: the
    boundary's print live, the bar's close over history, the day's close for a
    daily fund. Nothing from after the session, and no second fetch of a name
    the clock has already seen. A name the clock cannot price at the session
    has no quote. Everything else passes through to *data*."""

    def __init__(self, data: DataClient, clock: Clock, session: str) -> None:
        self._data = data
        self._clock = clock
        self._session = session

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        try:
            marked = self._clock.marks([ticker], self._session)
        except ValueError:
            return None
        when = (marked.times or {}).get(ticker) or _session_stamp(self._session)
        return PriceSnapshot(ticker=ticker, price=marked.prices[ticker], time=when)

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        return self._data.get_prices(ticker, start_date, end_date, **kwargs)

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        return self._data.get_financial_metrics(ticker, end_date, period, limit)

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        return self._data.get_news(ticker, end_date, start_date, limit)

    def get_insider_trades(self, ticker, end_date, start_date=None, limit=1000):
        return self._data.get_insider_trades(ticker, end_date, start_date, limit)

    def get_company_facts(self, ticker):
        return self._data.get_company_facts(ticker)

    def get_earnings(self, ticker):
        return self._data.get_earnings(ticker)

    def get_earnings_history(self, ticker, limit=12):
        return self._data.get_earnings_history(ticker, limit)

    def get_market_cap(self, ticker, end_date):
        return self._data.get_market_cap(ticker, end_date)


def _session_stamp(session: str) -> str:
    """When a session's print was, absent a print time: the bar itself, or
    the day's 4pm close."""
    if is_intraday(session):
        return bar_time(session).isoformat()
    return datetime.fromisoformat(session).replace(hour=16, tzinfo=NEW_YORK).isoformat()


def execution_policy(session: str) -> str:
    return "next_bar" if is_intraday(session) else "next_close"


def _positive(ticker: str, session: str, price: float) -> None:
    if not isfinite(price) or price <= 0:
        raise ValueError(f"{ticker}: price at {session} must be finite and positive, got {price}")
