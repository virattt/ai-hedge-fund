"""Sync Alpaca account state into the internal portfolio format agents expect."""

from __future__ import annotations

from integrations.broker.models import AccountSnapshot, Position


def merge_tickers(requested: list[str], positions: list[Position]) -> list[str]:
    """Union of CLI tickers and any symbols already held at the broker."""
    tickers = {t.upper() for t in requested}
    for position in positions:
        tickers.add(position.ticker.upper())
    return sorted(tickers)


def positions_to_portfolio(
    *,
    account: AccountSnapshot,
    positions: list[Position],
    tickers: list[str],
    margin_requirement: float,
) -> dict:
    """Convert broker state into the portfolio dict used by src/main.py agents."""
    portfolio = {
        "cash": account.cash,
        "margin_requirement": margin_requirement,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0} for ticker in tickers},
    }

    for position in positions:
        ticker = position.ticker.upper()
        if ticker not in portfolio["positions"]:
            portfolio["positions"][ticker] = {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            portfolio["realized_gains"][ticker] = {"long": 0.0, "short": 0.0}

        if position.side == "long":
            portfolio["positions"][ticker]["long"] = abs(position.quantity)
            portfolio["positions"][ticker]["long_cost_basis"] = position.avg_entry_price
        else:
            short_qty = abs(position.quantity)
            portfolio["positions"][ticker]["short"] = short_qty
            portfolio["positions"][ticker]["short_cost_basis"] = position.avg_entry_price
            margin_used = short_qty * position.avg_entry_price * margin_requirement
            portfolio["positions"][ticker]["short_margin_used"] = margin_used
            portfolio["margin_used"] += margin_used

    return portfolio
