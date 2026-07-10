"""Alpha Learnability — how well OUR pipeline has predicted each stock.

Replays the rule-based analysts (the same agent functions the light trading
cycle runs, zero LLM cost) at historical checkpoints, compares their signals
against forward returns, and scores each ticker on:

- Information coefficient (Spearman rank corr of signal vs forward return)
- Directional hit rate
- Consistency across market regimes (SPY up/down x high/low volatility)

A stock the pipeline has predicted accurately AND consistently across
regimes scores high; a stock with occasional lucky calls does not: the score
is shrunk toward zero by sample size and penalized by cross-regime IC
dispersion.

Replayed signals are cached to disk (one JSON per ticker) so rebuilding a
universe or building historical universes for backtests is incremental.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from integrations.universe.cache import JsonDiskCache
from integrations.universe.config import UniverseConfig

logger = logging.getLogger(__name__)

_SIGNAL_VALUE = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
# Cache bookkeeping key: analysts that ran cleanly for a checkpoint, even if
# they produced no signal. Not a signal payload.
_ATTEMPTED_KEY = "_attempted"
_SHRINK_PRIOR = 20  # pseudo-observations pulling the score toward zero
_IC_WEIGHT = 0.7
_HIT_WEIGHT = 0.3
_REGIME_PENALTY = 0.5
_MIN_REGIME_OBS = 4
_REPLAY_LOOKBACK_DAYS = 90  # analysis window handed to the analysts

# replayer(tickers, checkpoint_date, lookback_start) ->
#   {ticker: {analyst: {"signal": str, "confidence": float}}}
SignalReplayer = Callable[[Sequence[str], str, str], dict[str, dict[str, dict[str, Any]]]]


@dataclass
class LearnabilityResult:
    ticker: str
    score: float
    ic: float | None = None
    hit_rate: float | None = None
    n_signals: int = 0
    regime_ics: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal replay (production path)
# ---------------------------------------------------------------------------

class LightAnalystReplayer:
    """Replay the rule-based analysts at a historical checkpoint, with disk cache.

    Signals are cached per ticker as {checkpoint_date: {analyst: payload}} so
    a re-run only computes checkpoints it has never seen.
    """

    def __init__(self, config: UniverseConfig) -> None:
        self._analysts = list(config.learnability_analysts)
        self._cache = JsonDiskCache(config.signal_cache_dir)

    def __call__(
        self, tickers: Sequence[str], checkpoint_date: str, lookback_start: str
    ) -> dict[str, dict[str, dict[str, Any]]]:
        cached: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for ticker in tickers:
            stored = self._cache.get("signals", ticker) or {}
            entry = stored.get(checkpoint_date)
            if entry is not None:
                day = {k: v for k, v in entry.items() if k != _ATTEMPTED_KEY}
                # An analyst counts as covered if it produced a signal OR ran
                # cleanly and just had nothing to say. Only analysts that
                # *crashed* (e.g. provider 429) are retried on a later build —
                # otherwise one bad build forces a full re-replay forever.
                attempted = set(entry.get(_ATTEMPTED_KEY, day.keys()))
                if set(self._analysts) <= (set(day.keys()) | attempted):
                    cached[ticker] = day
                    continue
            missing.append(ticker)

        if missing:
            fresh, succeeded = self._run_analysts(missing, checkpoint_date, lookback_start)
            for ticker in missing:
                stored = self._cache.get("signals", ticker) or {}
                entry = dict(stored.get(checkpoint_date) or {})
                previously_attempted = set(entry.pop(_ATTEMPTED_KEY, []))
                entry.update(fresh.get(ticker, {}))
                entry[_ATTEMPTED_KEY] = sorted(previously_attempted | succeeded)
                stored[checkpoint_date] = entry
                self._cache.set("signals", ticker, stored)
                cached[ticker] = {k: v for k, v in entry.items() if k != _ATTEMPTED_KEY}
        return cached

    def _run_analysts(
        self, tickers: list[str], checkpoint_date: str, lookback_start: str
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], set[str]]:
        """Run each rule-based analyst once for the whole ticker batch.

        Returns the signals plus the set of analysts that completed without
        raising (so no-signal outcomes can be cached as final).
        """
        from src.utils.analysts import get_analyst_nodes

        analyst_nodes = get_analyst_nodes()
        out: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in tickers}
        succeeded: set[str] = set()

        for key in self._analysts:
            if key not in analyst_nodes:
                logger.warning("Unknown learnability analyst %s — skipping", key)
                continue
            agent_id, agent_func = analyst_nodes[key]
            state = _make_state(tickers, lookback_start, checkpoint_date)
            try:
                update = agent_func(state)
            except Exception as exc:
                logger.warning(
                    "Analyst %s failed at %s for %d tickers (will retry next build): %s",
                    key, checkpoint_date, len(tickers), exc,
                )
                continue
            succeeded.add(key)
            signals = (update.get("data", {}) or {}).get("analyst_signals", {}).get(agent_id, {})
            for ticker in tickers:
                payload = signals.get(ticker)
                if isinstance(payload, dict) and payload.get("signal") in _SIGNAL_VALUE:
                    out[ticker][key] = {
                        "signal": payload["signal"],
                        "confidence": float(payload.get("confidence") or 0.0),
                    }
        return out, succeeded


def _make_state(tickers: Sequence[str], start_date: str, end_date: str) -> dict[str, Any]:
    """Minimal AgentState for running analyst functions outside the graph."""
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="Universe learnability replay.")],
        "data": {
            "tickers": list(tickers),
            "portfolio": {},
            "start_date": start_date,
            "end_date": end_date,
            "analyst_signals": {},
        },
        "metadata": {
            "show_reasoning": False,
            "model_name": "none",
            "model_provider": "none",
        },
    }


def signed_score(day_signals: dict[str, dict[str, Any]]) -> float | None:
    """Confidence-weighted vote across analysts, in [-1, +1]."""
    total, weight = 0.0, 0.0
    for payload in day_signals.values():
        direction = _SIGNAL_VALUE.get(payload.get("signal"))
        if direction is None:
            continue
        confidence = max(float(payload.get("confidence") or 0.0), 1.0) / 100.0
        total += direction * confidence
        weight += confidence
    if weight <= 0:
        return None
    return total / weight


# ---------------------------------------------------------------------------
# Regimes and scoring math
# ---------------------------------------------------------------------------

def classify_regime(spy_closes: pd.Series, checkpoint: pd.Timestamp) -> str:
    """Trailing SPY direction x volatility bucket at *checkpoint*."""
    history = spy_closes.loc[:checkpoint]
    if len(history) < 64:
        return "unknown"
    returns = history.pct_change().dropna()
    trailing_return = float(history.iloc[-1] / history.iloc[-63] - 1.0)
    trailing_vol = float(returns.tail(21).std())
    median_vol = float(returns.rolling(21).std().median())
    direction = "up" if trailing_return >= 0 else "down"
    vol_bucket = "highvol" if trailing_vol > median_vol else "lowvol"
    return f"{direction}_{vol_bucket}"


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    from scipy.stats import spearmanr

    rho = spearmanr(a, b).statistic
    return float(rho) if np.isfinite(rho) else None


def score_ticker_learnability(
    ticker: str,
    observations: list[tuple[float, dict[int, float], str]],
) -> LearnabilityResult:
    """Score one ticker from (signal, {horizon: fwd_return}, regime) tuples.

    score = shrink * (0.7 * IC + 0.3 * scaled_hit_rate) - 0.5 * regime_IC_std
    where shrink = n / (n + 20). Only non-neutral signals count.
    """
    active = [(s, f, r) for s, f, r in observations if abs(s) > 1e-9 and f]
    n = len(active)
    if n == 0:
        return LearnabilityResult(ticker=ticker, score=0.0, n_signals=0)

    horizons = sorted({h for _, fwd, _ in active for h in fwd})
    signals = np.array([s for s, _, _ in active])

    ics: list[float] = []
    for horizon in horizons:
        pairs = [(s, f[horizon]) for s, f, _ in active if horizon in f]
        if len(pairs) < 3:
            continue
        ic = _spearman(np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs]))
        if ic is not None:
            ics.append(ic)
    mean_ic = float(np.mean(ics)) if ics else None

    # Hit rate on the shortest horizon
    shortest = horizons[0]
    hits = [
        1.0 if np.sign(s) == np.sign(f[shortest]) else 0.0
        for s, f, _ in active
        if shortest in f and f[shortest] != 0
    ]
    hit_rate = float(np.mean(hits)) if hits else None

    # Cross-regime consistency (shortest horizon)
    regime_ics: dict[str, float] = {}
    for regime in sorted({r for _, _, r in active if r != "unknown"}):
        pairs = [(s, f[shortest]) for s, f, r in active if r == regime and shortest in f]
        if len(pairs) < _MIN_REGIME_OBS:
            continue
        ic = _spearman(np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs]))
        if ic is not None:
            regime_ics[regime] = ic

    ic_component = mean_ic if mean_ic is not None else 0.0
    hit_component = (hit_rate - 0.5) * 2.0 if hit_rate is not None else 0.0
    raw = _IC_WEIGHT * ic_component + _HIT_WEIGHT * hit_component

    shrink = n / (n + _SHRINK_PRIOR)
    penalty = _REGIME_PENALTY * float(np.std(list(regime_ics.values()))) if len(regime_ics) >= 2 else 0.0
    score = shrink * raw - penalty

    return LearnabilityResult(
        ticker=ticker,
        score=score,
        ic=mean_ic,
        hit_rate=hit_rate,
        n_signals=n,
        regime_ics=regime_ics,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def checkpoint_dates(
    calendar: pd.DatetimeIndex,
    as_of: str,
    config: UniverseConfig,
) -> list[pd.Timestamp]:
    """Every Nth trading day, leaving room for the longest forward horizon."""
    max_horizon = max(config.learnability_horizons)
    cutoff = pd.Timestamp(as_of)
    days = [d for d in calendar if d <= cutoff]
    days = days[-(config.learnability_lookback_days):]
    # Drop the tail where forward returns would run past as_of.
    if max_horizon > 0:
        days = days[: -max_horizon] if len(days) > max_horizon else []
    return days[:: config.learnability_checkpoint_days]


def forward_returns(
    closes: pd.Series, checkpoint: pd.Timestamp, horizons: Sequence[int]
) -> dict[int, float]:
    """Trading-day forward returns from *checkpoint*, only if data exists."""
    positions = closes.index.get_indexer([checkpoint], method="ffill")
    if positions[0] == -1:
        return {}
    start = positions[0]
    base = float(closes.iloc[start])
    if base <= 0:
        return {}
    out: dict[int, float] = {}
    for horizon in horizons:
        idx = start + horizon
        if idx < len(closes):
            out[horizon] = float(closes.iloc[idx]) / base - 1.0
    return out


def compute_learnability(
    price_frames: dict[str, pd.DataFrame],
    spy_closes: pd.Series,
    as_of: str,
    config: UniverseConfig,
    replayer: SignalReplayer | None = None,
) -> dict[str, LearnabilityResult]:
    """Replay signals for all tickers across checkpoints and score each one."""
    if replayer is None:
        replayer = LightAnalystReplayer(config)

    checkpoints = checkpoint_dates(spy_closes.index, as_of, config)
    if not checkpoints:
        logger.warning("No learnability checkpoints available before %s", as_of)
        return {t: LearnabilityResult(ticker=t, score=0.0) for t in price_frames}

    tickers = list(price_frames)
    observations: dict[str, list[tuple[float, dict[int, float], str]]] = {t: [] for t in tickers}

    for checkpoint in checkpoints:
        date_str = checkpoint.strftime("%Y-%m-%d")
        lookback_start = (
            datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=_REPLAY_LOOKBACK_DAYS)
        ).strftime("%Y-%m-%d")
        regime = classify_regime(spy_closes, checkpoint)

        try:
            day_signals = replayer(tickers, date_str, lookback_start)
        except Exception as exc:
            logger.warning("Signal replay failed at %s: %s", date_str, exc)
            continue

        for ticker in tickers:
            score = signed_score(day_signals.get(ticker, {}))
            if score is None:
                continue
            fwd = forward_returns(
                price_frames[ticker]["close"], checkpoint, config.learnability_horizons
            )
            if not fwd:
                continue
            observations[ticker].append((score, fwd, regime))

    return {
        ticker: score_ticker_learnability(ticker, obs)
        for ticker, obs in observations.items()
    }
