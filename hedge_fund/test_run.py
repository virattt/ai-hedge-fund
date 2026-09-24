"""CLI configuration preflight must run before any external activity."""

import sys
from unittest.mock import Mock

import pytest
import yaml

from hedge_fund import run
from hedge_fund.fund import custom_strategy, FundSpec


@pytest.mark.parametrize("backtest", [False, True])
@pytest.mark.parametrize("unversioned", [False, True])
def test_cli_rejects_invalid_configuration_before_clients(tmp_path, monkeypatch, capsys, backtest, unversioned):
    spec = FundSpec(schema_version=2, name="mixed", strategies=[custom_strategy(["buffett", "druckenmiller"])],
                    risk={"max_position_pct": .25, "max_gross_exposure": 1})
    data = spec.model_dump()
    if unversioned:
        data.pop("schema_version")
    else:
        data["strategies"][0]["blend"]["mode"] = "invalid"
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
    assert ("older format" if unversioned else "blend.mode") in output.err
    assert path.read_bytes() == original


@pytest.mark.parametrize("backtest", [False, True])
@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
def test_cli_executes_all_modes_with_offline_clients(tmp_path, monkeypatch, capsys, mode, backtest):
    import json

    from hedge_fund.backtesting.test_fund import FakeAnalyst, FakeDataClient
    from hedge_fund.fund import Fund
    spec = FundSpec(schema_version=2, name="mixed", strategies=[custom_strategy(["buffett", "druckenmiller"])],
                    risk={"max_position_pct": .25, "max_gross_exposure": 1})
    spec.strategies[0].blend.mode = mode
    path = tmp_path / "fund.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump()))
    class OfflineClient(FakeDataClient):
        def __init__(self):
            super().__init__({ticker: {"2025-01-03": 100, "2025-01-10": 100} for ticker in ("AAPL", "MSFT", "SPY")})
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    def build_fund(spec):
        return Fund(spec, models={"custom": [FakeAnalyst(name, {"AAPL": .8, "MSFT": -.6}) for name in ("buffett", "druckenmiller")]})
    monkeypatch.setattr(run, "apply_credentials", lambda: None)
    monkeypatch.setattr(run, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(run, "Fund", build_fund)
    monkeypatch.setattr(run, "FDClient", OfflineClient)
    monkeypatch.setattr(run, "CachedDataClient", lambda client: client)
    monkeypatch.setattr(sys, "argv", ["aihf", str(path), "--tickers", "AAPL,MSFT", "--date", "2025-01-10"] +
                        (["--backtest", "--start", "2025-01-03"] if backtest else []))
    run.main()
    result = json.loads(capsys.readouterr().out)
    records = result["records"] if backtest else [result]
    for record in records:
        assert record["positions"]["AAPL"] > 0
        assert (record["positions"].get("MSFT", 0) < 0) == (mode != "long_only")
        if mode == "dollar_neutral":
            assert sum(record["final_weights"].values()) == pytest.approx(0)
