"""The scorecard — who is right, and which sleeve makes the money.

The first half of the feedback loop: measurement only. `score` reads a
fund's SessionRecords (a backtest's `records`, a paper fund's ledger) and
grades every analyst and every strategy on what happened next. Nothing is
stored; the scorecard is derived from the ledger at the point of use.
"""

from __future__ import annotations

from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard.analysts import score_analysts
from hedge_fund.scorecard.models import AnalystScore, Scorecard, StrategyScore
from hedge_fund.scorecard.strategies import fund_pnl, score_strategies, trading_cost


def score(records: list[SessionRecord]) -> Scorecard:
    """Grade *records*, in session order. Raises ValueError on an empty list."""
    if not records:
        raise ValueError("nothing to score: no sessions recorded")
    first_decision = next((r.decision for r in records if r.decision is not None), None)
    return Scorecard(
        fund=records[0].fund,
        first_session=records[0].session,
        last_session=records[-1].session,
        horizon=first_decision.spec.cadence_label if first_decision is not None else None,
        analysts=score_analysts(records),
        strategies=score_strategies(records),
        fund_pnl=fund_pnl(records),
        trading_cost=trading_cost(records),
    )


__all__ = ["AnalystScore", "Scorecard", "StrategyScore", "score", "score_analysts", "score_strategies"]
