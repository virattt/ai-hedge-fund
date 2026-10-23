"""Tests for the ARF-backed DataClient."""

from __future__ import annotations

import duckdb
import pytest

from hedge_fund.data.arf_data import ARFDataClient


@pytest.fixture
def price_db(tmp_path):
    path = tmp_path / "arf.db"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE daily_prices (
            ticker VARCHAR, date DATE, open DOUBLE, high DOUBLE, low DOUBLE,
            close DOUBLE, volume DOUBLE
        )
    """)
    con.executemany(
        "INSERT INTO daily_prices VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ["NVDA", "2026-06-01", 100.0, 102.0, 99.0, 101.0, 1000],
            ["NVDA", "2026-06-02", 101.0, 104.0, 100.0, 103.0, 1200],
        ],
    )
    con.close()
    return path


def test_reads_bars_from_the_database(price_db):
    client = ARFDataClient(db_path=price_db)
    prices = client.get_prices("nvda", "2026-06-01", "2026-06-02")
    assert [p.close for p in prices] == [101.0, 103.0]
    assert prices[0].time == "2026-06-01T20:00:00Z"


def test_shares_an_existing_connection(price_db):
    # The ARF webapp holds a read-write connection for its lifetime; opening a
    # second read-only connection to the same file raises in DuckDB.
    con = duckdb.connect(str(price_db))
    try:
        client = ARFDataClient(connection=con)
        assert len(client.get_prices("NVDA", "2026-06-01", "2026-06-02")) == 2
    finally:
        con.close()


def test_history_is_loaded_once_per_ticker(price_db, monkeypatch):
    client = ARFDataClient(db_path=price_db)
    calls = []
    original = client._con

    def counted():
        calls.append(1)
        return original()

    monkeypatch.setattr(client, "_con", counted)
    client.get_prices("NVDA", "2026-06-01", "2026-06-01")
    client.get_prices("NVDA", "2026-06-02", "2026-06-02")
    assert len(calls) == 1


def test_minute_interval_is_unsupported(price_db):
    client = ARFDataClient(db_path=price_db)
    assert client.get_prices("NVDA", "2026-06-01", "2026-06-02", interval="minute") == []


def test_missing_database_fails_loudly(tmp_path):
    client = ARFDataClient(db_path=tmp_path / "missing.db")
    with pytest.raises(FileNotFoundError):
        client.get_prices("NVDA", "2026-06-01", "2026-06-02")
