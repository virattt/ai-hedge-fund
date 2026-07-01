"""Smoke tests for the A-share data layer (akshare-backed).

These tests hit the live akshare API for Kweichow Moutai (600519.SH).
They require network access but no API key. Skipped if akshare import fails.
"""
from __future__ import annotations

import pytest

try:
    import akshare as _ak  # noqa: F401
    _AKSHARE_OK = True
except Exception:
    _AKSHARE_OK = False

_AKSHARE_SKIP = not _AKSHARE_OK

from src.data.models import FinancialMetrics, Price
from src.tools.api import get_financial_metrics, get_prices


def _enable() -> bool:
    import os
    return os.environ.get("ASHARE_SMOKE") == "1"


@pytest.mark.skipif(not _enable() or _AKSHARE_SKIP, reason="ASHARE_SMOKE not set or akshare unavailable")
def test_get_prices_ashare():
    prices = get_prices("600519.SH", "2025-09-01", "2025-09-10")
    assert prices, "expected non-empty price list"
    assert all(isinstance(p, Price) for p in prices)
    assert all(p.volume > 0 for p in prices), "volume should be positive"
    # time field is ISO date string
    assert prices[0].time.startswith("2025-09")


@pytest.mark.skipif(not _enable() or _AKSHARE_SKIP, reason="ASHARE_SMOKE not set or akshare unavailable")
def test_get_financial_metrics_ashare():
    metrics = get_financial_metrics("600519.SH", "2025-12-31", limit=3)
    assert metrics, "expected non-empty metrics list"
    assert all(isinstance(m, FinancialMetrics) for m in metrics)
    assert all(m.currency == "CNY" for m in metrics)
    assert all(m.ticker == "600519.SH" for m in metrics)
