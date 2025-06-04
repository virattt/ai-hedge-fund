import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest

pytest.importorskip("langchain_core", reason="langchain not installed")
from app.backend.services.graph import run_graph


def test_crypto_smoke():
    run_graph(pair="BTC/USDT", exchange="binance", timeframe="1h")
