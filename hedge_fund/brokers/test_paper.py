"""PaperBroker — SimBroker fills that survive the process."""

import json

import pytest

from hedge_fund.brokers.models import Order
from hedge_fund.brokers.paper import PaperBroker


def test_book_round_trips_through_the_file(tmp_path):
    path = tmp_path / "broker.json"
    broker = PaperBroker.create(path, cash=10_000)
    assert json.loads(path.read_text()) == {"cash": 10_000, "shares": {}}

    broker.place_order(Order(ticker="B", side="sell", quantity=5, price=100))
    broker.place_order(Order(ticker="A", side="buy", quantity=10, price=100))
    assert json.loads(path.read_text()) == {"cash": 9_500, "shares": {"A": 10, "B": -5}}

    reopened = PaperBroker(path)
    assert reopened.cash() == 9_500
    assert {t: p.shares for t, p in reopened.positions().items()} == {"A": 10, "B": -5}

    reopened.place_order(Order(ticker="A", side="sell", quantity=10, price=110))
    assert json.loads(path.read_text()) == {"cash": 10_600, "shares": {"B": -5}}
    assert "A" not in PaperBroker(path).positions()


def test_create_refuses_to_overwrite_and_open_requires_a_book(tmp_path):
    path = tmp_path / "broker.json"
    PaperBroker.create(path, cash=1)
    with pytest.raises(FileExistsError):
        PaperBroker.create(path, cash=1)
    with pytest.raises(ValueError, match="cannot read"):
        PaperBroker(tmp_path / "missing.json")


def test_rejected_order_leaves_the_file_untouched(tmp_path):
    path = tmp_path / "broker.json"
    broker = PaperBroker.create(path, cash=1_000)
    before = path.read_text()
    with pytest.raises(ValueError):
        broker.place_order(Order(ticker="A", side="buy", quantity=1, price=float("nan")))
    assert path.read_text() == before
