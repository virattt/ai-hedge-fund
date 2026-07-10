"""Deterministic portfolio decisions for light (no-LLM) cycles."""

from __future__ import annotations

from typing import Any

from src.agents.portfolio_manager import compute_allowed_actions

_SIGNAL_SCORE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}


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
        current_price = float(risk_data.get(ticker, {}).get("current_price", 0.0))
        position_limit = float(risk_data.get(ticker, {}).get("remaining_position_limit", 0.0))
        max_shares = int(position_limit // current_price) if current_price > 0 else 0

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

        action = "hold"
        quantity = 0
        reasoning = f"Light vote: {direction} ({confidence}%)"

        if direction == "bullish" and strength >= 0.35:
            if "buy" in allowed:
                action = "buy"
                quantity = max(1, int(max_shares * min(strength, 0.5)))
            elif "cover" in allowed:
                action = "cover"
                quantity = max(1, int(allowed["cover"] * min(strength, 0.5)))
        elif direction == "bearish" and strength >= 0.35:
            if "sell" in allowed:
                action = "sell"
                quantity = max(1, int(allowed["sell"] * min(strength, 0.5)))
            elif "short" in allowed:
                action = "short"
                quantity = max(1, int(allowed["short"] * min(strength, 0.5)))

        if action != "hold":
            cap = allowed.get(action, 0)
            quantity = min(quantity, int(cap)) if cap else 0
            if quantity <= 0:
                action = "hold"
                quantity = 0
                reasoning = "Light: signal present but size capped to 0"

        decisions[ticker] = {
            "action": action,
            "quantity": quantity,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    return decisions
