import sys

from hedge_fund import run
from hedge_fund.tui.app import HedgeFundApp


def test_cli_model_overrides_env_default(monkeypatch):
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("HEDGE_FUND_LLM_PROVIDER", "OpenRouter")
    monkeypatch.setattr(sys, "argv", ["aihf", "--model", "gpt-5.5"])
    monkeypatch.setattr(HedgeFundApp, "run", lambda self: None)

    run.main()

    assert run.os.environ["HEDGE_FUND_LLM_MODEL"] == "gpt-5.5"
    assert run.os.environ["HEDGE_FUND_LLM_PROVIDER"] == "OpenRouter"
