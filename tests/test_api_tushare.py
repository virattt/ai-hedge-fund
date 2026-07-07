"""Tests for the Tushare valuation provider.

No real token or network is required: the SDK is mocked via sys.modules and
``_get_pro`` is monkeypatched to return a fake pro client.
"""
from __future__ import annotations

import sys
import types

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
    fake_ts.pro_api = lambda: client
    monkeypatch.setitem(sys.modules, "tushare", fake_ts)
    monkeypatch.setattr(api_tushare._get_pro, "_pro", None, raising=False)

    first = api_tushare._get_pro()
    second = api_tushare._get_pro()
    assert first is client
    assert second is client  # cached → same object, no second pro_api() call
