"""backtest_fund tests — fake data client + fake analysts, real broker + pipeline."""

import pytest

from v2.backtesting.fund import backtest_fund, rebalance_grid
from v2.data.models import Price
from v2.fund.spec import Fund, FundSpec
from v2.models import Signal


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

    def __init__(self, name, views=None):
        self._name = name
        self._views = views or {}

    @property
    def name(self):
        return self._name

    def predict(self, ticker, date, data_client):
        return Signal(model_name=self._name, ticker=ticker, date=date,
                      value=self._views.get(ticker, 0.0))


def _spec(**overrides):
    base = dict(
        name="test-fund",
        universe=["AAPL"],
        strategies=[{"name": "solo", "models": [{"name": "a"}]}],
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

# Closes chosen so 100k always targets exactly 500 AAPL shares — the fund
# buys once and then correctly has nothing to trade.
SERIES = {
    "SPY": {day: close for day, close in
            zip(FRIDAYS, [100.0, 102.0, 101.0])},
    "AAPL": {day: close for day, close in
             zip(FRIDAYS, [200.0, 210.0, 190.0])},
}


def _run(series=SERIES, spec=None):
    spec = spec or _spec()
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    return backtest_fund(fund, "2024-06-03", "2024-06-21",
                         FakeDataClient(series))


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

    assert result.dates == FRIDAYS
    assert len(result.records) == 3
    # Week 1: buy 500 @ 200 (full conviction, 100% cap). Weeks 2-3: the
    # closes are chosen so the target stays exactly 500 shares — no churn.
    assert result.records[0].positions == {"AAPL": 500}
    assert result.nav == [100_000.0, 105_000.0, 95_000.0]
    assert result.metrics.n_orders == 1
    # Benchmark scaled to starting capital off its first grid close.
    assert result.benchmark_nav == [100_000.0, 102_000.0, 101_000.0]

    m = result.metrics
    assert m.total_return_pct == pytest.approx(-0.05)
    assert m.benchmark_return_pct == pytest.approx(0.01)
    assert m.excess_return_pct == pytest.approx(-0.06)
    # Peak 105k -> trough 95k.
    assert m.max_drawdown_pct == pytest.approx(10_000 / 105_000, abs=1e-6)
    assert m.n_cycles == 3


def test_positions_carry_across_cycles_not_restart():
    result = _run()
    # Same book all three weeks; only the marks moved.
    assert [r.positions for r in result.records] == [{"AAPL": 500}] * 3
    assert result.records[1].orders == []
    assert result.records[2].orders == []


def test_deterministic_json_round_trip():
    first, second = _run(), _run()
    assert first.model_dump_json() == second.model_dump_json()
    from v2.backtesting.fund import FundBacktestResult
    assert FundBacktestResult.model_validate_json(first.model_dump_json()) == first


def test_on_cycle_fires_per_tick_in_order():
    seen = []
    spec = _spec()
    fund = Fund(spec, models={"solo": [FakeAnalyst("a", views={"AAPL": 1.0})]})
    backtest_fund(fund, "2024-06-03", "2024-06-21", FakeDataClient(SERIES),
                  on_cycle=lambda i, n, record: seen.append((i, n, record.as_of)))
    assert seen == [(0, 3, FRIDAYS[0]), (1, 3, FRIDAYS[1]), (2, 3, FRIDAYS[2])]


def test_missing_benchmark_raises():
    series = {"AAPL": SERIES["AAPL"]}  # no SPY bars at all
    with pytest.raises(ValueError, match="trading grid"):
        _run(series=series)


def test_grid_follows_mandate_cadence():
    spec = _spec(rebalance="monthly")
    result = _run(spec=spec)
    assert result.dates == ["2024-06-21"]  # one June rebalance
    assert result.rebalance == "monthly"
