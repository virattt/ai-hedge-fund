"""The scorecard — who is right, and which sleeve makes the money.

The feedback loop. `score` reads a fund's SessionRecords (a backtest's
`records`, a paper fund's ledger) and grades every analyst and every
strategy on what happened next; `allocate` turns those grades into the
weights the next decision uses. Nothing is stored; both are derived from
the ledger at the point of use, and the decision records what it used.
"""

from __future__ import annotations

from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard.allocation import allocate, current_allocation
from hedge_fund.scorecard.analysts import score_analysts
from hedge_fund.scorecard.models import AnalystScore, Scorecard, StrategyScore
from hedge_fund.scorecard.strategies import fund_pnl, score_strategies, trading_cost


def score(records: list[SessionRecord]) -> Scorecard:
    """Grade *records*, in session order. Raises ValueError on an empty list."""
    if not records:
        raise ValueError("nothing to score: no sessions recorded")
    return Scorecard(
        fund=records[0].fund,
        first_session=records[0].session,
        last_session=records[-1].session,
        analysts=score_analysts(records),
        strategies=score_strategies(records),
        fund_pnl=fund_pnl(records),
        trading_cost=trading_cost(records),
    )


__all__ = [
    "AnalystScore", "Scorecard", "StrategyScore", "allocate", "current_allocation",
    "score", "score_analysts", "score_strategies",
]
