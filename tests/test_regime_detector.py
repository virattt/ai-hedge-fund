import numpy as np
import pandas as pd
import pytest

from src.agents.regime_detector import RegimeState, detect_regime


def _make_prices(n: int, daily_return: float, daily_vol: float) -> pd.DataFrame:
    """Build a synthetic price series."""
    rng = np.random.default_rng(42)
    returns = rng.normal(daily_return, daily_vol, n)
    prices = 100 * np.cumprod(1 + returns)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": prices}, index=dates)


def test_returns_regime_state_dataclass():
    prices = _make_prices(252, 0.0005, 0.008)
    result = detect_regime(prices)
    assert isinstance(result, RegimeState)
    assert result.regime in ("Bull", "Bear", "High-Vol", "Risk-Off")
    assert result.trend in ("bull", "bear")
    assert result.vol_level in ("low", "elevated", "crisis")
    assert result.momentum in ("risk_on", "neutral", "risk_off")


def test_strong_uptrend_is_bull():
    prices = _make_prices(252, 0.001, 0.003)
    result = detect_regime(prices)
    assert result.trend == "bull"
    assert result.regime == "Bull"


def test_strong_downtrend_is_bear():
    prices = _make_prices(252, -0.002, 0.004)
    result = detect_regime(prices)
    assert result.trend == "bear"
    assert result.regime in ("Bear", "Risk-Off")


def test_high_vol_overrides_trend():
    prices = _make_prices(252, 0.0005, 0.025)
    result = detect_regime(prices)
    assert result.vol_level == "crisis"
    assert result.regime == "High-Vol"


def test_insufficient_data_returns_valid_state():
    prices = _make_prices(10, 0.001, 0.01)
    result = detect_regime(prices)
    assert isinstance(result, RegimeState)
    assert result.regime in ("Bull", "Bear", "High-Vol", "Risk-Off")


def test_regime_multiplier_bull():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Bull") == 1.0


def test_regime_multiplier_risk_off():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Risk-Off") == 0.40


def test_regime_multiplier_unknown_defaults_to_one():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Unknown") == 1.0
