"""FundSpec + StrategySpec + Fund tests — YAML loading, validation, staffing."""

import pytest
from pydantic import ValidationError

from hedge_fund.fund.spec import (
    Fund,
    FundSpec,
    StrategySpec,
    load_spec,
    load_strategy,
    normalize_universe,
)

MINIMAL = {
    "name": "test-fund",
    "strategies": [{"name": "event", "models": [{"name": "pead"}]}],
    "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0},
}


def test_yaml_load_happy_path(tmp_path):
    path = tmp_path / "fund.yaml"
    path.write_text(
        "name: yaml-fund\n"
        "strategies:\n"
        "  - name: event\n"
        "    weight: 2.0\n"
        "    models:\n"
        "      - name: pead\n"
        "        weight: 3.0\n"
        "risk:\n"
        "  max_position_pct: 0.2\n"
        "  max_gross_exposure: 1.5\n"
        "capital: 50000\n"
    )
    spec = load_spec(path)
    assert spec.name == "yaml-fund"
    assert spec.strategies[0].weight == 2.0
    assert spec.strategies[0].models[0].weight == 3.0
    assert spec.capital == 50000


def test_load_strategy(tmp_path):
    path = tmp_path / "value.yaml"
    path.write_text(
        "name: value\n"
        "models:\n"
        "  - name: buffett\n"
        "  - name: pead\n"
    )
    strategy = load_strategy(path)
    assert strategy.name == "value"
    assert strategy.weight == 1.0  # slices are a fund-assembly concern
    assert strategy.model_weights == {"buffett": 1.0, "pead": 1.0}


def test_defaults_applied():
    spec = FundSpec(**MINIMAL)
    assert spec.strategies[0].blend.method == "conviction_weighted"
    assert spec.strategies[0].blend.gross_target == 1.0
    assert spec.strategies[0].weight == 1.0
    assert spec.capital == 100_000.0
    assert spec.rebalance == "weekly"
    assert spec.benchmark == "SPY"


def test_rebalance_cadence_validated():
    assert FundSpec(**{**MINIMAL, "rebalance": "daily"}).rebalance == "daily"
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "rebalance": "hourly"})


def test_benchmark_uppercased():
    assert FundSpec(**{**MINIMAL, "benchmark": "qqq"}).benchmark == "QQQ"


def test_typo_key_rejected():
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "capitol": 1000})


def test_mandate_carries_no_tickers():
    """A fund is the desk, not a watchlist — `universe` is not a spec field."""
    assert not hasattr(FundSpec(**MINIMAL), "universe")
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "universe": ["AAPL"]})


def test_legacy_universe_key_is_dropped_on_load(tmp_path):
    """Funds saved before tickers moved to run time must still load."""
    path = tmp_path / "old.yaml"
    path.write_text(
        "name: old-fund\n"
        "universe: [AAPL, MSFT]\n"
        "strategies:\n"
        "  - name: event\n"
        "    models:\n"
        "      - name: pead\n"
        "risk:\n"
        "  max_position_pct: 0.25\n"
        "  max_gross_exposure: 1.0\n"
    )
    spec = load_spec(path)
    assert spec.name == "old-fund"
    assert not hasattr(spec, "universe")


def test_normalize_universe():
    assert normalize_universe(["aapl", " msft ", "AAPL"]) == ["AAPL", "MSFT"]
    with pytest.raises(ValueError, match="universe is empty"):
        normalize_universe([])
    with pytest.raises(ValueError, match="universe is empty"):
        normalize_universe(["  "])


def test_duplicate_strategy_name_rejected():
    strategies = [
        {"name": "event", "models": [{"name": "pead"}]},
        {"name": "event", "models": [{"name": "buffett"}]},
    ]
    with pytest.raises(ValidationError, match="duplicate strategy"):
        FundSpec(**{**MINIMAL, "strategies": strategies})


def test_strategy_needs_models():
    with pytest.raises(ValidationError):
        StrategySpec(name="empty", models=[])


def test_unknown_analyst_names_valid_keys():
    strategies = [{"name": "s", "models": [{"name": "lynch-typo"}]}]
    spec = FundSpec(**{**MINIMAL, "strategies": strategies})
    with pytest.raises(ValueError, match="pead"):
        Fund(spec)


def test_fund_staffs_each_strategy_once():
    fund = Fund(FundSpec(**MINIMAL))
    strategy, staff = fund.strategies[0]
    assert strategy.name == "event"
    assert len(staff) == 1
    # The same objects persist for the fund's lifetime — caches survive cycles.
    assert fund.strategies[0][1][0] is staff[0]
