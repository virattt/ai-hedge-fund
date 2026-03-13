"""Integration-adjacent tests for WM backtest wiring."""

from types import SimpleNamespace

from autoresearch.cache_worldmonitor import format_worldmonitor_status_line
from autoresearch import paper_trading
from autoresearch.portfolio_backtest import run_sector_backtest


def test_run_sector_backtest_sets_wm_override(monkeypatch):
    captured = {}

    def _fake_load_params(_module_name: str):
        return SimpleNamespace(
            BACKTEST_START="2025-01-01",
            BACKTEST_END="2025-12-31",
            BACKTEST_INITIAL_CASH=100_000.0,
            BACKTEST_MARGIN_REQ=0.5,
        )

    class _FakeEngine:
        def __init__(self, params, prices_path_override=None):
            captured["params"] = params
            self.portfolio_values = [{"date": "2025-01-01", "value": 100000.0}]

        def run(self):
            return {"sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0, "total_return_pct": 0.0}

    monkeypatch.setattr("autoresearch.portfolio_backtest.load_params", _fake_load_params)
    monkeypatch.setattr("autoresearch.fast_backtest.FastBacktestEngine", _FakeEngine)

    _pv, _metrics, _engine = run_sector_backtest(
        "autoresearch.params_tech",
        "prices.json",
        wm_enabled=True,
    )
    assert getattr(captured["params"], "USE_WM_FILTER", None) is True


def test_paper_trading_passes_wm_flag_to_sector_backtest(monkeypatch):
    class _FakeEngine:
        final_positions = {}
        last_prices = {}

    captured = {"wm_enabled": []}

    def _fake_run_sector_backtest(*args, **kwargs):
        captured["wm_enabled"].append(kwargs.get("wm_enabled"))
        return ([{"date": "2026-03-01", "value": 100000.0}], {"sharpe_ratio": 0.0, "total_return_pct": 0.0}, _FakeEngine())

    monkeypatch.setattr(paper_trading, "SECTOR_CONFIG", {"tech": ("autoresearch.params_tech", "prices.json")})
    monkeypatch.setattr(paper_trading, "run_sector_backtest", _fake_run_sector_backtest)

    # Avoid pulling any live regime state in this unit test path.
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper_trading.py",
            "--date",
            "2026-03-07",
            "--no-regime",
            "--wm-filter",
        ],
    )
    rc = paper_trading.main()
    assert rc == 0
    assert captured["wm_enabled"] == [True]


def test_format_worldmonitor_status_line_disabled():
    line = paper_trading._format_worldmonitor_status_line(enabled=False)
    assert line == "  World Monitor: DISABLED"


def test_format_worldmonitor_status_line_missing_snapshot(monkeypatch):
    monkeypatch.setattr(
        "autoresearch.cache_worldmonitor.load_worldmonitor_snapshot",
        lambda: None,
    )
    line = paper_trading._format_worldmonitor_status_line(enabled=True)
    assert "snapshot missing" in line


def test_cache_status_formatter_disabled_prefix():
    line = format_worldmonitor_status_line(enabled=False, prefix="WM")
    assert line == "WM DISABLED"

