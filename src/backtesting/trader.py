from __future__ import annotations

import logging

from .portfolio import Portfolio
from .types import ActionLiteral, Action
from src.tools.markets import is_a_share

logger = logging.getLogger(__name__)

# A-share price-limit percentages by board.
# Main board: ±10% | STAR (688/689) & ChiNext (300/301): ±20% | Beijing (.BJ): ±30%
_PRICE_LIMIT_MAIN = 0.10
_PRICE_LIMIT_STAR_CHINEXT = 0.20
_PRICE_LIMIT_BJ = 0.30


def _ashare_price_limit_pct(ticker: str) -> float:
    """Return the daily price-limit percentage for an A-share ticker."""

    code = ticker.split(".", 1)[0]  # 6-digit bare code
    suffix = ticker.split(".", 1)[1] if "." in ticker else ""
    if suffix == "BJ":
        return _PRICE_LIMIT_BJ
    if code.startswith(("688", "689")) or code.startswith(("300", "301")):
        return _PRICE_LIMIT_STAR_CHINEXT
    return _PRICE_LIMIT_MAIN


class TradeExecutor:
    """Executes trades against a Portfolio with Backtester-identical semantics.

    When the ticker is a Chinese A-share (detected via ``is_a_share``) the
    following rules are enforced in addition to the base logic:

    * **No short selling** – ``SHORT`` / ``COVER`` actions return 0.
    * **100-share lot size** – BUY/SELL quantities are rounded *down* to the
      nearest multiple of 100; if the result is 0 the trade is skipped.
    * **涨跌停 price-limit filter** – if *previous_close* is supplied and the
      current price exceeds the daily price-limit band, the trade is skipped.
    """

    _ashare_short_warned = False  # class-level guard so we log once

    def execute_trade(
        self,
        ticker: str,
        action: ActionLiteral,
        quantity: float,
        current_price: float,
        portfolio: Portfolio,
        *,
        previous_close: float | None = None,
    ) -> int:
        if quantity is None or quantity <= 0:
            return 0

        is_ashare = is_a_share(ticker)

        # --- A-share rule: no short selling -----------------------------
        if is_ashare:
            try:
                action_enum = Action(action) if not isinstance(action, Action) else action
            except Exception:
                action_enum = Action.HOLD
            if action_enum in (Action.SHORT, Action.COVER):
                if not TradeExecutor._ashare_short_warned:
                    logger.warning(
                        "Short selling is not supported for A-share tickers (%s); "
                        "SHORT/COVER orders will be skipped.",
                        ticker,
                    )
                    TradeExecutor._ashare_short_warned = True
                return 0

            # --- A-share rule: price-limit (涨跌停) filter --------------
            if previous_close is not None and previous_close > 0:
                limit_pct = _ashare_price_limit_pct(ticker)
                upper = previous_close * (1.0 + limit_pct)
                lower = previous_close * (1.0 - limit_pct)
                if current_price > upper or current_price < lower:
                    logger.debug(
                        "A-share %s price %.4f outside ±%.0f%% band [%.4f, %.4f] "
                        "(prev close %.4f) – skipping trade.",
                        ticker,
                        current_price,
                        limit_pct * 100,
                        lower,
                        upper,
                        previous_close,
                    )
                    return 0

            # --- A-share rule: 100-share lot rounding ------------------
            quantity = (int(quantity) // 100) * 100
            if quantity <= 0:
                return 0

        # Coerce to enum if strings provided
        try:
            action_enum = Action(action) if not isinstance(action, Action) else action
        except Exception:
            action_enum = Action.HOLD

        if action_enum == Action.BUY:
            return portfolio.apply_long_buy(ticker, int(quantity), float(current_price))
        if action_enum == Action.SELL:
            return portfolio.apply_long_sell(ticker, int(quantity), float(current_price))
        if action_enum == Action.SHORT:
            return portfolio.apply_short_open(ticker, int(quantity), float(current_price))
        if action_enum == Action.COVER:
            return portfolio.apply_short_cover(ticker, int(quantity), float(current_price))

        # hold or unknown action
        return 0


