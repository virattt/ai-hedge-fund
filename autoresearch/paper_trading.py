"""
autoresearch/paper_trading.py — Run autoresearch strategy for a single day (dry run or paper).

Uses cached prices to compute signals and output suggested orders. With --execute,
submits BUY orders to PaperBroker (shorts not supported by PaperBroker yet).

Usage:
    poetry run python -m autoresearch.paper_trading
    poetry run python -m autoresearch.paper_trading --date 2026-03-07
    poetry run python -m autoresearch.paper_trading --execute --state-path .paper_broker_state.json
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.portfolio_backtest import (
    SECTOR_CONFIG,
    SECTOR_OOS_SHARPE,
    SECTOR_OOS_SHARPE_BULL,
    SECTOR_OOS_SHARPE_BEAR,
    run_sector_backtest,
)
from autoresearch.regime import get_regime_for_paper_trading, regime_scale
from autoresearch.risk_controls import should_halt_for_drawdown, scale_for_drawdown, apply_stop_loss


def _get_broker(live: bool, state_path: str, initial_cash: float, slippage_bps: float):
    """Return PaperBroker or TastytradeBroker based on --live flag."""
    from src.execution.models import OrderSide, OrderType, AssetClass, OrderStatus
    if live:
        import os
        if os.environ.get("TASTYTRADE_ORDER_ENABLED") != "true":
            raise RuntimeError(
                "Live tastytrade requires TASTYTRADE_ORDER_ENABLED=true. "
                "Set TASTYTRADE_CLIENT_SECRET, TASTYTRADE_REFRESH_TOKEN. Dry-run first."
            )
        from src.execution.tastytrade_broker import TastytradeBroker
        return TastytradeBroker()
    from src.execution.paper_broker import PaperBroker
    return PaperBroker(initial_cash=initial_cash, state_path=Path(state_path), slippage_bps=slippage_bps)


async def execute_orders(
    orders: list,
    prices: dict,
    state_path: str,
    initial_cash: float,
    target_positions: dict[str, int],
    slippage_bps: float = 5.0,
    live: bool = False,
):
    """Submit BUY/SELL orders to PaperBroker or TastytradeBroker (--live). Skips SHORT."""
    from src.execution.models import Order, OrderSide, OrderType, AssetClass, OrderStatus

    broker = _get_broker(live, state_path, initial_cash, slippage_bps)
    await broker.connect()

    account = await broker.get_account()
    positions = {p.ticker: p.quantity for p in account.positions}

    executed = []
    for ticker, target_qty in target_positions.items():
        price = prices.get(ticker)
        if not price or price <= 0:
            continue
        current = positions.get(ticker, 0)
        delta = target_qty - current
        if delta == 0:
            continue
        if hasattr(broker, "set_last_price"):
            broker.set_last_price(ticker, price)
        if delta > 0:
            order = Order(ticker=ticker, side=OrderSide.BUY, quantity=float(delta), order_type=OrderType.MARKET, asset_class=AssetClass.EQUITY)
        else:
            order = Order(ticker=ticker, side=OrderSide.SELL, quantity=float(-delta), order_type=OrderType.MARKET, asset_class=AssetClass.EQUITY)
        result = await broker.submit_order(order)
        if result.status == OrderStatus.FILLED:
            side = "BUY" if delta > 0 else "SELL"
            executed.append(f"  FILLED {side} {abs(delta)} {ticker} @ ${price:.2f}")
        else:
            executed.append(f"  REJECTED {ticker}: {result.message}")

    await broker.disconnect()
    return executed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date to run (YYYY-MM-DD)")
    parser.add_argument("--weights", choices=["equal", "oos"], default="oos")
    parser.add_argument("--execute", action="store_true", help="Submit orders (paper or live with --live)")
    parser.add_argument("--live", action="store_true", help="Use TastytradeBroker (requires TASTYTRADE_ORDER_ENABLED=true)")
    parser.add_argument("--state-path", type=str, default=".paper_broker_state.json",
                        help="PaperBroker state file path")
    parser.add_argument("--initial-cash", type=float, default=100_000.0, help="Initial cash for PaperBroker")
    parser.add_argument("--cost-bps", type=float, default=0, help="Transaction cost in bps (e.g. 10 = 0.1%%)")
    parser.add_argument("--no-regime", action="store_true", help="Disable regime-adaptive position scaling")
    parser.add_argument("--regime-drawdown", action="store_true", help="Use drawdown-based regime (bear if DD>5%%)")
    parser.add_argument("--lookback-days", type=int, default=10, help="Backtest lookback for signal generation (default 10)")
    parser.add_argument("--max-ticker-weight", type=float, default=0.15, help="Max weight per ticker (0.15 = 15%%, 0 = no cap)")
    parser.add_argument("--vol-weight", action="store_true", help="Use inverse-volatility (risk parity) position sizing")
    parser.add_argument("--slippage-bps", type=float, default=5.0, help="Paper only: simulated slippage in bps")
    parser.add_argument("--max-drawdown-pct", type=float, default=0, help="Halt if portfolio DD exceeds this %% (e.g. 15)")
    parser.add_argument("--stop-loss-pct", type=float, default=0, help="Trim position if unrealized loss exceeds this %% (e.g. 10)")
    args = parser.parse_args()

    date = args.date
    lookback_end = date
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
        lookback_start = (d - timedelta(days=args.lookback_days)).strftime("%Y-%m-%d")
    except ValueError:
        lookback_start = date
    print(f"Paper trading run for {date}")
    print("-" * 50)

    if args.execute:
        from autoresearch.validate_prices import validate_prices
        ok, msgs = validate_prices()
        if msgs:
            for m in msgs:
                print(f"  VALIDATE: {m}")
            if not ok:
                print("  Price validation failed. Run refresh_all_prices.sh or fix cache.")
                return 1

    regime_scale_factor = 1.0
    regime = "bull"
    if not args.no_regime:
        regime = get_regime_for_paper_trading(use_drawdown=args.regime_drawdown)
        regime_scale_factor = regime_scale(regime)
        if args.max_drawdown_pct > 0:
            regime_scale_factor = scale_for_drawdown(
                regime_scale_factor, args.state_path, args.max_drawdown_pct,
            )
        print(f"  Regime: {regime} (scale={regime_scale_factor:.2f})")

    sector_positions = {}
    sector_engines = {}
    prices_by_ticker = {}

    for sector, (mod, path) in SECTOR_CONFIG.items():
        try:
            pv, metrics, engine = run_sector_backtest(mod, path, start=lookback_start, end=lookback_end, cost_bps=args.cost_bps)
            sector_positions[sector] = getattr(engine, "final_positions", {})
            sector_engines[sector] = engine
            for t, p in getattr(engine, "last_prices", {}).items():
                prices_by_ticker[t] = p
            val = pv[-1]["value"] if pv else 0
            print(f"  {sector:12} value=${val:,.0f}")
        except Exception as e:
            print(f"  {sector:12} SKIP: {e}")
            continue

    if regime == "bull" and not args.no_regime:
        oos = {s: max(SECTOR_OOS_SHARPE_BULL.get(s, SECTOR_OOS_SHARPE.get(s, 0)), 0.01) for s in sector_positions}
    elif not args.no_regime:
        oos = {s: max(SECTOR_OOS_SHARPE_BEAR.get(s, SECTOR_OOS_SHARPE.get(s, 0)), 0.01) for s in sector_positions}
    else:
        oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in sector_positions}
    total_oos = sum(oos.values())
    weights = {s: oos[s] / total_oos for s in sector_positions}

    all_orders = []
    target_positions: dict[str, int] = {}
    for sector, positions in sector_positions.items():
        w = weights.get(sector, 1.0 / len(sector_positions))
        for ticker, pos in positions.items():
            long_qty = pos.get("long", 0)
            short_qty = pos.get("short", 0)
            if long_qty > 0:
                scale = (args.initial_cash * w) / 100_000.0 * regime_scale_factor
                qty = max(0, int(long_qty * scale))
                if qty > 0:
                    target_positions[ticker] = target_positions.get(ticker, 0) + qty
                    all_orders.append({"ticker": ticker, "side": "BUY", "quantity": qty, "sector": sector, "weight": f"{w:.2%}"})
            if short_qty > 0:
                all_orders.append({"ticker": ticker, "side": "SHORT", "quantity": short_qty, "sector": sector, "weight": f"{w:.2%}"})

    if args.vol_weight and sector_engines and target_positions and prices_by_ticker:
        from autoresearch.risk_controls import volatility_weights
        rets_by_ticker = {}
        for ticker in target_positions:
            for eng in sector_engines.values():
                prices = getattr(eng, "prices", {})
                if ticker in prices:
                    df = prices[ticker]
                    if hasattr(df, "columns") and "close" in df.columns and len(df) >= 5:
                        rets_by_ticker[ticker] = df["close"].pct_change().dropna().tolist()
                    break
        if rets_by_ticker:
            vol_w = volatility_weights(rets_by_ticker)
            total_value = sum(target_positions.get(t, 0) * prices_by_ticker.get(t, 0) for t in target_positions)
            if total_value > 0:
                for ticker in list(target_positions.keys()):
                    w = vol_w.get(ticker, 1.0 / len(target_positions))
                    p = prices_by_ticker.get(ticker, 0)
                    if p <= 0:
                        continue
                    target_val = total_value * w
                    target_positions[ticker] = max(0, int(target_val / p))
        for o in all_orders:
            if o["side"] == "BUY":
                o["quantity"] = target_positions.get(o["ticker"], 0)
    if args.max_ticker_weight > 0 and target_positions and prices_by_ticker:
        total_value = sum(target_positions.get(t, 0) * prices_by_ticker.get(t, 0) for t in target_positions)
        if total_value > 0:
            for ticker in list(target_positions.keys()):
                p = prices_by_ticker.get(ticker, 0)
                if p <= 0:
                    continue
                val = target_positions[ticker] * p
                if val / total_value > args.max_ticker_weight:
                    cap_val = total_value * args.max_ticker_weight
                    target_positions[ticker] = max(0, int(cap_val / p))
    for o in all_orders:
        if o["side"] == "BUY":
            o["quantity"] = target_positions.get(o["ticker"], 0)

    print("-" * 50)
    print("Suggested orders (dry run):")
    for o in all_orders:
        print(f"  {o['side']:5} {o['quantity']:4} {o['ticker']:6} ({o['sector']}, weight {o['weight']})")

    if args.execute:
        state_path = Path(args.state_path)
        if state_path.exists():
            import json
            with open(state_path) as f:
                state = json.load(f)
            for ticker, p in state.get("positions", {}).items():
                qty = p.get("quantity", 0)
                if qty > 0 and ticker not in target_positions:
                    target_positions[ticker] = 0
        missing = [t for t in target_positions if t not in prices_by_ticker]
        if missing:
            from autoresearch.performance_tracker import load_prices_for_tickers
            for t, pr in load_prices_for_tickers(missing).items():
                prices_by_ticker[t] = pr
        if args.max_drawdown_pct > 0:
            halt, dd = should_halt_for_drawdown(args.state_path, args.max_drawdown_pct)
            if halt and dd is not None:
                print(f"\nHALT: Drawdown {dd*100:.1f}% >= max {args.max_drawdown_pct}%. Skipping execution.")
                return 0
        if args.stop_loss_pct > 0 and state_path.exists():
            import json
            with open(state_path) as f:
                state = json.load(f)
            trim = apply_stop_loss(state.get("positions", {}), prices_by_ticker, args.stop_loss_pct)
            for t, v in trim.items():
                target_positions[t] = v
        if not target_positions:
            print("\nNo target positions to execute.")
        else:
            broker_name = "TastytradeBroker (LIVE)" if args.live else "PaperBroker"
            print(f"\nExecuting orders via {broker_name} (BUY/SELL to reach targets)...")
            executed = asyncio.run(execute_orders(
                all_orders, prices_by_ticker, args.state_path, args.initial_cash, target_positions,
                slippage_bps=args.slippage_bps,
                live=args.live,
            ))
            for line in executed:
                print(line)
            print(f"\nState saved to {args.state_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
