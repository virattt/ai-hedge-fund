from __future__ import annotations

from typing import Dict, Mapping
from types import MappingProxyType

from .types import PortfolioSnapshot, PositionState, TickerRealizedGains


class Portfolio:
    """Portfolio state management for backtesting operations.

    Encapsulates cash, positions, and margin tracking.
    Supports both long and short positions with proper cost basis tracking
    and realized gains/losses calculation.
    """

    def __init__(
        self,
        *,
        tickers: list[str],
        initial_cash: float,
        margin_requirement: float,
    ) -> None:
        self._portfolio: PortfolioSnapshot = {
            "cash": float(initial_cash),
            "margin_used": 0.0,
            "margin_requirement": float(margin_requirement),
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
            "realized_gains": {
                ticker: {"long": 0.0, "short": 0.0}
                for ticker in tickers
            },
        }

    def get_snapshot(self) -> PortfolioSnapshot:
        positions_copy: Dict[str, PositionState] = {
            t: {
                "long": p["long"],
                "short": p["short"],
                "long_cost_basis": p["long_cost_basis"],
                "short_cost_basis": p["short_cost_basis"],
                "short_margin_used": p["short_margin_used"],
            }
            for t, p in self._portfolio["positions"].items()
        }
        gains_copy: Dict[str, TickerRealizedGains] = {
            t: {"long": g["long"], "short": g["short"]}
            for t, g in self._portfolio["realized_gains"].items()
        }
        return {
            "cash": float(self._portfolio["cash"]),
            "margin_used": float(self._portfolio["margin_used"]),
            "margin_requirement": float(self._portfolio["margin_requirement"]),
            "positions": positions_copy,
            "realized_gains": gains_copy,
        }

    def get_cash(self) -> float:
        return float(self._portfolio["cash"])

    def get_margin_used(self) -> float:
        return float(self._portfolio["margin_used"])

    def get_margin_requirement(self) -> float:
        return float(self._portfolio["margin_requirement"])

    def get_positions(self) -> Mapping[str, PositionState]:
        return MappingProxyType(self._portfolio["positions"])  # type: ignore[arg-type]

    def get_realized_gains(self) -> Mapping[str, TickerRealizedGains]:
        return MappingProxyType(self._portfolio["realized_gains"])  # type: ignore[arg-type]

    def apply_long_buy(self, ticker: str, quantity: int, price: float) -> int:
        if quantity <= 0:
            return 0
        quantity = int(quantity)
        position = self._portfolio["positions"][ticker]
        cost = quantity * price
        if cost <= self._portfolio["cash"]:
            old_shares = position["long"]
            old_cost_basis = position["long_cost_basis"]
            total_shares = old_shares + quantity
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_shares
                total_new_cost = cost
                position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            position["long"] = old_shares + quantity
            self._portfolio["cash"] -= cost
            return quantity
        max_quantity = int(self._portfolio["cash"] / price) if price > 0 else 0
        if max_quantity > 0:
            cost = max_quantity * price
            old_shares = position["long"]
            old_cost_basis = position["long_cost_basis"]
            total_shares = old_shares + max_quantity
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_shares
                total_new_cost = cost
                position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            position["long"] = old_shares + max_quantity
            self._portfolio["cash"] -= cost
            return max_quantity
        return 0

    def apply_long_sell(self, ticker: str, quantity: int, price: float) -> int:
        position = self._portfolio["positions"][ticker]
        quantity = min(int(quantity), position["long"]) if quantity > 0 else 0
        if quantity <= 0:
            return 0
        avg_cost = position["long_cost_basis"] if position["long"] > 0 else 0.0
        realized_gain = (price - avg_cost) * quantity
        self._portfolio["realized_gains"][ticker]["long"] += realized_gain
        position["long"] -= quantity
        self._portfolio["cash"] += quantity * price
        if position["long"] == 0:
            position["long_cost_basis"] = 0.0
        return quantity

    def apply_short_open(self, ticker: str, quantity: int, price: float) -> int:
        if quantity <= 0:
            return 0
        quantity = int(quantity)
        position = self._portfolio["positions"][ticker]
        proceeds = price * quantity
        margin_ratio = self._portfolio["margin_requirement"]
        margin_required = proceeds * margin_ratio
        if margin_required <= self._portfolio["cash"]:
            old_short_shares = position["short"]
            old_cost_basis = position["short_cost_basis"]
            total_shares = old_short_shares + quantity
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_short_shares
                total_new_cost = price * quantity
                position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            position["short"] = old_short_shares + quantity
            position["short_margin_used"] += margin_required
            self._portfolio["margin_used"] += margin_required
            self._portfolio["cash"] += proceeds
            self._portfolio["cash"] -= margin_required
            return quantity
        max_quantity = int(self._portfolio["cash"] / (price * margin_ratio)) if margin_ratio > 0 and price > 0 else 0
        if max_quantity > 0:
            proceeds = price * max_quantity
            margin_required = proceeds * margin_ratio
            old_short_shares = position["short"]
            old_cost_basis = position["short_cost_basis"]
            total_shares = old_short_shares + max_quantity
            if total_shares > 0:
                total_old_cost = old_cost_basis * old_short_shares
                total_new_cost = price * max_quantity
                position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares
            position["short"] = old_short_shares + max_quantity
            position["short_margin_used"] += margin_required
            self._portfolio["margin_used"] += margin_required
            self._portfolio["cash"] += proceeds
            self._portfolio["cash"] -= margin_required
            return max_quantity
        return 0

    def apply_short_cover(self, ticker: str, quantity: int, price: float) -> int:
        position = self._portfolio["positions"][ticker]
        quantity = min(int(quantity), position["short"]) if quantity > 0 else 0
        if quantity <= 0:
            return 0
        cover_cost = quantity * price
        avg_short_price = position["short_cost_basis"] if position["short"] > 0 else 0.0
        realized_gain = (avg_short_price - price) * quantity
        if position["short"] > 0:
            portion = quantity / position["short"]
        else:
            portion = 1.0
        margin_to_release = portion * position["short_margin_used"]
        position["short"] -= quantity
        position["short_margin_used"] -= margin_to_release
        self._portfolio["margin_used"] -= margin_to_release
        self._portfolio["cash"] += margin_to_release
        self._portfolio["cash"] -= cover_cost
        self._portfolio["realized_gains"][ticker]["short"] += realized_gain
        if position["short"] == 0:
            position["short_cost_basis"] = 0.0
            position["short_margin_used"] = 0.0
        return quantity

