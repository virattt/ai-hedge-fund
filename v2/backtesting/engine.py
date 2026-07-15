"""Backtesting engine — simulate trading an alpha model's views over time.

The engine queries an AlphaModel across a date grid, turns its convictions
into trades, and computes performance (return, Sharpe, drawdown).

IMPORTANT — separation of concerns (the "unify" decision):
  - The AlphaModel forms *views* (conviction in [-1, +1]).
  - This engine owns *mechanics* (entry timing, holding period, sizing).
These mechanics are intentionally simple for now (threshold + fixed holding
period + equal-dollar sizing). Week 8 portfolio construction will replace
this harness with real position sizing and risk-aware weighting.

Usage:
    from datetime import date
    from v2.data import FDClient
    from v2.backtesting import BacktestEngine
    from v2.signals import PEADModel

    with FDClient() as fd:
        engine = BacktestEngine(capital=100_000, per_trade=10_000)
        result = engine.run_alpha(
            PEADModel(), ["AAPL", "MSFT"], fd,
            "2024-06-01", date.today().isoformat(), holding_days=5,
        )
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np

from v2.backtesting.models import BacktestResult, PerformanceMetrics, Trade
from v2.data.protocol import DataClient
from v2.signals.base import AlphaModel

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Simulates trading an alpha model's signals with equal-dollar sizing."""

    def __init__(
        self,
        *,
        capital: float = 100_000.0,
        per_trade: float = 10_000.0,
    ) -> None:
        self._capital = capital
        self._per_trade = per_trade

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
        """Backtest an alpha model over [start_date, end_date].

        For each ticker we walk the trading-day grid, ask the model for its
        view, and open a position whenever conviction clears `threshold`.
        Positions are held for `holding_days` trading days.

        Args:
            model:        AlphaModel to backtest (e.g. PEADModel()).
            tickers:      Universe to trade.
            data_client:    Data client.
            start_date:   First date to evaluate signals (YYYY-MM-DD).
            end_date:     Last date to evaluate signals (YYYY-MM-DD).
            threshold:    Minimum |conviction| to act on (0.0 = any nonzero view).
            holding_days: Trading days to hold each position.
        """
        trades: list[Trade] = []
        for ticker in tickers:
            trades.extend(self._trade_ticker(
                model, ticker, data_client, start_date, end_date,
                threshold=threshold, holding_days=holding_days,
            ))

        if not trades:
            return BacktestResult()

        trades.sort(key=lambda t: t.entry_date)
        equity_curve = self._build_equity_curve(trades)
        metrics = self._compute_metrics(trades, equity_curve)
        return BacktestResult(trades=trades, metrics=metrics, equity_curve=equity_curve)

    # ------------------------------------------------------------------
    # Per-ticker simulation
    # ------------------------------------------------------------------

    def _trade_ticker(
        self,
        model: AlphaModel,
        ticker: str,
        data_client: DataClient,
        start_date: str,
        end_date: str,
        *,
        threshold: float,
        holding_days: int,
    ) -> list[Trade]:
        """Walk one ticker's trading-day grid and open/close positions."""
        # Fetch the price series once. Pad the end so exits beyond end_date
        # still have a closing price to fill against.
        end_padded = (_parse_date(end_date) + timedelta(days=holding_days * 2 + 10)).isoformat()
        today = date.today().isoformat()
        if end_padded > today:
            end_padded = today

        prices = data_client.get_prices(ticker, start_date, end_padded)
        if not prices:
            return []

        price_map = {p.time[:10]: p.close for p in prices}
        all_days = sorted(price_map)
        # Scan grid = trading days within [start_date, end_date]
        grid = [d for d in all_days if start_date <= d <= end_date]

        trades: list[Trade] = []
        armed = True  # edge-trigger: only open when re-armed (signal returned to flat)
        i = 0
        while i < len(grid):
            d = grid[i]
            signal = model.predict(ticker, d, data_client)

            if armed and abs(signal.value) > threshold:
                direction = "long" if signal.value > 0 else "short"
                entry_idx = all_days.index(d)
                exit_idx = entry_idx + holding_days
                if exit_idx >= len(all_days):
                    break  # not enough future data to close the position
                trade = self._build_trade(
                    ticker, direction, d, all_days[exit_idx],
                    price_map, holding_days, signal.reasoning, dict(signal.metadata),
                )
                if trade is not None:
                    trades.append(trade)
                armed = False
                # Skip ahead past the holding period — no overlapping positions
                i = grid.index(all_days[exit_idx]) if all_days[exit_idx] in grid else len(grid)
                continue

            # Re-arm once the model goes back to "no view"
            if abs(signal.value) <= threshold:
                armed = True
            i += 1

        return trades

    # ------------------------------------------------------------------
    # Signal -> Trade
    # ------------------------------------------------------------------

    def _build_trade(
        self,
        ticker: str,
        direction: str,
        entry_date: str,
        exit_date: str,
        price_map: dict[str, float],
        holding_days: int,
        reasoning: str | None,
        metadata: dict,
    ) -> Trade | None:
        """Fill a position at entry/exit closes with equal-dollar sizing."""
        entry_price = price_map.get(entry_date)
        exit_price = price_map.get(exit_date)
        if entry_price is None or exit_price is None or entry_price <= 0:
            return None

        shares = self._per_trade / entry_price

        if direction == "long":
            pnl = shares * (exit_price - entry_price)
            return_pct = (exit_price - entry_price) / entry_price
        else:
            pnl = shares * (entry_price - exit_price)
            return_pct = (entry_price - exit_price) / entry_price

        return Trade(
            ticker=ticker,
            direction=direction,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            shares=round(shares, 4),
            pnl=round(pnl, 2),
            return_pct=round(return_pct, 6),
            holding_days=holding_days,
            reasoning=reasoning,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    def _build_equity_curve(self, trades: list[Trade]) -> list[float]:
        """Track portfolio value after each trade settles.

        Starts at initial capital (e.g. $100,000) and adds each trade's
        dollar P&L in chronological order. The result is a list like:
        [100000, 100500, 99800, 100200, ...] — one entry per trade plus
        the starting value. This is what you'd plot to visualize the
        strategy's performance and see drawdowns.
        """
        equity = self._capital
        curve = [equity]
        for t in trades:
            equity += t.pnl
            curve.append(round(equity, 2))
        return curve

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        trades: list[Trade],
        equity_curve: list[float],
    ) -> PerformanceMetrics:
        """Compute the three numbers that tell you if a strategy works.

        1. Total/annualized return — did it make money?
        2. Sharpe ratio — is the return worth the risk? (return per unit
           of volatility, annualized). Above 1.0 is decent, above 2.0
           is strong. Our PEAD strategy hit 0.33 — not tradable yet.
        3. Max drawdown — how bad did it get at the worst point?
           (largest peak-to-trough drop in the equity curve)

        Also computes win rate and trade counts for context.
        """
        returns = [t.return_pct for t in trades]
        n = len(returns)

        # Total return: how much the portfolio gained or lost overall
        final_equity = equity_curve[-1]
        total_return_pct = (final_equity - self._capital) / self._capital

        # Annualized return: what the total return would be per year
        # if the strategy ran at the same rate continuously
        first_entry = _parse_date(trades[0].entry_date)
        last_exit = _parse_date(trades[-1].exit_date)
        calendar_days = (last_exit - first_entry).days
        years = max(calendar_days / 365.25, 0.01)
        annualized = (1 + total_return_pct) ** (1 / years) - 1

        # Sharpe ratio: average return divided by volatility, scaled to
        # annual terms. Higher = better risk-adjusted performance.
        arr = np.array(returns)
        avg = float(arr.mean())
        std = float(arr.std(ddof=1)) if n > 1 else 1.0
        trades_per_year = n / years if years > 0 else n
        sharpe = (avg / std) * np.sqrt(trades_per_year) if std > 0 else 0.0

        # Max drawdown: walk the equity curve tracking the peak. Whenever
        # the value drops below the peak, measure how far it fell. The
        # largest such drop is the max drawdown.
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd

        # Win rate: fraction of trades that made money
        wins = sum(1 for r in returns if r > 0)

        return PerformanceMetrics(
            total_return_pct=round(total_return_pct, 6),
            annualized_return_pct=round(annualized, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown_pct=round(max_dd, 6),
            win_rate=round(wins / n, 4) if n > 0 else 0.0,
            n_trades=n,
            n_long=sum(1 for t in trades if t.direction == "long"),
            n_short=sum(1 for t in trades if t.direction == "short"),
            avg_return_pct=round(avg, 6),
            avg_holding_days=round(sum(t.holding_days for t in trades) / n, 1),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()
