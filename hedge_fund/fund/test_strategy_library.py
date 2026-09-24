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
