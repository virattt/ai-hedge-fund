"""Deterministic portfolio decisions for light (no-LLM) cycles."""

from __future__ import annotations

from typing import Any

from src.agents.portfolio_manager import compute_allowed_actions

_SIGNAL_SCORE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}

# Minimum conviction before a light cycle trades at all. Light cycles run
# every few minutes, so acting on marginal votes creates constant churn.
_TRADE_THRESHOLD = 0.5

# Skip adds smaller than this fraction of the name's total risk limit —
# prevents 1-2 share dribble orders as a position hovers near target.
_MIN_DELTA_FRACTION = 0.05


def _aggregate_ticker_signals(ticker_signals: dict[str, dict[str, Any]]) -> tuple[str, float]:
    total = 0.0
    weight = 0.0
    for payload in ticker_signals.values():
        signal = payload.get("signal")
        confidence = payload.get("confidence")
        if signal not in _SIGNAL_SCORE or confidence is None:
            continue
        w = max(float(confidence), 1.0) / 100.0
        total += _SIGNAL_SCORE[signal] * w
        weight += w
    if weight <= 0:
        return "neutral", 0.0
    score = total / weight
    if score > 0.2:
        return "bullish", min(score, 1.0)
    if score < -0.2:
        return "bearish", min(abs(score), 1.0)
    return "neutral", abs(score)


def _total_position_limit(
    ticker_risk: dict[str, Any],
    remaining_limit: float,
    existing_value: float,
) -> float:
    """The name's full dollar risk limit (not just what's left of it)."""
    reasoning = ticker_risk.get("reasoning")
    if isinstance(reasoning, dict):
        limit = reasoning.get("position_limit")
        if limit:
            return float(limit)
    return remaining_limit + existing_value


def _size_trade(
    direction: str,
    strength: float,
    *,
    current_price: float,
    ticker_risk: dict[str, Any],
    remaining_limit: float,
    long_shares: int,
    short_shares: int,
    allowed: dict[str, int],
) -> tuple[str, int, str]:
    """Trade toward a conviction-scaled target position.

    The target is `strength × total risk limit`, and only the *delta* between
    target and current position is ordered. Repeated cycles with the same
    signal therefore converge instead of stacking new orders every run.
    """
    confidence = int(min(100, max(30, strength * 100)))
    vote = f"Light vote: {direction} ({confidence}%)"

    if direction == "neutral" or strength < _TRADE_THRESHOLD:
        return "hold", 0, f"{vote} — below trade threshold"

    if direction == "bullish":
        unwind, extend = "cover", "buy"
        opposing, existing = short_shares, long_shares
    else:
        unwind, extend = "sell", "short"
        opposing, existing = long_shares, short_shares

    # Exit an opposing position before building the new one.
    if opposing > 0 and unwind in allowed:
        quantity = min(opposing, int(allowed[unwind]))
        if quantity > 0:
            return unwind, quantity, f"{vote} — unwind opposing position"

    if extend not in allowed or current_price <= 0:
        return "hold", 0, f"{vote} — no valid trade"

    total_limit = _total_position_limit(ticker_risk, remaining_limit, existing * current_price)
    target_shares = int((total_limit * min(strength, 1.0)) // current_price)
    delta = target_shares - existing
    if delta <= 0 or delta * current_price < _MIN_DELTA_FRACTION * total_limit:
        return "hold", 0, f"{vote} — at target ({existing}/{target_shares} shares)"

    quantity = min(delta, int(allowed[extend]))
    if quantity <= 0:
        return "hold", 0, f"{vote} — size capped to 0"
    return extend, quantity, f"{vote} — toward target {target_shares} shares"


def generate_light_decisions(
    tickers: list[str],
    analyst_signals: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Vote across rule-based analyst signals; respect risk limits."""
    risk_key = "risk_management_agent"
    risk_data = analyst_signals.get(risk_key, {})

    decisions: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        ticker_risk = risk_data.get(ticker, {})
        current_price = float(ticker_risk.get("current_price", 0.0))
        remaining_limit = float(ticker_risk.get("remaining_position_limit", 0.0))
        max_shares = int(remaining_limit // current_price) if current_price > 0 else 0

        if current_price <= 0:
            # No risk/price data (risk manager failed or feed gap) — never
            # trade blind, not even unwinds.
            decisions[ticker] = {
                "action": "hold",
                "quantity": 0,
                "confidence": 100,
                "reasoning": "No price/risk data (light) — holding",
            }
            continue

        ticker_signals: dict[str, dict[str, Any]] = {}
        for agent, signals in analyst_signals.items():
            if agent.startswith("risk_management") or ticker not in signals:
                continue
            payload = signals[ticker]
            if payload.get("signal") is not None:
                ticker_signals[agent] = payload

        allowed = compute_allowed_actions(
            [ticker],
            {ticker: current_price},
            {ticker: max_shares},
            portfolio,
        ).get(ticker, {"hold": 0})

        if set(allowed.keys()) == {"hold"}:
            decisions[ticker] = {
                "action": "hold",
                "quantity": 0,
                "confidence": 100,
                "reasoning": "No valid trade (light)",
            }
            continue

        direction, strength = _aggregate_ticker_signals(ticker_signals)
        confidence = int(min(100, max(30, strength * 100)))

        position = portfolio.get("positions", {}).get(ticker, {})
        action, quantity, reasoning = _size_trade(
            direction,
            strength,
            current_price=current_price,
            ticker_risk=ticker_risk,
            remaining_limit=remaining_limit,
            long_shares=int(position.get("long", 0) or 0),
            short_shares=int(position.get("short", 0) or 0),
            allowed=allowed,
        )

        decisions[ticker] = {
            "action": action,
            "quantity": quantity,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    return decisions
