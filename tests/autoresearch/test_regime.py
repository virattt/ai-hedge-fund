"""Tests for autoresearch.regime."""

import numpy as np
import pandas as pd
import pytest

from autoresearch.regime import get_regime, get_regime_with_drawdown, regime_scale


def test_get_regime_bull():
    close = pd.Series([100.0] * 19 + [105.0])
    assert get_regime(close, lookback=20, threshold=0.02) == "bull"


def test_get_regime_bear():
    close = pd.Series([100.0] * 19 + [97.0])
    assert get_regime(close, lookback=20, threshold=0.02) == "bear"


def test_get_regime_sideways():
    close = pd.Series([100.0] * 20)
    assert get_regime(close, lookback=20, threshold=0.02) == "sideways"


def test_get_regime_insufficient_data():
    close = pd.Series([100.0] * 5)
    assert get_regime(close, lookback=20) == "sideways"


def test_regime_scale():
    assert regime_scale("bull") == 1.0
    assert regime_scale("bear") == 0.5
    assert regime_scale("sideways") == 0.75
    assert regime_scale("unknown") == 0.75


def test_get_regime_with_drawdown_bear():
    close = pd.Series([100.0, 98.0, 94.0, 93.0, 95.0] * 4)
    assert get_regime_with_drawdown(close, lookback=20, drawdown_threshold=0.05) == "bear"


def test_get_regime_with_drawdown_bull():
    close = pd.Series([100.0] * 19 + [106.0])
    assert get_regime_with_drawdown(close, lookback=20, return_threshold=0.02) == "bull"
