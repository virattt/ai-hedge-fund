"""Alpha Learnability tests: IC math, shrinkage, regimes, replay orchestration."""

from __future__ import annotations

import numpy as np
import pandas as pd

from integrations.universe.config import UniverseConfig
from integrations.universe.learnability import (
    checkpoint_dates,
    classify_regime,
    compute_learnability,
    forward_returns,
    score_ticker_learnability,
    signed_score,
)

from tests.integrations.universe.universe_fixtures import make_prices, trading_calendar


def test_signed_score_confidence_weighted_vote():
    score = signed_score(
        {
            "technical_analyst": {"signal": "bullish", "confidence": 80},
            "fundamentals_analyst": {"signal": "bearish", "confidence": 20},
        }
    )
    assert score is not None and score > 0

    assert signed_score({}) is None
    neutral = signed_score({"a": {"signal": "neutral", "confidence": 50}})
    assert neutral == 0.0


def test_predictive_signals_outscore_random():
    rng = np.random.default_rng(0)
    n = 40
    fwd = rng.normal(0, 0.02, n)

    good_obs = [(float(np.sign(r)), {5: float(r)}, "up_lowvol") for r in fwd]
    random_obs = [
        (float(rng.choice([-1.0, 1.0])), {5: float(r)}, "up_lowvol") for r in fwd
    ]

    good = score_ticker_learnability("GOOD", good_obs)
    random_result = score_ticker_learnability("RAND", random_obs)
    assert good.score > random_result.score
    # Binary signals vs continuous returns cap Spearman below 1; still strongly positive.
    assert good.ic is not None and good.ic > 0.7
    assert good.hit_rate == 1.0


def test_shrinkage_discounts_small_samples():
    obs = [(1.0, {5: 0.02}, "up_lowvol"), (-1.0, {5: -0.02}, "up_lowvol"), (1.0, {5: 0.03}, "up_lowvol")]
    small = score_ticker_learnability("SMALL", obs)
    large = score_ticker_learnability("LARGE", obs * 20)
    assert 0 < small.score < large.score


def test_regime_inconsistency_penalized():
    rng = np.random.default_rng(1)
    fwd = rng.normal(0, 0.02, 40)
    consistent = [
        (float(np.sign(r)), {5: float(r)}, "up_lowvol" if i % 2 else "down_highvol")
        for i, r in enumerate(fwd)
    ]
    # Perfect in one regime, inverted in the other — same overall sample.
    inconsistent = [
        (float(np.sign(r)) if i % 2 else -float(np.sign(r)), {5: float(r)},
         "up_lowvol" if i % 2 else "down_highvol")
        for i, r in enumerate(fwd)
    ]
    good = score_ticker_learnability("CONS", consistent)
    flaky = score_ticker_learnability("FLAKY", inconsistent)
    assert good.score > flaky.score
    assert len(good.regime_ics) == 2


def test_no_signals_scores_zero():
    result = score_ticker_learnability("NONE", [])
    assert result.score == 0.0 and result.n_signals == 0
    all_neutral = score_ticker_learnability("NEUT", [(0.0, {5: 0.01}, "up_lowvol")] * 10)
    assert all_neutral.score == 0.0


def test_forward_returns_respects_data_boundary():
    closes = make_prices(n_days=50)["close"]
    checkpoint = closes.index[45]
    fwd = forward_returns(closes, checkpoint, [3, 21])
    assert 3 in fwd  # 45 + 3 < 50
    assert 21 not in fwd  # would run past the data


def test_checkpoint_dates_leave_forward_room():
    calendar = trading_calendar(300, end="2026-06-30")
    config = UniverseConfig(learnability_checkpoint_days=21, learnability_lookback_days=252)
    checkpoints = checkpoint_dates(calendar, "2026-06-30", config)
    assert checkpoints
    max_horizon = max(config.learnability_horizons)
    assert all(c <= calendar[-max_horizon - 1] for c in checkpoints)


def test_classify_regime_buckets():
    calendar = trading_calendar(300)
    rising = pd.Series(np.linspace(100, 150, 300), index=calendar)
    regime = classify_regime(rising, calendar[-1])
    assert regime.startswith("up_")
    assert classify_regime(rising.head(10), calendar[9]) == "unknown"


def test_compute_learnability_with_stub_replayer():
    prices = {"WIN": make_prices(seed=2), "LOSE": make_prices(seed=3)}
    spy = make_prices(seed=4)["close"]
    config = UniverseConfig(
        learnability_checkpoint_days=10,
        learnability_lookback_days=400,
        learnability_horizons=(5,),
    )

    def replayer(tickers, checkpoint_date, lookback_start):
        out = {}
        for ticker in tickers:
            closes = prices[ticker]["close"]
            fwd = forward_returns(closes, pd.Timestamp(checkpoint_date), [5])
            if not fwd:
                continue
            # WIN's analysts predict the future perfectly; LOSE's invert it.
            direction = np.sign(fwd[5]) if ticker == "WIN" else -np.sign(fwd[5])
            signal = "bullish" if direction > 0 else "bearish" if direction < 0 else "neutral"
            out[ticker] = {"technical_analyst": {"signal": signal, "confidence": 90}}
        return out

    frames = {t: p for t, p in prices.items()}
    results = compute_learnability(frames, spy, "2026-06-30", config, replayer)
    assert results["WIN"].score > 0 > results["LOSE"].score


def test_replayer_caches_no_signal_outcomes(tmp_path, monkeypatch):
    """An analyst that ran cleanly but produced no signal must not force a
    re-run on the next build (this made every build re-replay everything)."""
    from integrations.universe.learnability import LightAnalystReplayer

    config = UniverseConfig(
        signal_cache_dir=str(tmp_path),
        learnability_analysts=("technical_analyst", "sentiment_analyst"),
    )
    replayer = LightAnalystReplayer(config)
    calls: list[list[str]] = []

    def fake_run(tickers, checkpoint, lookback):
        calls.append(list(tickers))
        # technical yields a signal; sentiment runs cleanly with nothing to say
        return (
            {t: {"technical_analyst": {"signal": "bullish", "confidence": 60}} for t in tickers},
            {"technical_analyst", "sentiment_analyst"},
        )

    monkeypatch.setattr(replayer, "_run_analysts", fake_run)
    replayer(["AAA"], "2026-01-05", "2025-10-07")
    second = replayer(["AAA"], "2026-01-05", "2025-10-07")
    assert calls == [["AAA"]]  # second call was a pure cache hit
    assert second["AAA"]["technical_analyst"]["signal"] == "bullish"
    assert "_attempted" not in second["AAA"]


def test_replayer_retries_crashed_analysts(tmp_path, monkeypatch):
    """Analysts that crashed (e.g. provider 429) are retried and merged."""
    from integrations.universe.learnability import LightAnalystReplayer

    config = UniverseConfig(
        signal_cache_dir=str(tmp_path),
        learnability_analysts=("technical_analyst", "sentiment_analyst"),
    )
    replayer = LightAnalystReplayer(config)
    outcomes = iter(
        [
            (  # first build: sentiment crashed
                {"AAA": {"technical_analyst": {"signal": "bearish", "confidence": 70}}},
                {"technical_analyst"},
            ),
            (  # second build: sentiment recovered
                {"AAA": {"sentiment_analyst": {"signal": "bullish", "confidence": 55}}},
                {"technical_analyst", "sentiment_analyst"},
            ),
        ]
    )
    calls: list[list[str]] = []

    def fake_run(tickers, checkpoint, lookback):
        calls.append(list(tickers))
        return next(outcomes)

    monkeypatch.setattr(replayer, "_run_analysts", fake_run)
    replayer(["AAA"], "2026-01-05", "2025-10-07")
    merged = replayer(["AAA"], "2026-01-05", "2025-10-07")
    assert len(calls) == 2  # retried because sentiment never ran cleanly
    assert merged["AAA"]["technical_analyst"]["signal"] == "bearish"
    assert merged["AAA"]["sentiment_analyst"]["signal"] == "bullish"

    third = replayer(["AAA"], "2026-01-05", "2025-10-07")
    assert len(calls) == 2  # now fully cached
    assert third["AAA"]["sentiment_analyst"]["signal"] == "bullish"
