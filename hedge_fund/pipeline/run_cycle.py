"""Assess investment views and execute them at a subsequent completed close."""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from math import isfinite

from hedge_fund.brokers.models import Fill
from hedge_fund.brokers.protocol import Broker
from hedge_fund.data.protocol import DataClient
from hedge_fund.data.sessions import completed_through, previous_day, session_closes
from hedge_fund.fund import Fund, normalize_universe
from hedge_fund.models import Signal
from hedge_fund.pipeline.execution import build_orders
from hedge_fund.pipeline.models import (
    CycleRecord,
    DecisionRecord,
    PendingRunResult,
    StrategyRecord,
    TickerSkip,
)
from hedge_fund.portfolio.construction import blend_signals, WEIGHT_TOLERANCE
from hedge_fund.portfolio.validation import validate_targets
from hedge_fund.risk.limits import apply_limits
from hedge_fund.signals import get_investment_approach

# How far back to look for the most recent close: covers weekends, holiday
# clusters, and short trading halts without reaching into stale history.
_MARK_LOOKBACK_DAYS = 7


def assess_fund(
    fund: Fund, as_of: str, data_client: DataClient, universe: list[str],
) -> DecisionRecord:
    """Construct validated target weights using only the assessment cutoff."""
    if as_of > completed_through():
        raise ValueError(f"assessment {as_of} requires incomplete daily data")
    spec = fund.spec.model_copy(deep=True)
    universe = normalize_universe(universe)
    marks, skipped = _mark_prices(universe, as_of, data_client)

    tradeable = [t for t in universe if t in marks]

    # Each strategy runs its own analysts and blends its own sleeve; the fund
    # nets the sleeves by capital slice. A persona staffed into two strategies
    # is asked twice, but the second ask is a prompt-cache hit, not spend.
    total_slice = sum(s.weight for s, _ in fund.strategies)
    strategy_records: list[StrategyRecord] = []
    netted: dict[str, float] = {t: 0.0 for t in tradeable}
    for strategy, staff in fund.strategies:
        signals: list[Signal] = []
        for ticker in tradeable:
            for model in staff:
                signals.append(model.predict(ticker, as_of, data_client))
        blend = blend_signals(
            signals, strategy.model_weights, strategy.blend.gross_target,
            mode=strategy.blend.mode,
            investment_approaches={m.name: get_investment_approach(m.name) for m in strategy.models},
        )
        slice_ = strategy.weight / total_slice
        for ticker, weight in blend.weights.items():
            netted[ticker] += slice_ * weight
        strategy_records.append(StrategyRecord(
            name=strategy.name,
            slice=slice_,
            signals=signals,
            convictions=blend.convictions,
            weights=blend.weights,
            eligible_scores=blend.eligible_scores,
            flat_reason=blend.flat_reason,
        ))

    preserve_proportions = any(s.blend.mode == "dollar_neutral" for s in spec.strategies)
    risk = apply_limits(netted, spec.risk, preserve_proportions=preserve_proportions)
    if risk.scale_factor is not None:
        multipliers = dict.fromkeys(netted, risk.scale_factor)
    else:
        # Exactly offset contributions stay visible even though no net trade remains.
        multipliers = {ticker: risk.weights[ticker] / weight if weight != 0 else 1.0 for ticker, weight in netted.items()}
    for record in strategy_records:
        record.final_contribution = {
            ticker: record.slice * weight * multipliers[ticker]
            for ticker, weight in record.weights.items()
        }
    validate_targets(spec, strategy_records, risk.weights)

    return DecisionRecord(
        fund=spec.name, as_of=as_of, spec=spec, universe=universe,
        marks=marks, skipped=skipped, strategies=strategy_records,
        target_weights=netted, clamps=risk.clamps,
        risk_scale_factor=risk.scale_factor, final_weights=risk.weights,
    )


def exact_marks(tickers: list[str], session: str, data_client: DataClient) -> dict[str, float]:
    """Require a finite, positive close for every name on the exact session."""
    if session > completed_through():
        raise ValueError(f"{session}: daily prices are not yet complete")
    marks: dict[str, float] = {}
    for ticker in sorted(set(tickers)):
        bars = data_client.get_prices(ticker, session, session)
        matches = [bar for bar in bars if bar.time[:10] == session]
        if not matches:
            raise ValueError(f"{ticker}: missing close on {session}; cannot value the book or execute")
        close = max(matches, key=lambda bar: bar.time).close
        if not isfinite(close) or close <= 0:
            raise ValueError(f"{ticker}: close on {session} must be finite and positive, got {close}")
        marks[ticker] = close
    return marks


def execute_decision(
    fund: Fund, original: DecisionRecord, session: str,
    broker: Broker, data_client: DataClient,
) -> CycleRecord:
    """Refresh views before sizing a complete rebalance at exact closing prices."""
    if session <= original.as_of or session > completed_through():
        raise ValueError(f"execution session {session} must follow {original.as_of} and be complete")
    if fund.spec != original.spec:
        raise ValueError("fund mandate changed after assessment; create a new assessment")
    cutoff = previous_day(session)
    effective = original if cutoff == original.as_of else assess_fund(
        fund, cutoff, data_client, original.universe,
    )
    spec = effective.spec
    validate_targets(spec, effective.strategies, effective.final_weights)
    held = broker.positions()
    targets = {t: w for t, w in effective.final_weights.items() if w != 0}
    marks = exact_marks(list(set(held) | set(targets)), session, data_client)
    cash_before = broker.cash()
    equity_before = cash_before + sum(p.shares * marks[t] for t, p in held.items())
    if not isfinite(equity_before) or equity_before <= 0:
        raise ValueError(f"{spec.name}: equity on {session} must be finite and positive")
    orders = build_orders(targets, held, marks, equity_before)
    projected = {t: p.shares for t, p in held.items()}
    for order in orders:
        projected[order.ticker] = projected.get(order.ticker, 0) + (
            order.quantity if order.side == "buy" else -order.quantity
        )
    weights = {t: shares * marks[t] / equity_before for t, shares in projected.items()}
    for ticker, weight in weights.items():
        if not isfinite(weight) or abs(weight) > spec.risk.max_position_pct + WEIGHT_TOLERANCE:
            raise ValueError(f"{ticker}: projected position violates max_position_pct")
    if sum(abs(w) for w in weights.values()) > spec.risk.max_gross_exposure + WEIGHT_TOLERANCE:
        raise ValueError("projected portfolio violates max_gross_exposure")
    fills: list[Fill] = [broker.place_order(order) for order in orders]
    positions = {t: p.shares for t, p in broker.positions().items()}
    cash = broker.cash()
    fields = effective.model_dump(exclude={"as_of", "marks"})
    return CycleRecord(
        **fields, as_of=original.as_of, marks=marks,
        equity_before=equity_before, cash_before=cash_before,
        orders=orders, fills=fills, positions=positions, cash=cash,
        nav=cash + sum(shares * marks[t] for t, shares in positions.items()),
        original_assessment=original.model_copy(deep=True),
        refreshed_assessment=effective.model_copy(deep=True),
        execution_as_of=session, execution_policy="next_close",
    )


def run_cycle(
    fund: Fund, as_of: str, broker: Broker, data_client: DataClient,
    universe: list[str],
) -> CycleRecord | PendingRunResult:
    """Assess at the effective cutoff and execute only on a later completed session."""
    as_of = min(_date.fromisoformat(as_of).isoformat(), completed_through())
    proposal = assess_fund(fund, as_of, data_client, universe)
    start = (_date.fromisoformat(as_of) + timedelta(days=1)).isoformat()
    closes = session_closes(data_client, fund.spec.benchmark, start, completed_through())
    if not closes:
        return PendingRunResult(
            fund=fund.spec.name, as_of=as_of, proposal=proposal,
            reason="No subsequent completed benchmark session is available. Run again explicitly when data is available.",
        )
    return execute_decision(fund, proposal, min(closes), broker, data_client)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _mark_prices(
    tickers: list[str],
    as_of: str,
    data_client: DataClient,
) -> tuple[dict[str, float], list[TickerSkip]]:
    """Analytical lookback marks; names without data are excluded from assessment."""
    start = (_date.fromisoformat(as_of) - timedelta(days=_MARK_LOOKBACK_DAYS)).isoformat()
    marks: dict[str, float] = {}
    skipped: list[TickerSkip] = []

    for ticker in tickers:
        prices = data_client.get_prices(ticker, start, as_of)
        bars = [p for p in prices if start <= p.time[:10] <= as_of]
        if bars:
            marks[ticker] = max(bars, key=lambda p: p.time).close
            if not isfinite(marks[ticker]) or marks[ticker] <= 0:
                raise ValueError(f"{ticker}: analytical close on {as_of} must be finite and positive")
        else:
            skipped.append(TickerSkip(
                ticker=ticker,
                reason=f"no close within {_MARK_LOOKBACK_DAYS} days of {as_of}",
            ))

    return marks, skipped
