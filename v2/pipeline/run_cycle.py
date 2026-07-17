"""run_cycle — one tick of the fund, the same code path in every mode.

    point-in-time data -> analysts -> blend -> risk -> execution -> record

This is the fund's heartbeat. A backtest is run_cycle in a loop over history
with a SimBroker; paper trading is the same loop on a live clock with a
PaperBroker; live is the same loop with a real broker. Only the clock and the
broker change — the pipeline never does.

run_cycle is the pipeline's only impure piece: it talks to the data client
and the broker. Every stage it delegates to (blend_signals, apply_limits,
build_orders) is a pure function. Determinism: given the same spec, date,
broker state, and data responses, the returned record is byte-identical —
with the one caveat that a cold LLM cache makes an agent's first live call
nondeterministic; the prompt cache makes every replay exact.

Notable behavior, chosen deliberately:
- Targets are the complete statement of the desired book. If every analyst
  abstains or goes neutral, the targets are all zero and the fund closes to
  flat. The record shows `abstained` on each signal, so an outer loop (the
  Day-5 daemon) can decide to skip a tick instead — that guard belongs
  outside the pipeline.
- A universe ticker with no price and no position is skipped (recorded, its
  analysts never called): unlisted/delisted names are normal in history.
  A HELD ticker with no price raises — a fund that cannot price its own
  book has an infrastructure problem, and its NAV would be a lie.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

from v2.brokers.models import Fill
from v2.brokers.protocol import Broker
from v2.data.protocol import DataClient
from v2.fund.spec import Fund
from v2.models import Signal
from v2.pipeline.execution import build_orders
from v2.pipeline.models import CycleRecord, TickerSkip
from v2.portfolio.construction import blend_signals
from v2.risk.limits import apply_limits

# How far back to look for the most recent close: covers weekends, holiday
# clusters, and short trading halts without reaching into stale history.
_MARK_LOOKBACK_DAYS = 7


def run_cycle(
    fund: Fund,
    as_of: str,
    broker: Broker,
    data_client: DataClient,
) -> CycleRecord:
    """Run one tick of *fund* as of *as_of* (YYYY-MM-DD) and return the record."""
    spec = fund.spec
    held = broker.positions()

    marks, skipped = _mark_prices(
        sorted(set(spec.universe) | set(held)), as_of, held, data_client,
    )

    cash_before = broker.cash()
    equity_before = cash_before + sum(
        p.shares * marks[t] for t, p in held.items()
    )
    if equity_before <= 0:
        raise ValueError(
            f"{spec.name}: equity is {equity_before:.2f} as of {as_of} — "
            "cannot size positions against a non-positive book"
        )

    tradeable = [t for t in spec.universe if t in marks]
    signals: list[Signal] = []
    for ticker in tradeable:
        for model in fund.analysts:
            signals.append(model.predict(ticker, as_of, data_client))

    blend = blend_signals(signals, fund.analyst_weights, spec.blend.gross_target)
    risk = apply_limits(blend.weights, spec.risk)

    orders = build_orders(risk.weights, held, marks, equity_before)
    fills: list[Fill] = [broker.place_order(o) for o in orders]

    positions_after = {t: p.shares for t, p in broker.positions().items()}
    cash_after = broker.cash()
    nav = cash_after + sum(s * marks[t] for t, s in positions_after.items())

    return CycleRecord(
        fund=spec.name,
        as_of=as_of,
        spec=spec,
        marks=marks,
        skipped=skipped,
        signals=signals,
        convictions=blend.convictions,
        target_weights=blend.weights,
        clamps=risk.clamps,
        final_weights=risk.weights,
        equity_before=equity_before,
        cash_before=cash_before,
        orders=orders,
        fills=fills,
        positions=positions_after,
        cash=cash_after,
        nav=nav,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _mark_prices(
    tickers: list[str],
    as_of: str,
    held: dict,
    data_client: DataClient,
) -> tuple[dict[str, float], list[TickerSkip]]:
    """Last close on or before *as_of* for each ticker, within the lookback.

    No bar and not held -> TickerSkip (the caller then never runs analysts
    on it). No bar but HELD -> raise: the book cannot be honestly valued.
    """
    start = (_date.fromisoformat(as_of) - timedelta(days=_MARK_LOOKBACK_DAYS)).isoformat()
    marks: dict[str, float] = {}
    skipped: list[TickerSkip] = []

    for ticker in tickers:
        prices = data_client.get_prices(ticker, start, as_of)
        bars = [p for p in prices if p.time[:10] <= as_of]
        if bars:
            marks[ticker] = max(bars, key=lambda p: p.time).close
        elif ticker in held:
            raise ValueError(
                f"held position {ticker} has no price within "
                f"{_MARK_LOOKBACK_DAYS} days of {as_of} — cannot value the book"
            )
        else:
            skipped.append(TickerSkip(
                ticker=ticker,
                reason=f"no close within {_MARK_LOOKBACK_DAYS} days of {as_of}",
            ))

    return marks, skipped
