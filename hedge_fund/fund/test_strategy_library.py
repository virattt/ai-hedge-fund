"""The shipped strategy library must always load against the registry."""

from pathlib import Path

from hedge_fund.fund.spec import load_strategy
from hedge_fund.signals import ALPHA_MODEL_REGISTRY


def test_shipped_strategy_library_is_valid():
    """Every YAML in hedge_fund/strategies/ must load, and its analysts must exist."""
    library = sorted(Path(__file__).parent.parent.glob("strategies/*.yaml"))
    assert library, "strategy library is empty"
    modes = {"deep-value": "long_only", "fundamental-ls": "dollar_neutral",
             "inflections": "long_short", "earnings-drift": "long_short"}
    for path in library:
        strategy = load_strategy(path)
        assert strategy.name == path.stem
        assert strategy.blend.mode == modes[strategy.name]
        for m in strategy.models:
            assert m.name in ALPHA_MODEL_REGISTRY, (
                f"{path.name} references unknown model {m.name!r}"
            )


def test_packaged_example_uses_current_format():
    from hedge_fund.fund.spec import load_spec
    spec = load_spec(Path(__file__).parent / "example.yaml")
    assert spec.schema_version == 2
    assert [s.blend.mode for s in spec.strategies] == ["long_only", "long_short"]


def test_all_shipped_strategies_execute_with_fixed_signals():
    from hedge_fund.brokers import SimBroker
    from hedge_fund.fund import Fund, FundSpec
    from hedge_fund.pipeline import run_cycle
    from hedge_fund.pipeline.test_run_cycle import FakeAnalyst, FakeDataClient
    library = sorted(Path(__file__).parent.parent.glob("strategies/*.yaml"))
    for path in library:
        strategy = load_strategy(path)
        spec = FundSpec(schema_version=2, name=path.stem, strategies=[strategy],
                        risk={"max_position_pct": .25, "max_gross_exposure": 1})
        fund = Fund(spec, models={strategy.name: [FakeAnalyst(m.name, {"A": 1, "B": -1}) for m in strategy.models]})
        record = run_cycle(fund, "2025-01-01", SimBroker(100_000), FakeDataClient({"A": 100, "B": 100}), ["A", "B"])
        assert record.positions["A"] > 0
        assert (record.positions.get("B", 0) < 0) == (strategy.blend.mode != "long_only")
