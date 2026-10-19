"""The saved-results index under research/."""

import json

import pytest

from hedge_fund import paths
from hedge_fund.backtesting import research


@pytest.fixture
def research_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RESEARCH_DIR", tmp_path)
    return tmp_path


def test_research_history_is_matched_on_the_fund_field_not_the_filename_prefix(research_dir):
    """`alpha` must not pick up `alpha-2`'s backtests: names can be prefixes."""
    receipt = {"fund": "alpha-2", "start": "2025-01-01", "end": "2025-02-01", "benchmark": "SPY",
               "metrics": {"total_return_pct": .5, "annualized_return_pct": .5, "sharpe_ratio": 2,
                           "max_drawdown_pct": .1, "benchmark_return_pct": .1, "excess_return_pct": .4, "n_cycles": 5}}
    (research_dir / "alpha-2-2025-01-01-2025-02-01-x.json").write_text(json.dumps(receipt))
    assert research.receipts("alpha") == []
    assert len(research.receipts("alpha-2")) == 1
    assert research.last_score("alpha") is None
