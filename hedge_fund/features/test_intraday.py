"""IntradayContext — the day so far, rendered so quiet bars match."""

import pytest

from hedge_fund.data.models import CompanyNews, EarningsData, EarningsRecord, Price, PriceSnapshot
from hedge_fund.features.intraday import build_intraday_context, IntradayContext
from hedge_fund.fund.spec import TradingWindow
from hedge_fund.pipeline.clock import BarClock, PinnedQuotes


class DayClient:
    """A provider with minute history: bars for one day, a daily close
    before it, headlines, filings. The context never reads the bars itself;
    `PinnedQuotes` turns them into the quote at the bar, as the engine does."""

    def __init__(self, *, minute=None, closes=None, news=(), earnings=()):
        self.minute = minute or {}      # ticker -> {HH:MM -> close} on 2024-06-04
        self.closes = closes or {}      # ticker -> previous close
        self.news = list(news)
        self.earnings = list(earnings)

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        if interval == "minute":
            return [Price(open=p, close=p, high=p, low=p, volume=1, time=f"2024-06-04T{hm}:00-04:00")
                    for hm, p in sorted(self.minute.get(ticker, {}).items())]
        close = self.closes.get(ticker)
        return [] if close is None else [Price(open=close, close=close, high=close, low=close, volume=1,
                                               time="2024-06-03T00:00:00Z")]

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        return [n for n in self.news if n.ticker == ticker]

    def get_earnings_history(self, ticker, limit=12):
        return [e for e in self.earnings if e.ticker == ticker]


def _context(ticker, bar, data):
    return build_intraday_context(ticker, bar, PinnedQuotes(data, BarClock(data, 60, TradingWindow()), bar))


def _news(when, title, source="Wire"):
    return CompanyNews(ticker="TEST", title=title, source=source, date=when)


def _filing(when, window="PRE_MARKET", revenue="BEAT", eps="MISS"):
    return EarningsRecord(ticker="TEST", report_period="2024-03-31", source_type="8-K", fiscal_period="Q1 2024",
                          filing_date=when[:10], filing_datetime=when, filing_window=window,
                          quarterly=EarningsData(revenue_surprise=revenue, eps_surprise=eps))


def test_two_quiet_bars_render_the_same_block():
    data = DayClient(minute={"TEST": {"09:30": 101.0, "09:31": 101.2, "09:32": 101.1},
                             "SPY": {"09:30": 500.0, "09:31": 500.5, "09:32": 500.4}},
                     closes={"TEST": 100.0, "SPY": 500.0},
                     news=[_news("2024-06-04T13:20:00Z", "Early piece")])  # 09:20 ET: before both bars
    first = _context("TEST", "2024-06-04T09:31:00", data)
    second = _context("TEST", "2024-06-04T09:32:00", data)
    assert first.render() == second.render() and first.content_hash == second.content_hash
    assert "09:31" not in first.render() and "09:32" not in second.render()  # the bar's own time never shows
    assert first.render() == (
        "Since the previous close:\n"
        "  Price: up 1–2%; ahead of the market by 1–2%\n"
        "  Earnings: none released\n"
        "  Headlines (1, newest last):\n"
        "    09:20 ET  Wire: Early piece"
    )


def test_a_headline_a_filing_or_a_band_crossing_changes_the_block():
    # The price at a bar is the close of the minute before it (the bar's own
    # open at the window's first bar), as `BarClock` marks it.
    data = DayClient(minute={"TEST": {"09:30": 100.2, "09:34": 100.3, "09:39": 102.5},
                             "SPY": {"09:30": 500.0, "09:34": 500.0, "09:39": 500.0}},
                     closes={"TEST": 100.0, "SPY": 500.0},
                     news=[_news("2024-06-04T13:33:00Z", "Guidance raised", "Reuters"),
                           _news("2024-06-03T21:00:00Z", "After the bell yesterday"),
                           _news("2024-06-03T19:00:00Z", "Before yesterday's close: not since the previous close")],
                     earnings=[_filing("2024-06-04T07:30:00-04:00")])
    at_open = _context("TEST", "2024-06-04T09:30:00", data)
    text = at_open.render()
    assert "Price: flat (within 0.5%); in line with the market" in text
    assert "Earnings: Q1 2024 results filed at 07:30 ET, pre market (8-K): revenue BEAT, EPS MISS" in text
    assert "Jun 3 17:00 ET  Wire: After the bell yesterday" in text and "not since" not in text
    assert "Guidance raised" not in text  # 09:33, after this bar
    later = _context("TEST", "2024-06-04T09:35:00", data)
    assert "09:33 ET  Reuters: Guidance raised" in later.render() and later.content_hash != at_open.content_hash
    crossed = _context("TEST", "2024-06-04T09:40:00", data)
    assert "Price: up 2–3%; ahead of the market by 2–3%" in crossed.render()


def test_blind_render_keeps_bands_and_surprise_and_drops_names_and_clocks():
    data = DayClient(minute={"TEST": {"09:30": 94.0}, "SPY": {"09:30": 490.0}},  # −6% vs −2%
                     closes={"TEST": 100.0, "SPY": 500.0},
                     news=[_news("2024-06-04T13:00:00Z", "TEST Corp plunges on results")],
                     earnings=[_filing("2024-06-04T07:30:00-04:00", revenue="MISS", eps="MISS")])
    context = _context("TEST", "2024-06-04T09:30:00", data)
    blind = context.render(blind=True)
    assert blind == (
        "Since the previous close:\n"
        "  Price: down more than 5%; behind the market by 3–5%\n"
        "  Earnings: released (revenue MISS, EPS MISS)"
    )
    assert "TEST" not in blind and "07:30" not in blind and "Headlines" not in blind


def test_before_the_first_print_and_without_a_market_read():
    data = DayClient(minute={"TEST": {"09:31": 100.0}}, closes={"TEST": 100.0})
    early = _context("TEST", "2024-06-04T09:30:00", data)
    assert "Price: no print yet today" in early.render() and "market" not in early.render()
    printed = _context("TEST", "2024-06-04T09:31:00", data)
    assert "Price: flat (within 0.5%)\n" in printed.render()  # SPY has no bars: no relative clause
    with pytest.raises(ValueError, match="daily session"):
        _context("TEST", "2024-06-04", data)


class LiveClient(DayClient):
    """Financial Datasets, live: daily bars and a quote; no minute history."""

    def __init__(self, quotes, **kwargs):
        super().__init__(**kwargs)
        self.quotes = quotes  # ticker -> PriceSnapshot

    def get_prices(self, ticker, start_date, end_date, interval="day", interval_multiplier=1):
        if interval != "day":
            raise AssertionError(f"{interval} bars were asked for; the provider has none")
        return super().get_prices(ticker, start_date, end_date)

    def get_snapshot(self, ticker):
        return self.quotes.get(ticker)


def test_live_the_move_is_read_from_the_quote_and_yesterdays_print_is_no_print():
    data = LiveClient(
        {"TEST": PriceSnapshot(ticker="TEST", price=103.0, time="2024-06-04T13:40:02Z"),  # 09:40 ET today
         "SPY": PriceSnapshot(ticker="SPY", price=505.0, time="2024-06-03T20:00:00Z")},   # last trade: yesterday
        closes={"TEST": 100.0, "SPY": 500.0},
    )
    text = build_intraday_context("TEST", "2024-06-04T09:40:00", data).render()
    assert "Price: up 3–5%\n" in text  # the market has not printed today: no relative clause


def test_headlines_are_capped_to_the_newest():
    news = [_news(f"2024-06-04T13:{i:02d}:00Z", f"Item {i}") for i in range(20)]
    context = IntradayContext(ticker="TEST", as_of="2024-06-04T09:30:00", move_pct=None, market_pct=None,
                              earnings=None, headlines=_context(
                                  "TEST", "2024-06-04T10:00:00", DayClient(news=news)).headlines)
    text = context.render()
    assert "Headlines (20, newest last)" in text and "Item 19" in text and "Item 10" in text and "Item 9" not in text
