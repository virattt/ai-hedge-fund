"""The shipped strategy library must always load against the registry."""

from pathlib import Path

from v2.fund.spec import load_strategy
from v2.signals import ALPHA_MODEL_REGISTRY


def test_shipped_strategy_library_is_valid():
    """Every YAML in v2/strategies/ must load, and its analysts must exist."""
    library = sorted(Path(__file__).parent.parent.glob("strategies/*.yaml"))
    assert library, "strategy library is empty"
    for path in library:
        strategy = load_strategy(path)
        assert strategy.name == path.stem
        for m in strategy.models:
            assert m.name in ALPHA_MODEL_REGISTRY, (
                f"{path.name} references unknown model {m.name!r}"
            )
