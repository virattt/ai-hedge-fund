"""Tests for ``_with_retry`` backoff/jitter in :mod:`src.tools.api_akshare`.

The shared spot-table fetch is the single gating call for every ticker's
market cap, so it must absorb transient ``RemoteDisconnected`` errors with
exponential backoff + jitter rather than the one-shot fixed retry used by the
per-ticker callers.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.tools import api_akshare


def _no_jitter(lo: float, hi: float) -> float:
    """Make ``random.uniform`` deterministic so sleep values are exact."""
    return 0.0


def test_with_retry_backs_off_exponentially_then_succeeds():
    """Transient errors are retried with growing delays until success."""
    sleeps: list[float] = []
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 4:  # fail the first 3, succeed on the 4th
            raise ConnectionError("RemoteDisconnected: Remote end closed connection")
        return pd.DataFrame({"a": [1]})

    with patch.object(api_akshare.time, "sleep", lambda d: sleeps.append(d)), patch.object(
        api_akshare.random, "uniform", _no_jitter
    ):
        result = api_akshare._with_retry(flaky, retries=3, delay=2.0, backoff=2.0, jitter=1.0)

    assert result.equals(pd.DataFrame({"a": [1]}))
    assert attempts["n"] == 4  # 1 initial + 3 retries
    assert sleeps == [2.0, 4.0, 8.0]  # delay * backoff**attempt


def test_with_retry_applies_jitter_on_top_of_backoff():
    """Jitter adds up to ``jitter`` seconds to each computed backoff."""
    sleeps: list[float] = []

    def always_fail():
        raise ConnectionError("timeout")

    with patch.object(api_akshare.time, "sleep", lambda d: sleeps.append(d)), patch.object(
        api_akshare.random, "uniform", lambda lo, hi: hi  # always add full jitter
    ):
        with pytest.raises(ConnectionError):
            api_akshare._with_retry(always_fail, retries=2, delay=2.0, backoff=2.0, jitter=1.0)

    # backoff 2,4 + full jitter 1 each → 3.0, 5.0
    assert sleeps == [3.0, 5.0]


def test_with_retry_gives_up_after_max_retries():
    """A persistent transient error re-raises after retries are exhausted."""
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise ConnectionError("RemoteDisconnected")

    with patch.object(api_akshare.time, "sleep", lambda d: None), patch.object(
        api_akshare.random, "uniform", _no_jitter
    ):
        with pytest.raises(ConnectionError):
            api_akshare._with_retry(always_fail, retries=2, delay=1.0)

    assert calls["n"] == 3  # 1 initial + 2 retries


def test_with_retry_default_preserves_original_single_retry():
    """Default args still retry exactly once at the fixed 2.0s (no backoff)."""
    calls = {"n": 0}

    def transient_then_empty():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("timeout")
        return pd.DataFrame()  # second call returns empty

    sleeps: list[float] = []
    with patch.object(api_akshare.time, "sleep", lambda d: sleeps.append(d)), patch.object(
        api_akshare.random, "uniform", _no_jitter
    ):
        api_akshare._with_retry(transient_then_empty)  # all defaults

    assert calls["n"] == 2
    assert sleeps == [2.0]  # exactly one retry at the fixed delay — unchanged


def test_with_retry_non_transient_propagates_immediately():
    """Non-transient exceptions are not retried."""
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("not transient")

    with patch.object(api_akshare.time, "sleep", lambda d: None):
        with pytest.raises(ValueError):
            api_akshare._with_retry(boom, retries=5)

    assert calls["n"] == 1  # never retried
