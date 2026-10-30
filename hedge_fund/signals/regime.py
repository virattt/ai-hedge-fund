"""Regime alpha model — market-state detection with a Gaussian HMM.

Fits a Hidden Markov Model to daily features of a market proxy (IWM by
default), names each hidden state CALM_UP / CHOP / STRESS / CRASH by its
average return and volatility, and turns today's state into an exposure
dial: 1.0 in CALM_UP, 0.5 in CHOP, 0.25 in STRESS, 0.0 in CRASH.

The view is market-level, so every ticker gets the same conviction on a
given date. It is a risk-on / risk-off overlay, not a stock picker.

Point-in-time rules:
- Features on day t use data up to t; z-scores use the mean and spread
  from before t.
- State probabilities come from the forward filter, P(state_t | data_1..t).
  Never Viterbi or smoothed probabilities (hmmlearn's predict /
  predict_proba), which use later days.
- The HMM is fit only on bars on or before the as-of date, and refit
  every `refit_every` trading days.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

FEATURES = ["log_return", "realized_vol", "day_range", "volume_ratio", "trend"]
LABELS = ["CALM_UP", "CHOP", "STRESS", "CRASH"]
EXPOSURE = {"CALM_UP": 1.0, "CHOP": 0.5, "STRESS": 0.25, "CRASH": 0.0, None: 0.0}

_STANDARDIZE_MIN_DAYS = 252        # burn-in before z-scores exist
_MIN_FIT_DAYS = 756                # ~3 years of features before the first fit
_SWITCH_PROB = 0.70                # a new state must pass this probability...
_SWITCH_HOLD_DAYS = 3              # ...for this many days in a row
_COOLDOWN_DAYS = 5                 # then no switching again for this many days
_DANGER_NEXT_DAY_PROB = 0.25       # P(STRESS or CRASH tomorrow) above this -> half size
_UNCERTAIN_GAP = 0.15              # top two states this close -> size zero
_STALE_DAYS = 4                    # last bar older than this (calendar days) -> flat


@dataclass
class Decision:
    state: str | None
    size: float
    reason: str


class RegimeModel(QuantModel):
    """Long-only exposure dial from an HMM market regime.

    `predict(ticker, date)` returns conviction in [0, 1]: how much risk to
    take as of `date`. Abstains (0.0, metadata["abstained"]) until there is
    enough history to fit.
    """

    investment_approach = "long_only"

    def __init__(
        self,
        *,
        market_ticker: str = "IWM",
        history_start: str = "2000-01-01",
        refit_every: int = 30,
        n_states: tuple[int, ...] = (2, 3, 4, 5),
        n_restarts: int = 5,
        seed: int = 42,
    ) -> None:
        self._market_ticker = market_ticker
        self._history_start = history_start
        self._refit_every = refit_every
        self._n_states = n_states
        self._n_restarts = n_restarts
        self._seed = seed
        self._prices: pd.DataFrame | None = None
        self._prices_end: str | None = None
        self._model = None          # fitted GaussianHMM
        self._fit_date = None       # last feature date the model was fit on
        self._fit_pos: int = -1     # position of that date in the feature index
        self._by_date: dict[str, Signal] = {}

    @property
    def name(self) -> str:
        return "regime"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        if date not in self._by_date:
            self._by_date[date] = self._assess(date, data_client)
        cached = self._by_date[date]
        return cached.model_copy(update={"ticker": ticker})

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def _assess(self, date: str, data_client: DataClient) -> Signal:
        as_of = pd.Timestamp(date)
        prices = self._load_prices(date, data_client)
        prices = prices[prices.index <= as_of]   # point-in-time: nothing after `date`
        feats = build_features(prices)
        if len(feats) < _MIN_FIT_DAYS:
            return self._abstain(date, f"need {_MIN_FIT_DAYS} feature days, have {len(feats)}")

        X = feats[FEATURES].values
        self._maybe_refit(feats.index, X)
        probs = forward_filter(self._model, X)
        labels, stats = label_states(probs, feats["raw_return"].values)
        label_probs = to_label_probs(probs, labels)
        danger = danger_next_day(probs, self._model, labels)
        decision = apply_switching_rules(label_probs, danger)[-1]

        last_bar = feats.index[-1]
        if (as_of - last_bar).days > _STALE_DAYS:
            decision = Decision(None, 0.0, f"data is stale (last bar {last_bar.date()}), going flat")

        return Signal(
            model_name=self.name,
            ticker="",
            date=date,
            value=self._normalize_to_signal(decision.size, 0.0, 1.0),
            reasoning=f"{self._market_ticker} regime: {decision.reason}",
            components={lab: round(float(p), 4) for lab, p in zip(LABELS, label_probs[-1])},
            metadata={
                "state": decision.state,
                "danger_next_day": round(float(danger[-1]), 4),
                "n_states": int(self._model.n_components),
                "fit_date": str(self._fit_date.date()),
                "market_ticker": self._market_ticker,
            },
        )

    def _maybe_refit(self, index: pd.DatetimeIndex, X: np.ndarray) -> None:
        """Refit when there is no model, the schedule says so, or the cached
        model was fit on data after this date (a call that goes back in time)."""
        last = index[-1]
        stale = self._model is None or self._fit_date > last
        if not stale and len(index) - 1 - self._fit_pos < self._refit_every:
            return
        self._model = fit_hmm(X, self._n_states, self._n_restarts, self._seed)
        self._fit_date, self._fit_pos = last, len(index) - 1

    def _load_prices(self, date: str, data_client: DataClient) -> pd.DataFrame:
        """Fetch the market proxy once, extending only when a later date is asked for."""
        if self._prices is None or date > self._prices_end:
            bars = data_client.get_prices(self._market_ticker, self._history_start, date)
            df = pd.DataFrame([b.model_dump() for b in bars])
            if df.empty:
                df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])
            df.index = pd.to_datetime(df["time"].str[:10])
            self._prices = df.sort_index()[["open", "high", "low", "close", "volume"]].astype(float)
            self._prices_end = date
        return self._prices

    def _abstain(self, date: str, why: str) -> Signal:
        return Signal(model_name=self.name, ticker="", date=date, value=0.0,
                      reasoning=why, metadata={"abstained": True})


# ---------------------------------------------------------------------------
# HMM pieces (pure functions, testable on their own)
# ---------------------------------------------------------------------------

def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily OHLCV -> the five standardized features the HMM reads.

    Expects lowercase open/high/low/close/volume columns on a date index.
    """
    close, high, low, vol = prices["close"], prices["high"], prices["low"], prices["volume"]
    raw = pd.DataFrame(index=prices.index)
    raw["log_return"] = np.log(close).diff()
    raw["realized_vol"] = raw["log_return"].rolling(20).std()
    raw["day_range"] = np.log(high / low)
    raw["volume_ratio"] = np.log(vol / vol.rolling(20).mean())
    raw["trend"] = np.log(close / close.rolling(50).mean())
    raw = raw.replace([np.inf, -np.inf], np.nan)

    # Standardize with stats from before day t (shift 1), so day t never sees itself
    past_mean = raw.expanding(min_periods=_STANDARDIZE_MIN_DAYS).mean().shift(1)
    past_std = raw.expanding(min_periods=_STANDARDIZE_MIN_DAYS).std().shift(1)
    z = ((raw - past_mean) / past_std).dropna()
    z["raw_return"] = raw["log_return"].reindex(z.index)  # for labeling only, not fed to the HMM
    return z


def _n_params(n: int, d: int) -> int:
    return (n - 1) + n * (n - 1) + n * d + n * d * (d + 1) // 2


def fit_hmm(X: np.ndarray, n_states=(2, 3, 4, 5), n_restarts: int = 5, seed: int = 42):
    """Fit 2-5 state Gaussian HMMs with restarts; pick by BIC, preferring
    the smaller model when its BIC is within 0.5% of the best."""
    from hmmlearn.hmm import GaussianHMM  # optional dependency, only needed here

    results = {}
    for n in n_states:
        best = None
        for k in range(n_restarts):
            m = GaussianHMM(n_components=n, covariance_type="full", n_iter=200,
                            random_state=seed + k, tol=1e-3)
            try:
                m.fit(X)
                ll = m.score(X)
            except (ValueError, np.linalg.LinAlgError):
                continue
            if best is None or ll > best[1]:
                best = (m, ll)
        if best:
            results[n] = (best[0], -2 * best[1] + _n_params(n, X.shape[1]) * np.log(len(X)))
    if not results:
        raise RuntimeError("no HMM fit converged")
    best_bic = min(b for _, b in results.values())
    for n in sorted(results):
        if (results[n][1] - best_bic) / abs(best_bic) < 0.005:
            return results[n][0]
    raise RuntimeError("no HMM fit")  # unreachable: the best model always qualifies


def forward_filter(model, X: np.ndarray) -> np.ndarray:
    """P(state_t | data up to t) for every day. Never uses later days."""
    n = model.n_components
    log_b = np.column_stack([
        multivariate_normal(model.means_[s], model.covars_[s], allow_singular=True).logpdf(X)
        for s in range(n)
    ])
    log_A = np.log(model.transmat_ + 1e-300)
    out = np.empty((len(X), n))
    log_alpha = np.log(model.startprob_ + 1e-300) + log_b[0]
    out[0] = np.exp(log_alpha - logsumexp(log_alpha))
    for t in range(1, len(X)):
        log_alpha = logsumexp(log_alpha[:, None] + log_A, axis=0) + log_b[t]
        log_alpha -= logsumexp(log_alpha)
        out[t] = np.exp(log_alpha)
    return out


def label_states(probs: np.ndarray, returns: np.ndarray) -> tuple[dict, dict]:
    """Name each hidden state by its probability-weighted mean return and vol."""
    overall_vol = returns.std()
    stats = {}
    for s in range(probs.shape[1]):
        w = probs[:, s]
        mean = (w * returns).sum() / w.sum()
        stats[s] = (mean, np.sqrt((w * (returns - mean) ** 2).sum() / w.sum()))
    highest_vol = max(stats, key=lambda s: stats[s][1])
    labels = {}
    for s, (mean, vol) in stats.items():
        if s == highest_vol and mean < 0:
            labels[s] = "CRASH"
        elif vol > overall_vol:
            labels[s] = "STRESS"
        elif mean > 0:
            labels[s] = "CALM_UP"
        else:
            labels[s] = "CHOP"
    return labels, stats


def to_label_probs(probs: np.ndarray, labels: dict) -> np.ndarray:
    """Sum state probabilities that share a label. Columns follow LABELS."""
    out = np.zeros((len(probs), len(LABELS)))
    for s, lab in labels.items():
        out[:, LABELS.index(lab)] += probs[:, s]
    return out


def danger_next_day(probs: np.ndarray, model, labels: dict) -> np.ndarray:
    """P(STRESS or CRASH tomorrow) = today's filtered probs x transition matrix."""
    bad = [s for s, lab in labels.items() if lab in ("STRESS", "CRASH")]
    return (probs @ model.transmat_)[:, bad].sum(axis=1) if bad else np.zeros(len(probs))


def apply_switching_rules(label_probs: np.ndarray, danger: np.ndarray) -> list[Decision]:
    """Hysteresis so the dial does not flip on noise.

    1-3. A new state needs > 0.70 probability for 3 days running, then a
         5-day cooldown before the next switch.
    4.   In CALM_UP / CHOP, P(STRESS or CRASH tomorrow) > 0.25 halves size.
    5.   Top two labels within 0.15 of each other -> size zero.
    """
    active, candidate, streak, cooldown = None, None, 0, 0
    decisions = []
    for p, d in zip(label_probs, danger):
        top = int(np.argmax(p))
        top_label = LABELS[top]
        cooldown = max(0, cooldown - 1)

        if top_label != active and p[top] > _SWITCH_PROB:
            streak = streak + 1 if candidate == top_label else 1
            candidate = top_label
            if streak >= _SWITCH_HOLD_DAYS and cooldown == 0:
                active, cooldown, streak = top_label, _COOLDOWN_DAYS, 0
        else:
            candidate, streak = None, 0

        size, reason = EXPOSURE[active], f"state {active}"
        if p[top] - np.sort(p)[-2] < _UNCERTAIN_GAP:
            size, reason = 0.0, f"uncertain: top two states within {_UNCERTAIN_GAP}"
        elif d > _DANGER_NEXT_DAY_PROB and active in ("CALM_UP", "CHOP"):
            size, reason = size / 2, f"state {active}, {d:.0%} chance of STRESS/CRASH tomorrow, half size"
        decisions.append(Decision(active, size, reason))
    return decisions
