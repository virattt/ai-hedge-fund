"""The shipped strategy library must always load against the registry."""

from pathlib import Path

from hedge_fund.fund.spec import Fund, FundSpec, load_strategy
from hedge_fund.signals import ALPHA_MODEL_REGISTRY


def test_shipped_strategy_library_is_valid():
    """Every YAML in hedge_fund/strategies/ must load, and its analysts must exist."""
    library = sorted(Path(__file__).parent.parent.glob("strategies/*.yaml"))
    assert library, "strategy library is empty"
    for path in library:
        strategy = load_strategy(path)
        assert strategy.name == path.stem
        for m in strategy.models:
            assert m.name in ALPHA_MODEL_REGISTRY, (
                f"{path.name} references unknown model {m.name!r}"
            )


def test_quant_sleeves_staff_from_library():
    """Shipped momentum / mean-reversion YAMLs construct their models."""
    library = Path(__file__).parent.parent / "strategies"
    for stem in ("momentum", "mean-reversion"):
        strategy = load_strategy(library / f"{stem}.yaml")
        spec = FundSpec(
            name="sleeve-check",
            strategies=[strategy],
            risk={"max_position_pct": 0.25, "max_gross_exposure": 1.0},
        )
        fund = Fund(spec)
        staff = fund.strategies[0][1]
        assert len(staff) == 1
        assert staff[0].name in {"momentum", "mean_reversion"}
