"""Tests for autoresearch.performance_tracker."""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from autoresearch.performance_tracker import (
    compute_portfolio_value,
    load_prices_for_tickers,
)


def test_load_prices_for_tickers_empty():
    prices = load_prices_for_tickers(["UNKNOWN_TICKER"])
    assert prices == {}


def test_compute_portfolio_value_missing_file():
    cash, pos = compute_portfolio_value("/nonexistent/path.json")
    assert cash == 0.0
    assert pos == 0.0


def test_compute_portfolio_value_empty_state(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cash": 0, "positions": {}}))
    cash, pos = compute_portfolio_value(str(state))
    assert cash == 0
    assert pos == 0.0


def test_compute_portfolio_value_with_cash(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cash": 50_000, "positions": {}}))
    cash, pos = compute_portfolio_value(str(state))
    assert cash == 50_000
    assert pos == 0.0
