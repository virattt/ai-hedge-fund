"""Tests for the execution risk governor."""

from __future__ import annotations

from integrations.alpaca.risk_governor import RiskGovernor, RiskGovernorConfig
from integrations.broker.models import OrderResult, TradeOrder


def _governor(tmp_path, **overrides) -> RiskGovernor:
    defaults = dict(
        enabled=True,
        max_turnover_x=1.0,
        max_fills_per_day=40,
        symbol_cooldown_minutes=60,
        max_open_positions=15,
        max_intraday_drawdown_pct=0.5,
        min_triggered_heavy_confidence=70.0,
        state_dir=str(tmp_path),
    )
    defaults.update(overrides)
    return RiskGovernor(RiskGovernorConfig(**defaults))


def _order(ticker: str, action: str, qty: int) -> TradeOrder:
    return TradeOrder(ticker=ticker, action=action, quantity=qty, reason="test")


_FLAT = {"long": 0, "short": 0}


def _positions(**named) -> dict:
    return {k: v for k, v in named.items()}


class TestRiskGovernor:
    def test_risk_reducing_orders_always_pass(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_turnover_x=0.0001, max_fills_per_day=0)
        positions = _positions(AAPL={"long": 100, "short": 0}, CP={"long": 0, "short": 50})
        orders = [_order("AAPL", "sell", 100), _order("CP", "cover", 50)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=positions, equity=50_000.0,
            prices={"AAPL": 300.0, "CP": 90.0}, cycle_kind="light",
        )

        assert len(allowed) == 2 and not vetoed

    def test_turnover_cap_vetoes_entries(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_turnover_x=1.0)
        # 100k equity -> $100k budget; first order 90k passes, second 20k breaches.
        orders = [_order("AAPL", "buy", 300), _order("MSFT", "buy", 50)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=_positions(AAPL=_FLAT, MSFT=_FLAT), equity=100_000.0,
            prices={"AAPL": 300.0, "MSFT": 400.0}, cycle_kind="heavy",
        )

        assert [o.ticker for o in allowed] == ["AAPL"]
        assert len(vetoed) == 1 and "turnover cap" in vetoed[0].message

    def test_fill_cap_vetoes_entries(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_fills_per_day=1)
        orders = [_order("AAPL", "buy", 1), _order("MSFT", "buy", 1)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=_positions(AAPL=_FLAT, MSFT=_FLAT), equity=100_000.0,
            prices={"AAPL": 100.0, "MSFT": 100.0}, cycle_kind="heavy",
        )

        assert [o.ticker for o in allowed] == ["AAPL"]
        assert "fill cap" in vetoed[0].message

    def test_symbol_cooldown_blocks_reentry(self, tmp_path) -> None:
        gov = _governor(tmp_path)
        submitted = OrderResult(
            submitted=True, dry_run=False, order=_order("NVDA", "buy", 10), message="ok"
        )
        gov.record_submissions([submitted], prices={"NVDA": 200.0})

        # A fresh instance (same day, same state dir) must see the cooldown.
        gov2 = _governor(tmp_path)
        allowed, vetoed = gov2.filter_orders(
            [_order("NVDA", "buy", 10)], positions=_positions(NVDA=_FLAT),
            equity=100_000.0, prices={"NVDA": 200.0}, cycle_kind="heavy",
        )

        assert not allowed
        assert "cooldown" in vetoed[0].message

    def test_max_open_positions_blocks_new_names_not_resizes(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_open_positions=1)
        positions = _positions(AAPL={"long": 10, "short": 0}, MSFT=_FLAT)
        orders = [_order("AAPL", "buy", 5), _order("MSFT", "buy", 5)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=positions, equity=100_000.0,
            prices={"AAPL": 100.0, "MSFT": 100.0}, cycle_kind="heavy",
        )

        assert [o.ticker for o in allowed] == ["AAPL"]  # resize of held name passes
        assert "max open positions" in vetoed[0].message

    def test_drawdown_breaker_allows_only_reductions(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_intraday_drawdown_pct=0.5)
        positions = _positions(AAPL={"long": 100, "short": 0}, MSFT=_FLAT)
        # Seed day-open equity at 100k, then report equity down 1%.
        gov.filter_orders([], positions=positions, equity=100_000.0, prices={}, cycle_kind="light")
        orders = [_order("MSFT", "buy", 10), _order("AAPL", "sell", 100)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=positions, equity=99_000.0,
            prices={"AAPL": 100.0, "MSFT": 100.0}, cycle_kind="light",
        )

        assert [o.ticker for o in allowed] == ["AAPL"]
        assert "drawdown breaker" in vetoed[0].message

    def test_triggered_heavy_confidence_gate(self, tmp_path) -> None:
        gov = _governor(tmp_path, min_triggered_heavy_confidence=70.0)
        decisions = {
            "AAPL": {"action": "buy", "quantity": 10, "confidence": 55.0},
            "MSFT": {"action": "buy", "quantity": 10, "confidence": 85.0},
        }
        orders = [_order("AAPL", "buy", 10), _order("MSFT", "buy", 10)]

        allowed, vetoed = gov.filter_orders(
            orders, positions=_positions(AAPL=_FLAT, MSFT=_FLAT), equity=100_000.0,
            prices={"AAPL": 100.0, "MSFT": 100.0}, cycle_kind="triggered_heavy",
            decisions=decisions,
        )

        assert [o.ticker for o in allowed] == ["MSFT"]
        assert "conviction" in vetoed[0].message

    def test_scheduled_heavy_not_confidence_gated(self, tmp_path) -> None:
        gov = _governor(tmp_path)
        decisions = {"AAPL": {"action": "buy", "quantity": 10, "confidence": 55.0}}

        allowed, vetoed = gov.filter_orders(
            [_order("AAPL", "buy", 10)], positions=_positions(AAPL=_FLAT),
            equity=100_000.0, prices={"AAPL": 100.0}, cycle_kind="heavy",
            decisions=decisions,
        )

        assert len(allowed) == 1 and not vetoed

    def test_disabled_governor_passes_everything(self, tmp_path) -> None:
        gov = _governor(tmp_path, enabled=False, max_fills_per_day=0, max_turnover_x=0.0)

        allowed, vetoed = gov.filter_orders(
            [_order("AAPL", "buy", 1000)], positions=_positions(AAPL=_FLAT),
            equity=100.0, prices={"AAPL": 100.0}, cycle_kind="heavy",
        )

        assert len(allowed) == 1 and not vetoed

    def test_budgets_persist_across_instances(self, tmp_path) -> None:
        gov = _governor(tmp_path, max_fills_per_day=1)
        submitted = OrderResult(
            submitted=True, dry_run=False, order=_order("AAPL", "buy", 10), message="ok"
        )
        gov.record_submissions([submitted], prices={"AAPL": 100.0})

        gov2 = _governor(tmp_path, max_fills_per_day=1)
        allowed, vetoed = gov2.filter_orders(
            [_order("MSFT", "buy", 10)], positions=_positions(MSFT=_FLAT),
            equity=100_000.0, prices={"MSFT": 100.0}, cycle_kind="heavy",
        )

        assert not allowed and "fill cap" in vetoed[0].message
