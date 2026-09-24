"""backtest_fund tests — fake data client + fake analysts, real broker + pipeline."""

import pytest

from hedge_fund.backtesting.fund import backtest_fund, rebalance_grid
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.models import Signal

# ---------------------------------------------------------------------------
# Fakes (date-aware variants of the run_cycle test fakes)
# ---------------------------------------------------------------------------

class FakeDataClient:
    """Canned closes per ticker per date: {ticker: {date: close}}."""

    def __init__(self, series):
        self._series = series

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        days = self._series.get(ticker, {})
        return [
            Price(open=close, close=close, high=close, low=close,
                  volume=1000, time=f"{day}T00:00:00Z")
            for day, close in sorted(days.items())
            if start_date <= day <= end_date
        ]


class FakeAnalyst:
    """Fixed conviction per ticker, on every date."""

    investment_approach = "long_short"

    def __init__(self, name, views=None):
        self._name = name
        self._views = views or {}

    @property
    def name(self):
        return self._name

    def predict(self, ticker, date, data_client):
        return Signal(model_name=self._name, ticker=ticker, date=date,
                      value=self._views.get(ticker, 0.0))


@pytest.fixture(autouse=True)
def registered_fakes(monkeypatch):
    from hedge_fund.signals import ALPHA_MODEL_REGISTRY
    for name in ("a", "b"):
        monkeypatch.setitem(ALPHA_MODEL_REGISTRY, name, FakeAnalyst)


def _spec(**overrides):
    base = dict(
        schema_version=2,
        name="test-fund",
        strategies=[{"name": "solo", "models": [{"name": "a"}], "blend": {"mode": "long_short"}}],
        risk={"max_position_pct": 1.0, "max_gross_exposure": 1.0},
        capital=100_000.0,
        rebalance="weekly",
    )
    return FundSpec(**{**base, **overrides})


# Three trading weeks (Mon–Fri). Weekly grid = each Friday.
WEEKDAYS = [
    "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07",
    "2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14",
    "2024-06-17", "2024-06-18", "2024-06-19", "2024-06-20", "2024-06-21",
]
FRIDAYS = ["2024-06-07", "2024-06-14", "2024-06-21"]

# Initial Friday views execute on Monday at 200; subsequent daily marks move NAV.
SERIES = {
    "SPY": {day: (100.0 if i < 9 else 102.0 if i < 14 else 101.0)
            for i, day in enumerate(WEEKDAYS)},
    "AAPL": {day: (200.0 if i < 9 else 210.0 if i < 14 else 190.0)
             for i, day in enumerate(WEEKDAYS)},
}


def _run(series=SERIES, spec=None):
    spec = spec or _spec()
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    return backtest_fund(fund, "2024-06-03", "2024-06-21",
                         FakeDataClient(series), ["AAPL"])


# ---------------------------------------------------------------------------
# rebalance_grid
# ---------------------------------------------------------------------------

def test_grid_daily_is_identity():
    assert rebalance_grid(WEEKDAYS, "daily") == WEEKDAYS


def test_grid_weekly_takes_last_trading_day_of_each_iso_week():
    # A short holiday week (no Friday) still contributes its last day.
    days = ["2024-06-27", "2024-06-28", "2024-07-01", "2024-07-02", "2024-07-05"]
    assert rebalance_grid(days, "weekly") == ["2024-06-28", "2024-07-05"]
    assert rebalance_grid(WEEKDAYS, "weekly") == FRIDAYS


def test_grid_monthly_splits_where_weekly_does_not():
    # Dec 30 2024 – Jan 3 2025 is ONE ISO week but TWO calendar months.
    days = ["2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03"]
    assert rebalance_grid(days, "weekly") == ["2025-01-03"]
    assert rebalance_grid(days, "monthly") == ["2024-12-31", "2025-01-03"]


def test_grid_unknown_cadence_raises():
    with pytest.raises(ValueError, match="cadence"):
        rebalance_grid(WEEKDAYS, "hourly")


# ---------------------------------------------------------------------------
# backtest_fund
# ---------------------------------------------------------------------------

def test_happy_path_hand_computed():
    result = _run()

    assert result.dates == WEEKDAYS
    assert result.schema_version == 2
    assert len(result.records) == 2
    # Buy 500 at the following Monday close; later prices require no churn.
    assert result.records[0].positions == {"AAPL": 500}
    assert result.nav == [100_000.0] * 9 + [105_000.0] * 5 + [95_000.0]
    assert result.metrics.n_orders == 1
    # Benchmark scaled to starting capital off its first grid close.
    assert result.benchmark_nav == [100_000.0] * 9 + [102_000.0] * 5 + [101_000.0]

    m = result.metrics
    assert m.total_return_pct == pytest.approx(-0.05)
    assert m.benchmark_return_pct == pytest.approx(0.01)
    assert m.excess_return_pct == pytest.approx(-0.06)
    # Peak 105k -> trough 95k.
    assert m.max_drawdown_pct == pytest.approx(10_000 / 105_000, abs=1e-6)
    assert m.n_cycles == 2
    assert m.n_pending == 1
    assert result.pending[0].as_of == FRIDAYS[-1]


def test_positions_carry_across_cycles_not_restart():
    result = _run()
    # Positions persist across executions; only the marks moved.
    assert [r.positions for r in result.records] == [{"AAPL": 500}] * 2
    assert result.records[1].orders == []


def test_deterministic_json_round_trip():
    first, second = _run(), _run()
    assert first.model_dump_json() == second.model_dump_json()
    from hedge_fund.backtesting.fund import FundBacktestResult
    assert FundBacktestResult.model_validate_json(first.model_dump_json()) == first


def test_on_cycle_fires_per_tick_in_order():
    seen = []
    spec = _spec()
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    backtest_fund(fund, "2024-06-03", "2024-06-21", FakeDataClient(SERIES),
                  ["AAPL"],
                  on_cycle=lambda i, n, record: seen.append((i, n, record.as_of)))
    assert seen == [(0, 2, FRIDAYS[0]), (1, 2, FRIDAYS[1])]


def test_universe_round_trips_onto_the_result():
    """The study's tickers are recorded — the mandate never held them."""
    result = _run()
    assert result.universe == ["AAPL"]
    assert all(r.universe == ["AAPL"] for r in result.records)


def test_missing_benchmark_raises():
    series = {"AAPL": SERIES["AAPL"]}  # no SPY bars at all
    with pytest.raises(ValueError, match="trading grid"):
        _run(series=series)


def test_grid_follows_mandate_cadence():
    spec = _spec(rebalance="monthly")
    result = _run(spec=spec)
    assert result.dates == WEEKDAYS
    assert result.records == []
    assert result.pending[0].as_of == "2024-06-21"
    assert result.rebalance == "monthly"


@pytest.mark.parametrize("mode", ["long_only", "long_short", "dollar_neutral"])
def test_backtest_enforces_each_mode_with_mixed_analysts(mode):
    spec = _spec(strategies=[{"name": "mixed", "models": [{"name": "buffett"}, {"name": "druckenmiller"}], "blend": {"mode": mode}}])
    fund = Fund(spec, models={"mixed": [FakeAnalyst(name, {"AAPL": .8, "MSFT": -.6}) for name in ("buffett", "druckenmiller")]})
    series = {"SPY": {day: 100 for day in FRIDAYS}, "AAPL": {day: 100 for day in FRIDAYS}, "MSFT": {day: 100 for day in FRIDAYS}}
    result = backtest_fund(fund, FRIDAYS[0], FRIDAYS[-1], FakeDataClient(series), ["AAPL", "MSFT"])
    assert len(result.records) == 2
    assert result.nav == [100_000] * 3
    for record in result.records:
        assert record.positions["AAPL"] > 0
        if mode == "long_only":
            assert record.positions.get("MSFT", 0) == 0
        else:
            assert record.positions["MSFT"] < 0
        if mode == "dollar_neutral":
            assert sum(record.final_weights.values()) == pytest.approx(0)


def test_daily_callbacks_capture_losses_between_rebalances_and_after_last_trade():
    daily = []
    cycles = []
    series = {ticker: dict(values) for ticker, values in SERIES.items()}
    series["AAPL"]["2024-06-12"] = 100
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a", {"AAPL": 1})]})
    result = backtest_fund(fund, WEEKDAYS[0], WEEKDAYS[-1], FakeDataClient(series), ["AAPL"],
                           on_cycle=lambda i, n, r: cycles.append((i, n, r)),
                           on_valuation=lambda i, n, v: daily.append((i, n, v)))
    assert len(daily) == 15
    assert len(cycles) == 2
    assert daily[7][2].nav == 50_000
    assert result.metrics.max_drawdown_pct == .5
    assert result.nav[-1] == 95_000
    assert [v.nav for _, _, v in daily] == result.nav
    assert [r.execution_as_of for _, _, r in cycles] == ["2024-06-10", "2024-06-17"]


def test_single_session_window_is_cash_with_pending_proposal():
    fund = Fund(_spec(), models={"solo": [FakeAnalyst("a", {"AAPL": 1})]})
    result = backtest_fund(fund, FRIDAYS[0], FRIDAYS[0], FakeDataClient(SERIES), ["AAPL"])
    assert result.nav == result.benchmark_nav == [100_000]
    assert result.records == []
    assert len(result.pending) == 1
    assert result.metrics.total_return_pct == 0
    assert result.metrics.annualized_return_pct == 0
    assert result.metrics.max_drawdown_pct == 0
    assert result.metrics.sharpe_ratio == 0


def test_missing_daily_mark_for_held_ticker_stops_replay():
    series = {ticker: dict(values) for ticker, values in SERIES.items()}
    del series["AAPL"]["2024-06-12"]
    with pytest.raises(ValueError, match="AAPL.*2024-06-12"):
        _run(series)


def test_daily_sharpe_uses_consecutive_returns_without_initial_zero():
    import numpy as np
    from hedge_fund.backtesting.fund import performance_metrics
    nav = [100, 110, 99, 118.8]
    dates = ["2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06"]
    result = performance_metrics(100, dates, nav, [100] * 4, [])
    returns = np.array([.1, -.1, .2])
    assert result.sharpe_ratio == pytest.approx(returns.mean() / returns.std(ddof=1) * np.sqrt(252), abs=1e-4)
    assert result.n_cycles == 0


def test_schedule_shares_deduplicated_initial_and_refresh_dates():
    from hedge_fund.backtesting.fund import build_schedule
    schedule = build_schedule(FakeDataClient(SERIES), "SPY", WEEKDAYS[0], WEEKDAYS[-1], "weekly")
    assert schedule.execution_dates == {"2024-06-07": "2024-06-10", "2024-06-14": "2024-06-17", "2024-06-21": None}
    assert schedule.assessment_dates == ["2024-06-07", "2024-06-09", "2024-06-14", "2024-06-16", "2024-06-21"]
    daily = build_schedule(FakeDataClient(SERIES), "SPY", "2024-06-03", "2024-06-04", "daily")
    assert daily.assessment_dates == ["2024-06-03", "2024-06-04"]


def test_backtest_excludes_current_session_even_if_provider_returns_it(monkeypatch):
    from datetime import datetime
    from hedge_fund.data import sessions
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2024, 6, 10, 23, tzinfo=tz)
    monkeypatch.setattr(sessions, "datetime", Clock)
    result = _run()
    assert result.dates == WEEKDAYS[:5]
    assert result.records == []
    assert result.pending[0].as_of == "2024-06-07"
    assert result.nav == [100_000] * 5


def test_daily_replay_executes_before_creating_next_assessment():
    events = []
    class ObservedAnalyst(FakeAnalyst):
        def predict(self, ticker, date, data_client):
            events.append(("assessment", date))
            return super().predict(ticker, date, data_client)
    fund = Fund(_spec(rebalance="daily"), models={"solo": [ObservedAnalyst("a", {"AAPL": 1})]})
    backtest_fund(fund, WEEKDAYS[0], WEEKDAYS[1], FakeDataClient(SERIES), ["AAPL"],
                  on_cycle=lambda i, n, r: events.append(("execution", r.execution_as_of)),
                  on_valuation=lambda i, n, v: events.append(("valuation", v.as_of)))
    assert events == [("valuation", "2024-06-03"), ("assessment", "2024-06-03"),
                      ("execution", "2024-06-04"), ("valuation", "2024-06-04"),
                      ("assessment", "2024-06-04")]
