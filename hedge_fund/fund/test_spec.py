"""FundSpec + StrategySpec + Fund tests — YAML loading, validation, staffing."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
import yaml
from pydantic import ValidationError

from hedge_fund.fund import (
    custom_strategy,
    discover_funds,
    format_interval,
    Fund,
    FundSpec,
    load_spec,
    load_strategy,
    normalize_universe,
    save_spec,
    StrategySpec,
)
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, get_horizon_days, get_investment_approach

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


def test_minute_fund_has_an_interval_and_a_window():
    spec = FundSpec(**{**MINIMAL, "rebalance": "minute"})
    assert spec.is_intraday and spec.interval == 1.0 and spec.interval_seconds == 60
    assert spec.window.start == "09:30" and spec.window.end == "16:00"
    assert spec.cadence_label == "every 1m" and spec.window.label == "09:30–16:00 ET"
    half = FundSpec(**{**MINIMAL, "rebalance": "minute", "interval": 0.5, "window": {"start": "07:00", "end": "17:30"}})
    assert half.interval_seconds == 30 and half.cadence_label == "every 30s"
    assert half.window.start_seconds == 7 * 3600 and half.window.end_seconds == 17 * 3600 + 30 * 60
    assert FundSpec(**{**MINIMAL, "rebalance": "minute", "interval": 90}).cadence_label == "every 1h30m"
    assert format_interval(150) == "2m30s" and format_interval(3600) == "1h"
    # The round trip keeps both fields; a daily fund never writes them.
    assert FundSpec.model_validate(half.model_dump()) == half
    assert "interval" in half.model_dump_json() and "window" in half.model_dump_json()
    assert "interval" not in FundSpec(**MINIMAL).model_dump_json()
    assert "window" not in FundSpec(**MINIMAL).model_dump()
    assert not FundSpec(**MINIMAL).is_intraday and FundSpec(**MINIMAL).cadence_label == "weekly"


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"interval": 0.005}, "floor is 1 second"),  # 0.3s rounds to no bar at all
        ({"interval": 0}, "greater than 0"),
        ({"interval": 60 * 7}, "longer than the 09:30–16:00 ET window"),
        ({"window": {"start": "16:00", "end": "09:30"}}, "open before it closes"),
        ({"window": {"start": "03:59"}}, "outside US extended hours"),
        ({"window": {"end": "20:01"}}, "outside US extended hours"),
        ({"window": {"start": "9:30"}}, "not a time of day"),
        ({"window": {"start": "09:30", "lunch": "12:00"}}, "lunch"),
    ],
)
def test_minute_fund_rejects_bad_intervals_and_windows(overrides, message):
    with pytest.raises(ValidationError, match=message):
        FundSpec(**{**MINIMAL, "rebalance": "minute", **overrides})


def test_interval_and_window_are_refused_on_slower_cadences():
    with pytest.raises(ValidationError, match="interval, window: only a minute fund"):
        FundSpec(**{**MINIMAL, "rebalance": "daily", "interval": 5, "window": {"start": "10:00"}})
    with pytest.raises(ValidationError, match="interval: only a minute fund"):
        FundSpec(**{**MINIMAL, "interval": 5})


def test_benchmark_uppercased():
    assert FundSpec(**{**MINIMAL, "benchmark": "qqq"}).benchmark == "QQQ"


def test_costs_default_to_a_real_cost_model_and_serialize_only_when_changed():
    spec = FundSpec(**MINIMAL)
    assert spec.costs.spread_bps == 5.0 and spec.costs.commission_per_share == 0.005
    # A mandate at the default serializes exactly as it did before costs
    # existed, so every recorded hash still verifies.
    assert "costs" not in spec.model_dump()
    explicit = FundSpec(**{**MINIMAL, "costs": {"spread_bps": 5, "commission_per_share": 0.005}})
    assert explicit.model_dump_json() == spec.model_dump_json()
    free = FundSpec(**{**MINIMAL, "costs": {"spread_bps": 0, "commission_per_share": 0}})
    assert free.model_dump()["costs"] == {"spread_bps": 0.0, "commission_per_share": 0.0}
    assert FundSpec.model_validate(free.model_dump()) == free
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "costs": {"spread_bps": -1}})


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


@pytest.mark.parametrize("name", sorted(ALPHA_MODEL_REGISTRY))
def test_all_horizons_are_explicit(name):
    assert get_horizon_days(name) > 0


def test_initial_analyst_horizons():
    assert {name: get_horizon_days(name) for name in ALPHA_MODEL_REGISTRY} == {
        "buffett": 252, "munger": 252, "graham": 252, "lynch": 252, "druckenmiller": 126, "pead": 60,
    }


@pytest.mark.parametrize("horizon", [None, 0, 1.5, "1y"])
def test_missing_or_invalid_horizon_is_configuration_error(monkeypatch, horizon):
    class NoHorizon:
        investment_approach = "long_only"

        def __init__(self):
            raise AssertionError("must not instantiate")

    if horizon is not None:
        NoHorizon.horizon_days = horizon
    monkeypatch.setitem(ALPHA_MODEL_REGISTRY, "nohorizon", NoHorizon)
    with pytest.raises(ValueError, match="horizon_days"):
        get_horizon_days("nohorizon")
    with pytest.raises(ValueError, match="horizon_days"):
        custom_strategy(["nohorizon"])


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
def test_all_modes_construct_without_execution_gates(monkeypatch, names, mode):
    strategy = custom_strategy(names)
    strategy.blend.mode = mode
    spec = FundSpec(**{**MINIMAL, "strategies": [MINIMAL["strategies"][0], strategy]})
    for cls in ALPHA_MODEL_REGISTRY.values():
        monkeypatch.setattr(cls, "__init__", lambda self, **kwargs: None)
    fund = Fund(spec)
    assert [s.name for s, _ in fund.strategies] == ["event", "custom"]
    assert len(fund.strategies[1][1]) == len(names)


@pytest.mark.parametrize("blind", [False, True])
def test_blind_reaches_llm_agents_only(monkeypatch, blind):
    """Fund(blind=True) is the backtest's seam: every LLM persona renders
    blind prompts, quant models are constructed exactly as before."""
    seen = {}
    for name, cls in ALPHA_MODEL_REGISTRY.items():
        monkeypatch.setattr(cls, "__init__", lambda self, _name=name, **kwargs: seen.__setitem__(_name, kwargs))
    strategy = custom_strategy(["buffett", "druckenmiller"])
    spec = FundSpec(**{**MINIMAL, "strategies": [MINIMAL["strategies"][0], strategy]})

    Fund(spec, blind=blind)

    assert seen["pead"] == {}
    expected = {"blind": True} if blind else {}
    assert seen["buffett"] == expected
    assert seen["druckenmiller"] == expected


def test_save_spec_round_trips_and_never_overwrites(tmp_path):
    spec = FundSpec(**MINIMAL)
    path = save_spec(spec, tmp_path / "mandates")
    assert path == tmp_path / "mandates" / "test-fund.yaml"
    assert load_spec(path) == spec
    with pytest.raises(FileExistsError):
        save_spec(spec, tmp_path / "mandates")
    assert load_spec(path) == spec
