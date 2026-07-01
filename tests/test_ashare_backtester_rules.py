"""Tests for A-share trading rules in the new backtester.

Covers the 4 rules added for Chinese A-share tickers:
  1. T+1 settlement – shares bought today can't be sold until next day.
  2. 100-share lot rounding – quantities round down to nearest 100.
  3. No short selling – SHORT/COVER return 0, no exception.
  4. 涨跌停 price-limit filter – ±10% main / ±20% STAR+ChiNext / ±30% BJ.

These tests use synthetic data only — no akshare/API calls.
"""

from __future__ import annotations

import pytest

from src.backtesting.portfolio import Portfolio
from src.backtesting.trader import TradeExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MAIN_BOARD = "600519.SH"   # Kweichow Moutai – main board, ±10%
STAR_BOARD = "688001.SH"   # STAR Market, ±20%
CHINEXT = "300001.SZ"      # ChiNext, ±20%
BJ_BOARD = "830799.BJ"     # Beijing Stock Exchange, ±30%
US_TICKER = "AAPL"


@pytest.fixture()
def portfolio() -> Portfolio:
    return Portfolio(
        tickers=[MAIN_BOARD, STAR_BOARD, CHINEXT, BJ_BOARD, US_TICKER],
        initial_cash=1_000_000.0,
        margin_requirement=0.5,
    )


@pytest.fixture()
def executor() -> TradeExecutor:
    # Reset the class-level "warned" flag so each test is independent.
    TradeExecutor._ashare_short_warned = False
    return TradeExecutor()


# ---------------------------------------------------------------------------
# Rule 1: T+1 settlement
# ---------------------------------------------------------------------------

class TestTPlus1Settlement:
    def test_shares_bought_today_cannot_be_sold_same_day(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Buy 100 shares then immediately try to sell → should be blocked."""

        bought = executor.execute_trade(MAIN_BOARD, "buy", 100, 50.0, portfolio)
        assert bought == 100

        # Attempt same-day sell of the 100 shares just bought → blocked (T+1)
        sold = executor.execute_trade(MAIN_BOARD, "sell", 100, 55.0, portfolio)
        assert sold == 0

    def test_shares_sellable_after_advance_day(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """After advance_day(), yesterday's buys become sellable."""

        executor.execute_trade(MAIN_BOARD, "buy", 200, 50.0, portfolio)
        portfolio.advance_day()

        sold = executor.execute_trade(MAIN_BOARD, "sell", 100, 55.0, portfolio)
        assert sold == 100

    def test_partial_sell_after_advance_day(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Can sell some but not more than the unlocked amount."""

        executor.execute_trade(MAIN_BOARD, "buy", 300, 50.0, portfolio)
        portfolio.advance_day()

        # Sell 200 of the 300 unlocked shares
        sold = executor.execute_trade(MAIN_BOARD, "sell", 200, 55.0, portfolio)
        assert sold == 200

        # Remaining unlocked = 100, locked = 0 → can sell 100 more
        sold2 = executor.execute_trade(MAIN_BOARD, "sell", 200, 55.0, portfolio)
        assert sold2 == 100

    def test_locked_field_tracked_correctly(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Verify locked_long is set on buy and cleared by advance_day."""

        executor.execute_trade(MAIN_BOARD, "buy", 100, 50.0, portfolio)
        snap = portfolio.get_snapshot()
        assert snap["positions"][MAIN_BOARD]["locked_long"] == 100

        portfolio.advance_day()
        snap = portfolio.get_snapshot()
        assert snap["positions"][MAIN_BOARD]["locked_long"] == 0


# ---------------------------------------------------------------------------
# Rule 2: 100-share lot rounding
# ---------------------------------------------------------------------------

class TestLotSizeRounding:
    def test_buy_rounds_down_to_100(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """150 → 100 executed."""

        bought = executor.execute_trade(MAIN_BOARD, "buy", 150, 50.0, portfolio)
        assert bought == 100

    def test_buy_below_100_returns_zero(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """50 rounds down to 0 → skip."""

        bought = executor.execute_trade(MAIN_BOARD, "buy", 50, 50.0, portfolio)
        assert bought == 0

    def test_sell_rounds_down_to_100(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Set up 200 sellable shares, then try to sell 150 → 100."""

        executor.execute_trade(MAIN_BOARD, "buy", 200, 50.0, portfolio)
        portfolio.advance_day()

        sold = executor.execute_trade(MAIN_BOARD, "sell", 150, 55.0, portfolio)
        assert sold == 100

    def test_us_ticker_not_rounded(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """US tickers are not subject to lot-size rounding."""

        bought = executor.execute_trade(US_TICKER, "buy", 10, 100.0, portfolio)
        assert bought == 10


# ---------------------------------------------------------------------------
# Rule 3: No short selling for A-shares
# ---------------------------------------------------------------------------

class TestNoShortSelling:
    def test_short_returns_zero_no_exception(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        sold = executor.execute_trade(MAIN_BOARD, "short", 100, 50.0, portfolio)
        assert sold == 0

    def test_cover_returns_zero_no_exception(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        sold = executor.execute_trade(MAIN_BOARD, "cover", 100, 50.0, portfolio)
        assert sold == 0

    def test_us_ticker_short_still_works(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """US tickers should still be shortable."""

        sold = executor.execute_trade(US_TICKER, "short", 10, 100.0, portfolio)
        assert sold == 10


# ---------------------------------------------------------------------------
# Rule 4: 涨跌停 price-limit filter
# ---------------------------------------------------------------------------

class TestPriceLimitFilter:
    def test_main_board_above_10pct_skipped(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Main board ±10%: +15% from prev close → skip."""

        prev_close = 100.0
        current = 115.0  # +15%
        bought = executor.execute_trade(
            MAIN_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 0

    def test_main_board_within_10pct_executes(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Main board ±10%: +8% → OK."""

        prev_close = 100.0
        current = 108.0  # +8%
        bought = executor.execute_trade(
            MAIN_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 100

    def test_star_board_15pct_executes(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """STAR board ±20%: +15% from prev close → within band → executes."""

        prev_close = 100.0
        current = 115.0  # +15% < 20%
        bought = executor.execute_trade(
            STAR_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 100

    def test_star_board_above_20pct_skipped(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """STAR board ±20%: +25% from prev close → skip."""

        prev_close = 100.0
        current = 125.0  # +25% > 20%
        bought = executor.execute_trade(
            STAR_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 0

    def test_chinext_15pct_executes(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """ChiNext ±20%: +15% → executes."""

        prev_close = 100.0
        current = 115.0
        bought = executor.execute_trade(
            CHINEXT, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 100

    def test_bj_board_25pct_executes(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Beijing ±30%: +25% → executes."""

        prev_close = 100.0
        current = 125.0  # +25% < 30%
        bought = executor.execute_trade(
            BJ_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 100

    def test_bj_board_above_30pct_skipped(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Beijing ±30%: +35% → skip."""

        prev_close = 100.0
        current = 135.0
        bought = executor.execute_trade(
            BJ_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 0

    def test_price_limit_down_skipped(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """Main board: -15% from prev close → skip (limit down)."""

        prev_close = 100.0
        current = 85.0  # -15%
        bought = executor.execute_trade(
            MAIN_BOARD, "buy", 100, current, portfolio, previous_close=prev_close
        )
        assert bought == 0

    def test_no_previous_close_no_filter(
        self, portfolio: Portfolio, executor: TradeExecutor
    ) -> None:
        """If previous_close is None (e.g. first day), price-limit is skipped."""

        bought = executor.execute_trade(
            MAIN_BOARD, "buy", 100, 200.0, portfolio, previous_close=None
        )
        assert bought == 100
