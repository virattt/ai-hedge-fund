"""FundSpec + Fund tests — YAML loading, validation, analyst instantiation."""

import pytest
from pydantic import ValidationError

from v2.fund.spec import Fund, FundSpec, load_spec

MINIMAL = {
    "name": "test-fund",
    "universe": ["AAPL", "MSFT"],
    "analysts": [{"name": "pead"}],
    "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0},
}


def test_yaml_load_happy_path(tmp_path):
    path = tmp_path / "fund.yaml"
    path.write_text(
        "name: yaml-fund\n"
        "universe: [AAPL, msft]\n"
        "analysts:\n"
        "  - name: pead\n"
        "    weight: 2.0\n"
        "risk:\n"
        "  max_position_pct: 0.2\n"
        "  max_gross_exposure: 1.5\n"
        "capital: 50000\n"
    )
    spec = load_spec(path)
    assert spec.name == "yaml-fund"
    assert spec.universe == ["AAPL", "MSFT"]  # uppercased
    assert spec.analysts[0].weight == 2.0
    assert spec.capital == 50000


def test_defaults_applied():
    spec = FundSpec(**MINIMAL)
    assert spec.blend.method == "conviction_weighted"
    assert spec.blend.gross_target == 1.0
    assert spec.analysts[0].weight == 1.0
    assert spec.capital == 100_000.0


def test_typo_key_rejected():
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "universee": ["AAPL"]})


def test_empty_universe_rejected():
    with pytest.raises(ValidationError):
        FundSpec(**{**MINIMAL, "universe": []})


def test_duplicate_ticker_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        FundSpec(**{**MINIMAL, "universe": ["AAPL", "aapl"]})


def test_unknown_analyst_names_valid_keys():
    spec = FundSpec(**{**MINIMAL, "analysts": [{"name": "lynch"}]})
    with pytest.raises(ValueError, match="pead"):
        Fund(spec)


def test_fund_instantiates_analysts_once():
    fund = Fund(FundSpec(**MINIMAL))
    first = fund.analysts[0]
    # The same objects persist for the fund's lifetime — caches survive cycles.
    assert fund.analysts[0] is first
    assert fund.analyst_weights == {"pead": 1.0}
