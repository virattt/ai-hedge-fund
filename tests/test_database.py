import os
import pytest
from src.data import database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Point the module at a fresh temp DB for each test."""
    os.environ["HEDGE_FUND_DB_PATH"] = str(tmp_path / "test.db")
    database._engine = None
    yield
    database._engine = None
    del os.environ["HEDGE_FUND_DB_PATH"]


def test_write_and_read_trade():
    database.write_trade("run1", "2025-01-01", "AAPL", "buy", 10, 150.0, -1500.0)
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.TradeLog).all()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].action == "buy"
    assert rows[0].quantity == 10
    assert rows[0].cash_impact == -1500.0


def test_write_and_read_decision():
    database.write_decision("run1", "2025-01-01", "AAPL", "warren_buffett_agent", "bullish", 75.0, "Strong moat")
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.DecisionLog).all()
    assert len(rows) == 1
    assert rows[0].signal == "bullish"
    assert rows[0].confidence == 75.0


def test_write_and_read_portfolio_snapshot():
    portfolio = {
        "cash": 90000.0,
        "positions": {"AAPL": {"long": 10, "short": 0}},
    }
    current_prices = {"AAPL": 150.0}
    database.write_portfolio_snapshot("run1", "2025-01-01", portfolio, current_prices)
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.PortfolioSnapshot).all()
    assert len(rows) == 1
    assert rows[0].cash == 90000.0
    assert rows[0].long_value == 1500.0
    assert rows[0].nlv == 91500.0


def test_multiple_runs_are_independent():
    database.write_trade("runA", "2025-01-01", "AAPL", "buy", 5, 150.0, -750.0)
    database.write_trade("runB", "2025-01-01", "MSFT", "sell", 3, 300.0, 900.0)
    engine = database.get_engine()
    with database.Session(engine) as session:
        runA_trades = session.query(database.TradeLog).filter_by(run_id="runA").all()
        runB_trades = session.query(database.TradeLog).filter_by(run_id="runB").all()
    assert len(runA_trades) == 1
    assert len(runB_trades) == 1
    assert runA_trades[0].ticker == "AAPL"
    assert runB_trades[0].ticker == "MSFT"
