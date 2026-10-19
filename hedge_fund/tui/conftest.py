"""Every TUI test runs against a scratch home directory and without the network."""

from unittest.mock import Mock

import pytest
import requests

from hedge_fund import paths
from hedge_fund.llm import PROVIDER_ENV_VARS
from hedge_fund.tui import keys


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = tmp_path / "user" / ".env"
    saved.parent.mkdir()
    mandates = tmp_path / "mandates"
    mandates.mkdir()
    monkeypatch.setattr(paths, "MANDATES_DIR", mandates)
    monkeypatch.setattr(paths, "PAPER_DIR", tmp_path / "paper")
    monkeypatch.setattr(paths, "RESEARCH_DIR", tmp_path / "research")
    (tmp_path / "research").mkdir()
    monkeypatch.setattr(keys, "ENV_PATH", saved)
    monkeypatch.setattr(paths, "ENV_PATH", saved)
    monkeypatch.setattr(paths, "ensure_mandates_dir", lambda: mandates)
    for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY", "FINANCIAL_DATASETS_API_KEY", "HEDGE_FUND_LLM_MODEL", "UNRELATED_KEY"):
        # Track even initially absent keys, since dotenv and the UI set them
        # directly rather than through monkeypatch.
        monkeypatch.setenv(variable, "")
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(requests.sessions.Session, "request", Mock(side_effect=AssertionError("No live HTTP in TUI tests")))
    return saved
