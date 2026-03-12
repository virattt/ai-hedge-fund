"""
Risk controls for paper and live trading.
- Max drawdown: scale down or halt when portfolio DD exceeds threshold
- Stop-loss: per-ticker trim when unrealized loss exceeds threshold
- Volatility-based sizing: scale position by inverse volatility (target risk parity)
"""

from __future__ import annotations

import json
from pathlib import Path


def get_current_drawdown(state_path: str = ".paper_broker_state.json") -> float | None:
    """Return current drawdown from peak (0.0–1.0) if performance.csv exists."""
    perf_path = Path(__file__).resolve().parent / "logs" / "performance.csv"
    if not perf_path.exists():
        return None
    lines = perf_path.read_text().strip().splitlines()
    if len(lines) < 2:
        return None
    values = [float(row.split(",")[-1]) for row in lines[1:]]
    peak = max(values)
    current = values[-1] if values else 0
    if peak <= 0:
        return None
    return (peak - current) / peak


def should_halt_for_drawdown(
    state_path: str,
    max_drawdown_pct: float,
) -> tuple[bool, float | None]:
    """
    Return (should_halt, current_dd). Halt if DD > max_drawdown_pct.
    """
    dd = get_current_drawdown(state_path)
    if dd is None:
        return False, None
    return dd >= max_drawdown_pct / 100.0, dd


def scale_for_drawdown(
    regime_scale: float,
    state_path: str,
    max_drawdown_pct: float,
    dd_scale_factor: float = 0.5,
) -> float:
    """
    Reduce scale when approaching max DD. At max DD, scale *= dd_scale_factor.
    """
    dd = get_current_drawdown(state_path)
    if dd is None or max_drawdown_pct <= 0:
        return regime_scale
    threshold = max_drawdown_pct / 100.0
    if dd >= threshold:
        return regime_scale * dd_scale_factor
    # Linear ramp: at 80% of threshold, start scaling down
    ramp = 0.8 * threshold
    if dd <= ramp:
        return regime_scale
    # Interpolate between regime_scale and regime_scale * dd_scale_factor
    t = (dd - ramp) / (threshold - ramp)
    return regime_scale * (1 - t + t * dd_scale_factor)


def volatility_weights(
    returns_by_ticker: dict[str, list[float]],
) -> dict[str, float]:
    """
    Inverse-volatility weights for risk parity. Higher vol = lower weight.
    """
    import numpy as np
    weights = {}
    inv_vols = {}
    for ticker, rets in returns_by_ticker.items():
        if len(rets) < 5:
            inv_vols[ticker] = 1.0
            continue
        vol = np.std(rets)
        inv_vols[ticker] = 1.0 / (vol + 1e-8)
    total = sum(inv_vols.values())
    if total <= 0:
        return {t: 1.0 / len(inv_vols) for t in inv_vols}
    return {t: inv_vols[t] / total for t in inv_vols}


def apply_stop_loss(
    positions: dict[str, dict],
    prices: dict[str, float],
    stop_loss_pct: float,
) -> dict[str, int]:
    """
    Return tickers that should be trimmed to 0 due to stop-loss.
    positions: {ticker: {quantity, avg_price}}
    """
    trim = {}
    for ticker, pos in positions.items():
        qty = pos.get("quantity", 0)
        avg = pos.get("avg_price", 0)
        if qty <= 0 or avg <= 0 or ticker not in prices:
            continue
        p = prices[ticker]
        loss_pct = (avg - p) / avg if avg > 0 else 0
        if loss_pct >= stop_loss_pct / 100.0:
            trim[ticker] = 0
    return trim
