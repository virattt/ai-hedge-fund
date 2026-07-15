"""Backtest alpha views through one cash-constrained, marked-to-market book.

The AlphaModel only forms views. This harness owns the intentionally simple
mechanics: threshold entries, equal-dollar targets, fixed holding periods, and
fully collateralized shorts. All tickers share one PortfolioLedger, so capital
cannot be allocated independently more than once.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np

from v2.backtesting.ledger import PortfolioLedger, TradeIntent
from v2.backtesting.models import BacktestResult, PerformanceMetrics, PortfolioLedgerEntry, Trade
from v2.data.protocol import DataClient
from v2.signals.base import AlphaModel

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Simulate an alpha model against one shared portfolio."""

    def __init__(
        self,
        *,
        capital: float = 100_000.0,
        per_trade: float = 10_000.0,
    ) -> None:
        if capital <= 0:
            raise ValueError("capital must be positive")
        if per_trade <= 0:
            raise ValueError("per_trade must be positive")
        self._capital = float(capital)
        self._per_trade = float(per_trade)

    def run_alpha(
        self,
        model: AlphaModel,
        tickers: list[str],
        data_client: DataClient,
        start_date: str,
        end_date: str,
        *,
        threshold: float = 0.0,
        holding_days: int = 5,
    ) -> BacktestResult:
        """Backtest an alpha model over ``[start_date, end_date]``.

        Candidate entries are generated per ticker, then executed together in
        chronological order against a shared pool of cash. Same-day signals
        split available cash equally up to ``per_trade`` each. The returned
        ledger is marked to market at every available close through the later
        of ``end_date`` and the final accepted exit.
        """
        if holding_days <= 0:
            raise ValueError("holding_days must be positive")
        if threshold < 0:
            raise ValueError("threshold must be non-negative")

        price_maps = self._load_price_maps(
            tickers, data_client, start_date, end_date, holding_days,
        )
        if not price_maps:
            return BacktestResult()

        intents: list[TradeIntent] = []
        for ticker in tickers:
            price_map = price_maps.get(ticker)
            if not price_map:
                continue
            intents.extend(
                self._trade_ticker(
                    model,
                    ticker,
                    data_client,
                    price_map,
                    start_date,
                    end_date,
                    threshold=threshold,
                    holding_days=holding_days,
                )
            )

        # Include padded dates while simulating so positions opened near the
        # requested end can close mechanically.
        padded_calendar = sorted(
            {
                day
                for price_map in price_maps.values()
                for day in price_map
                if day >= start_date
            }
        )
        ledger = PortfolioLedger(capital=self._capital, per_trade=self._per_trade)
        trades, snapshots = ledger.run(intents, price_maps, padded_calendar)

        final_date = max(
            [end_date, *(trade.exit_date for trade in trades)],
        )
        snapshots = [snapshot for snapshot in snapshots if snapshot.date <= final_date]
        equity_curve = self._build_equity_curve(snapshots)
        metrics = self._compute_metrics(trades, snapshots) if trades else None
        return BacktestResult(
            trades=trades,
            metrics=metrics,
            equity_curve=equity_curve,
            ledger=snapshots,
        )

    # ------------------------------------------------------------------
    # Data and candidate generation
    # ------------------------------------------------------------------

    def _load_price_maps(
        self,
        tickers: list[str],
        data_client: DataClient,
        start_date: str,
        end_date: str,
        holding_days: int,
    ) -> dict[str, dict[str, float]]:
        end_padded = (_parse_date(end_date) + timedelta(days=holding_days * 2 + 10)).isoformat()
        end_padded = min(end_padded, date.today().isoformat())

        price_maps: dict[str, dict[str, float]] = {}
        for ticker in tickers:
            prices = data_client.get_prices(ticker, start_date, end_padded)
            if not prices:
                continue
            price_map = {
                price.time[:10]: float(price.close)
                for price in prices
                if price.close is not None and float(price.close) > 0
            }
            if price_map:
                price_maps[ticker] = price_map
        return price_maps

    def _trade_ticker(
        self,
        model: AlphaModel,
        ticker: str,
        data_client: DataClient,
        price_map: dict[str, float],
        start_date: str,
        end_date: str,
        *,
        threshold: float,
        holding_days: int,
    ) -> list[TradeIntent]:
        """Walk one ticker's signal grid and emit unallocated trade intents."""
        all_days = sorted(price_map)
        all_day_index = {day: index for index, day in enumerate(all_days)}
        grid = [day for day in all_days if start_date <= day <= end_date]
        grid_index = {day: index for index, day in enumerate(grid)}

        intents: list[TradeIntent] = []
        armed = True
        i = 0
        while i < len(grid):
            current_date = grid[i]
            signal = model.predict(ticker, current_date, data_client)

            if armed and abs(signal.value) > threshold:
                entry_idx = all_day_index[current_date]
                exit_idx = entry_idx + holding_days
                if exit_idx >= len(all_days):
                    break
                exit_date = all_days[exit_idx]
                direction = "long" if signal.value > 0 else "short"
                intents.append(
                    TradeIntent(
                        ticker=ticker,
                        direction=direction,
                        entry_date=current_date,
                        exit_date=exit_date,
                        entry_price=price_map[current_date],
                        exit_price=price_map[exit_date],
                        holding_days=holding_days,
                        reasoning=signal.reasoning,
                        metadata=dict(signal.metadata),
                    )
                )
                armed = False
                if exit_date not in grid_index:
                    break
                i = grid_index[exit_date]
                continue

            if abs(signal.value) <= threshold:
                armed = True
            i += 1

        return intents

    # ------------------------------------------------------------------
    # NAV curve and performance metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _build_equity_curve(ledger: list[PortfolioLedgerEntry]) -> list[float]:
        """Return the end-of-day NAV series from portfolio ledger entries."""
        return [snapshot.nav for snapshot in ledger]

    def _compute_metrics(
        self,
        trades: list[Trade],
        ledger: list[PortfolioLedgerEntry],
    ) -> PerformanceMetrics:
        """Compute performance from daily portfolio NAV, not per-trade returns."""
        if not ledger:
            raise ValueError("cannot compute metrics without portfolio ledger entries")

        nav = np.asarray([snapshot.nav for snapshot in ledger], dtype=float)
        final_nav = float(nav[-1])
        total_return_pct = (final_nav - self._capital) / self._capital

        first_date = _parse_date(ledger[0].date)
        last_date = _parse_date(ledger[-1].date)
        calendar_days = max((last_date - first_date).days, 1)
        years = calendar_days / 365.25
        if final_nav <= 0:
            annualized_return = -1.0
        else:
            annualized_return = (final_nav / self._capital) ** (1 / years) - 1

        daily_returns = np.asarray(
            [
                nav[index] / nav[index - 1] - 1
                for index in range(1, len(nav))
                if nav[index - 1] > 0
            ],
            dtype=float,
        )
        if len(daily_returns) >= 2:
            daily_std = float(daily_returns.std(ddof=1))
            annualized_volatility = daily_std * np.sqrt(252)
            sharpe = (
                float(daily_returns.mean()) / daily_std * np.sqrt(252)
                if daily_std > 1e-12
                else 0.0
            )
        else:
            annualized_volatility = 0.0
            sharpe = 0.0

        running_peak = np.maximum.accumulate(nav)
        drawdowns = np.divide(
            running_peak - nav,
            running_peak,
            out=np.zeros_like(nav),
            where=running_peak != 0,
        )
        max_drawdown = float(drawdowns.max()) if len(drawdowns) else 0.0

        trade_returns = [trade.return_pct for trade in trades]
        n_trades = len(trades)
        wins = sum(1 for value in trade_returns if value > 0)
        average_trade_return = float(np.mean(trade_returns)) if trade_returns else 0.0

        return PerformanceMetrics(
            total_return_pct=round(total_return_pct, 6),
            annualized_return_pct=round(annualized_return, 6),
            annualized_volatility=round(annualized_volatility, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown_pct=round(max_drawdown, 6),
            win_rate=round(wins / n_trades, 4) if n_trades else 0.0,
            n_trades=n_trades,
            n_long=sum(1 for trade in trades if trade.direction == "long"),
            n_short=sum(1 for trade in trades if trade.direction == "short"),
            avg_return_pct=round(average_trade_return, 6),
            avg_holding_days=round(
                sum(trade.holding_days for trade in trades) / n_trades, 1,
            ) if n_trades else 0.0,
        )


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()
