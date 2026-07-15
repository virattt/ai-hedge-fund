"""Cash-constrained, daily mark-to-market portfolio ledger for backtests."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from math import floor
from typing import Any, Literal

from v2.backtesting.models import PortfolioLedgerEntry, PositionSnapshot, Trade


Direction = Literal["long", "short"]


@dataclass(frozen=True)
class TradeIntent:
    """An alpha-triggered entry with a known mechanical exit date."""

    ticker: str
    direction: Direction
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    holding_days: int
    reasoning: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _OpenPosition:
    ticker: str
    direction: Direction
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    initial_notional: float
    holding_days: int
    reasoning: str | None
    metadata: dict[str, Any]

    def unrealized_pnl(self, market_price: float) -> float:
        price_change = market_price - self.entry_price
        sign = 1.0 if self.direction == "long" else -1.0
        return round(sign * self.shares * price_change, 2)

    def equity_value(self, market_price: float) -> float:
        if self.direction == "long":
            return round(self.shares * market_price, 2)
        # Shorts are fully collateralized in this harness. Their capital value
        # is the reserved entry notional plus mark-to-market P&L.
        return round(self.initial_notional + self.unrealized_pnl(market_price), 2)


class PortfolioLedger:
    """Execute trade intents against one shared pool of capital.

    Entries and exits fill at the supplied daily closes. Long positions spend
    their notional; shorts reserve the same notional as full collateral. When
    several signals arrive on the same day, available cash is split equally so
    ticker ordering cannot decide which signals receive capital.
    """

    def __init__(self, *, capital: float, per_trade: float) -> None:
        if capital <= 0:
            raise ValueError("capital must be positive")
        if per_trade <= 0:
            raise ValueError("per_trade must be positive")
        self._capital = float(capital)
        self._per_trade = float(per_trade)

    def run(
        self,
        intents: list[TradeIntent],
        price_maps: dict[str, dict[str, float]],
        calendar: list[str],
    ) -> tuple[list[Trade], list[PortfolioLedgerEntry]]:
        intents_by_date: dict[str, list[TradeIntent]] = defaultdict(list)
        for intent in intents:
            intents_by_date[intent.entry_date].append(intent)

        cash = self._capital
        realized_pnl = 0.0
        latest_prices: dict[str, float] = {}
        open_positions: dict[str, _OpenPosition] = {}
        completed_trades: list[Trade] = []
        snapshots: list[PortfolioLedgerEntry] = []

        for current_date in calendar:
            for ticker, price_map in price_maps.items():
                if current_date in price_map:
                    latest_prices[ticker] = price_map[current_date]

            # Close first so capital settled at today's close can fund entries
            # filled at the same close.
            for ticker in sorted(list(open_positions)):
                position = open_positions[ticker]
                if position.exit_date != current_date:
                    continue

                pnl = position.unrealized_pnl(position.exit_price)
                cash = round(cash + position.initial_notional + pnl, 2)
                realized_pnl = round(realized_pnl + pnl, 2)
                completed_trades.append(
                    Trade(
                        ticker=position.ticker,
                        direction=position.direction,
                        entry_date=position.entry_date,
                        exit_date=position.exit_date,
                        entry_price=position.entry_price,
                        exit_price=position.exit_price,
                        shares=position.shares,
                        pnl=pnl,
                        return_pct=round(pnl / position.initial_notional, 6),
                        holding_days=position.holding_days,
                        reasoning=position.reasoning,
                        metadata=position.metadata,
                    )
                )
                del open_positions[ticker]

            new_intents = [
                intent
                for intent in sorted(intents_by_date.get(current_date, []), key=lambda x: x.ticker)
                if intent.ticker not in open_positions and intent.entry_price > 0
            ]
            if new_intents and cash > 0:
                allocation = min(self._per_trade, cash / len(new_intents))
                for intent in new_intents:
                    # Four decimal places preserve the harness's fractional-share
                    # behavior without ever rounding above available cash.
                    shares = floor((allocation / intent.entry_price) * 10_000) / 10_000
                    notional = round(shares * intent.entry_price, 2)
                    if shares <= 0 or notional <= 0 or notional > cash:
                        continue
                    cash = round(cash - notional, 2)
                    open_positions[intent.ticker] = _OpenPosition(
                        ticker=intent.ticker,
                        direction=intent.direction,
                        entry_date=intent.entry_date,
                        exit_date=intent.exit_date,
                        entry_price=intent.entry_price,
                        exit_price=intent.exit_price,
                        shares=shares,
                        initial_notional=notional,
                        holding_days=intent.holding_days,
                        reasoning=intent.reasoning,
                        metadata=dict(intent.metadata),
                    )

            snapshots.append(
                self._snapshot(
                    current_date=current_date,
                    cash=cash,
                    realized_pnl=realized_pnl,
                    open_positions=open_positions,
                    latest_prices=latest_prices,
                )
            )

        completed_trades.sort(key=lambda trade: (trade.entry_date, trade.ticker))
        return completed_trades, snapshots

    def _snapshot(
        self,
        *,
        current_date: str,
        cash: float,
        realized_pnl: float,
        open_positions: dict[str, _OpenPosition],
        latest_prices: dict[str, float],
    ) -> PortfolioLedgerEntry:
        positions: dict[str, PositionSnapshot] = {}
        long_market_value = 0.0
        short_market_value = 0.0
        margin_used = 0.0
        unrealized_pnl = 0.0
        positions_equity = 0.0

        for ticker, position in sorted(open_positions.items()):
            market_price = latest_prices.get(ticker, position.entry_price)
            market_value = round(position.shares * market_price, 2)
            position_pnl = position.unrealized_pnl(market_price)
            equity_value = position.equity_value(market_price)
            if position.direction == "long":
                long_market_value += market_value
            else:
                short_market_value += market_value
                margin_used += position.initial_notional
            unrealized_pnl += position_pnl
            positions_equity += equity_value
            positions[ticker] = PositionSnapshot(
                direction=position.direction,
                shares=position.shares,
                entry_price=position.entry_price,
                market_price=market_price,
                market_value=market_value,
                equity_value=equity_value,
                unrealized_pnl=position_pnl,
                exit_date=position.exit_date,
            )

        long_market_value = round(long_market_value, 2)
        short_market_value = round(short_market_value, 2)
        unrealized_pnl = round(unrealized_pnl, 2)
        nav = round(cash + positions_equity, 2)

        return PortfolioLedgerEntry(
            date=current_date,
            cash=round(cash, 2),
            positions=positions,
            long_market_value=long_market_value,
            short_market_value=short_market_value,
            margin_used=round(margin_used, 2),
            gross_exposure=round(long_market_value + short_market_value, 2),
            net_exposure=round(long_market_value - short_market_value, 2),
            realized_pnl=round(realized_pnl, 2),
            unrealized_pnl=unrealized_pnl,
            nav=nav,
        )
