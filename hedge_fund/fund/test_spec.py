"""FundSpec + StrategySpec + Fund tests — YAML loading, validation, staffing."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
import yaml
from pydantic import ValidationError

from hedge_fund.fund import (
    custom_strategy,
    discover_funds,
    execution_unavailable,
    Fund,
    FundSpec,
    load_spec,
    load_strategy,
    normalize_universe,
    StrategySpec,
)
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, get_investment_approach

MINIMAL = {
    "schema_version": 2,
    "name": "test-fund",
    "strategies": [{"name": "event", "models": [{"name": "pead"}], "blend": {"mode": "long_short"}}],
    "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0},
}


def test_yaml_load_happy_path(tmp_path):
    path = tmp_path / "fund.yaml"
    path.write_text("schema_version: 2\n" "name: yaml-fund\n" "strategies:\n" "  - name: event\n" "    weight: 2.0\n" "    blend: {mode: long_short}\n" "    models:\n" "      - name: pead\n" "        weight: 3.0\n" "risk:\n" "  max_position_pct: 0.2\n" "  max_gross_exposure: 1.5\n" "capital: 50000\n")
    spec = load_spec(path)
    assert spec.name == "yaml-fund"
    assert spec.strategies[0].weight == 2.0
    assert spec.strategies[0].models[0].weight == 3.0
    assert spec.capital == 50000


def test_load_strategy(tmp_path):
    path = tmp_path / "value.yaml"
    path.write_text("name: value\n" "blend: {mode: long_short}\n" "models:\n" "  - name: buffett\n" "  - name: pead\n")
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


def test_unversioned_files_are_rejected_without_changes(tmp_path):
    path = tmp_path / "old.yaml"
    path.write_text("name: old-fund\n" "universe: [AAPL, MSFT]\n" "strategies:\n" "  - name: event\n" "    models:\n" "      - name: pead\n" "risk:\n" "  max_position_pct: 0.25\n" "  max_gross_exposure: 1.0\n")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="older format") as exc:
        load_spec(path)
    assert str(path) in str(exc.value)
    assert path.read_bytes() == original


def test_normalize_universe():
    assert normalize_universe(["aapl", " msft ", "AAPL"]) == ["AAPL", "MSFT"]
    with pytest.raises(ValueError, match="universe is empty"):
        normalize_universe([])
    with pytest.raises(ValueError, match="universe is empty"):
        normalize_universe(["  "])


def test_duplicate_strategy_name_rejected():
    strategies = [
        {"name": "event", "models": [{"name": "pead"}], "blend": {"mode": "long_short"}},
        {"name": "event", "models": [{"name": "buffett"}], "blend": {"mode": "long_only"}},
    ]
    with pytest.raises(ValidationError, match="duplicate strategy"):
        FundSpec(**{**MINIMAL, "strategies": strategies})


def test_strategy_needs_models():
    with pytest.raises(ValidationError, match="models"):
        StrategySpec(name="empty", models=[], blend={"mode": "long_short"})


def test_unknown_analyst_names_valid_keys():
    strategies = [{"name": "s", "models": [{"name": "lynch-typo"}], "blend": {"mode": "long_short"}}]
    with pytest.raises(ValueError, match="pead"):
        FundSpec(**{**MINIMAL, "strategies": strategies})


def test_fund_staffs_each_strategy_once():
    fund = Fund(FundSpec(**MINIMAL))
    strategy, staff = fund.strategies[0]
    assert strategy.name == "event"
    assert len(staff) == 1
    # The same objects persist for the fund's lifetime — caches survive cycles.
    assert fund.strategies[0][1][0] is staff[0]


@pytest.mark.parametrize(
    "names,mode",
    [
        (["buffett"], "long_only"),
        (["buffett", "munger"], "long_only"),
        (["druckenmiller"], "long_short"),
        (["buffett", "druckenmiller"], "long_short"),
    ],
)
def test_custom_rules_derive_without_constructing_analysts(names, mode, monkeypatch, tmp_path):
    for name in names:
        monkeypatch.setattr(ALPHA_MODEL_REGISTRY[name], "__init__", Mock(side_effect=AssertionError("constructed")))
    strategy = custom_strategy(names)
    assert strategy.blend.mode == mode
    spec = FundSpec(**{**MINIMAL, "strategies": [strategy]})
    path = tmp_path / "new.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump()))
    assert load_spec(path) == spec
    assert FundSpec.model_validate_json(spec.model_dump_json()) == spec


@pytest.mark.parametrize("name", sorted(ALPHA_MODEL_REGISTRY))
def test_all_profiles_are_explicit(name):
    assert get_investment_approach(name) in ("long_only", "long_short")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("buffett", "long_only"),
        ("munger", "long_only"),
        ("graham", "long_only"),
        ("lynch", "long_only"),
        ("druckenmiller", "long_short"),
        ("pead", "long_short"),
    ],
)
def test_initial_analyst_approaches(name, expected):
    assert get_investment_approach(name) == expected


@pytest.mark.parametrize("profile", [None, "dollar_neutral"])
def test_missing_or_invalid_profile_is_configuration_error(monkeypatch, profile):
    class InvalidAnalyst:
        def __init__(self):
            raise AssertionError("must not instantiate")

    if profile is not None:
        InvalidAnalyst.investment_approach = profile
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "invalid", InvalidAnalyst)
    with pytest.raises(ValueError, match="investment_approach"):
        custom_strategy(["invalid"])


@pytest.mark.parametrize(
    "mutation,field",
    [
        (lambda d: d.pop("schema_version"), "schema_version"),
        (lambda d: d.update(schema_version=3), "schema_version"),
        (lambda d: d.update(universe=["AAPL"]), "universe"),
        (lambda d: d["strategies"][0]["blend"].pop("mode"), "mode"),
        (lambda d: d["strategies"][0]["blend"].update(mode="magic"), "mode"),
        (lambda d: d["strategies"][0]["blend"].update(market_neutral=True), "market_neutral"),
    ],
)
def test_bad_configuration_names_file_and_field(tmp_path, mutation, field):
    data = deepcopy(MINIMAL)
    mutation(data)
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError) as exc:
        load_spec(path)
    assert str(path) in str(exc.value)
    assert field in str(exc.value)


def test_discovery_is_read_only_and_isolates_invalid_files(tmp_path):
    contents = {
        "valid.yaml": yaml.safe_dump(MINIMAL),
        "old.yaml": "name: old\n",
        "broken.yaml": "[not: valid",
        "empty.yaml": "",
    }
    for name, content in contents.items():
        (tmp_path / name).write_text(content)
    entries = {e.path.name: e for e in discover_funds(tmp_path)}
    assert entries["valid.yaml"].spec.name == "test-fund"
    assert all(entries[name].error for name in contents if name != "valid.yaml")
    assert {p.name: p.read_text() for p in tmp_path.iterdir()} == contents


@pytest.mark.parametrize(
    "names,mode",
    [
        (["buffett"], "long_only"),
        (["buffett", "druckenmiller"], "long_short"),
        (["druckenmiller"], "dollar_neutral"),
        (["druckenmiller"], "long_only"),
        (["buffett"], "long_short"),
    ],
)
def test_whole_fund_blocked_before_any_analyst_is_constructed(monkeypatch, names, mode):
    strategy = custom_strategy(names)
    strategy.blend.mode = mode
    spec = FundSpec(**{**MINIMAL, "strategies": [MINIMAL["strategies"][0], strategy]})
    for cls in ALPHA_MODEL_REGISTRY.values():
        monkeypatch.setattr(cls, "__init__", Mock(side_effect=AssertionError("constructed")))
    assert "Custom" in execution_unavailable(spec)
    with pytest.raises(ValueError, match="Execution unavailable"):
        Fund(spec)
