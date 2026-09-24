"""CLI configuration preflight must run before any external activity."""

import sys
from unittest.mock import Mock

import pytest
import yaml

from hedge_fund import run
from hedge_fund.fund import FundSpec, custom_strategy


@pytest.mark.parametrize("backtest", [False, True])
@pytest.mark.parametrize("unversioned", [False, True])
def test_cli_rejects_unavailable_fund_before_clients(tmp_path, monkeypatch, capsys, backtest, unversioned):
    spec = FundSpec(schema_version=2, name="mixed", strategies=[custom_strategy(["buffett", "druckenmiller"])],
                    risk={"max_position_pct": .25, "max_gross_exposure": 1})
    data = spec.model_dump()
    if unversioned:
        data.pop("schema_version")
    path = tmp_path / "fund.yaml"
    path.write_text(yaml.safe_dump(data))
    original = path.read_bytes()
    forbidden = Mock(side_effect=AssertionError("external activity"))
    monkeypatch.setattr(run, "apply_credentials", lambda: None)
    monkeypatch.setattr(run, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(run, "Fund", forbidden)
    monkeypatch.setattr(run, "FDClient", forbidden)
    monkeypatch.setattr(run, "SimBroker", forbidden)
    monkeypatch.setattr(sys, "argv", ["aihf", str(path), "--tickers", "AAPL"] + (["--backtest"] if backtest else []))
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == 2
    assert forbidden.call_count == 0
    output = capsys.readouterr()
    assert output.out == ""
    assert ("older format" if unversioned else "Execution unavailable") in output.err
    assert path.read_bytes() == original
