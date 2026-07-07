"""Tests for the Tushare valuation provider.

No real token or network is required: the SDK is mocked via sys.modules and
``_get_pro`` is monkeypatched to return a fake pro client.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pandas as pd
import pytest

from src.tools import api_tushare


@pytest.fixture
def fresh(monkeypatch):
    """Token enabled, breaker reset, table memo cleared."""
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    monkeypatch.setattr(api_tushare, "_disabled", False)
    monkeypatch.setattr(api_tushare, "_daily_basic_tables", {})
    # Reset any cached pro client from a prior test.
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)
    return monkeypatch


def test_get_pro_returns_none_when_no_token(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    assert api_tushare._get_pro() is None


def test_get_pro_returns_cached_client_when_token_set(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    fake_ts = types.ModuleType("tushare")
    fake_ts.set_token = lambda token: None
    client = object()
    pro_api = Mock(return_value=client)
    fake_ts.pro_api = pro_api
    monkeypatch.setitem(sys.modules, "tushare", fake_ts)
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)

    first = api_tushare._get_pro()
    second = api_tushare._get_pro()
    assert first is client
    assert second is client
    assert pro_api.call_count == 1  # cached → pro_api constructed only once


def test_to_float_rejects_nan_inf_and_garbage():
    """Tushare daily_basic yields pe=price/eps, which is inf for loss-makers;
    those must not leak into the valuation block."""
    assert api_tushare._to_float(None) is None
    assert api_tushare._to_float(float("nan")) is None
    assert api_tushare._to_float(float("inf")) is None
    assert api_tushare._to_float(float("-inf")) is None
    assert api_tushare._to_float("not-a-number") is None
    assert api_tushare._to_float("3.14") == 3.14
    assert api_tushare._to_float(0.0) == 0.0
