from pathlib import Path

from integrations.alpaca.config import load_alpaca_config
from integrations.alpaca.ledger import save_cycle
from integrations.alpaca.run_cycle import CycleResult
from integrations.broker.models import TradeOrder


def test_load_alpaca_config_execute_override(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")

    config = load_alpaca_config(execute=True)
    assert config.execution_enabled is True


def test_save_cycle_ledger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CycleResult(
        broker_name="noop",
        portfolio={"cash": 100_000},
        agent_result={"decisions": {"AAPL": {"action": "hold", "quantity": 0}}},
        orders=[TradeOrder(ticker="AAPL", action="hold", quantity=0)],
        execution_results=[],
        account_summary="Cash: $100,000",
    )
    path = save_cycle(result, broker_name="noop")
    assert path.exists()
    assert path.parent == Path("data/ledger")
