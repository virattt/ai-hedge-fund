"""Build options strategies from agent signals and confidence (delta targeting)."""

from typing import Any

from src.execution.options.chain import OptionsChainFetcher
from src.execution.options.greeks import GreeksCalculator


class StrategyBuilder:
    """
    Given agent signals + confidence, suggest or construct:
    - Covered calls (bullish hold + income)
    - Cash-secured puts (bullish, want to own cheaper)
    - Put spreads (defined-risk directional)
    - Iron condors (neutral/range-bound)
    Strike selection: high confidence -> closer ATM (higher delta), low -> further OTM.
    """

    def __init__(self, chain_fetcher: OptionsChainFetcher | None = None):
        self._chain = chain_fetcher

    def confidence_to_target_delta(self, confidence: int) -> float:
        """Map 0-100 confidence to target absolute delta (e.g. 0.30 = 30 delta)."""
        if confidence >= 80:
            return 0.50  # ATM
        if confidence >= 60:
            return 0.40
        if confidence >= 40:
            return 0.30
        return 0.20  # OTM

    def select_strike(
        self,
        chain: list[dict[str, Any]],
        underlying_price: float,
        option_type: str,
        target_delta: float,
    ) -> dict[str, Any] | None:
        """
        Pick the chain entry whose delta is closest to target_delta.
        chain entries: {symbol, strike, expiry, option_type}.
        Uses GreeksCalculator for delta if no broker delta provided.
        """
        if not chain or underlying_price <= 0:
            return None
        T = 30 / 365.0
        r = 0.05
        sigma = 0.25
        best = None
        best_diff = 1.0
        for opt in chain:
            if (opt.get("option_type") or "call").lower() != option_type.lower():
                continue
            K = opt.get("strike", 0)
            is_call = option_type.lower() == "call"
            delta = (
                GreeksCalculator.call_delta(underlying_price, K, T, r, sigma)
                if is_call
                else GreeksCalculator.put_delta(underlying_price, K, T, r, sigma)
            )
            diff = abs(abs(delta) - target_delta)
            if diff < best_diff:
                best_diff = diff
                best = opt
        return best

    def covered_call(
        self,
        symbol: str,
        underlying_price: float,
        confidence: int,
        chain: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Suggest a call to sell against long stock (income)."""
        if chain is None and self._chain:
            chain = self._chain.get_chain(symbol)
        if not chain:
            return None
        target = self.confidence_to_target_delta(confidence)
        return self.select_strike(chain, underlying_price, "call", target)

    def cash_secured_put(
        self,
        symbol: str,
        underlying_price: float,
        confidence: int,
        chain: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Suggest a put to sell (bullish, want to own cheaper)."""
        if chain is None and self._chain:
            chain = self._chain.get_chain(symbol)
        if not chain:
            return None
        target = self.confidence_to_target_delta(confidence)
        return self.select_strike(chain, underlying_price, "put", target)
