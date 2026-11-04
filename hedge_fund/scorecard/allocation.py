"""The allocator — the second half of the feedback loop.

A multi-manager gives capital to the pods with a record; a quant desk
weights its signals by their IC; both shrink toward the prior while the
record is short. Here both move by one rule, `AllocationPolicy.multiplier`:
a confidence multiplier on the mandate weight, from the t-stat the
scorecard measured. Nothing is stored beyond the decision that used it:
the allocation is derived from the ledger at the point of use, and the
DecisionRecord carries the weights it was made with.
"""

from __future__ import annotations

from typing import Callable

from hedge_fund.fund import AllocationPolicy, FundSpec
from hedge_fund.pipeline.models import Allocated, AllocationRecord
from hedge_fund.pipeline.session import FundState, SessionRecord
from hedge_fund.scorecard.analysts import score_analysts
from hedge_fund.scorecard.strategies import score_strategies


def allocate(spec: FundSpec, records: list[SessionRecord], as_of: str) -> AllocationRecord:
    """Every strategy slice and model weight the mandate names, moved by the
    scorecard of *records*. An empty ledger, or a strategy or analyst the
    scorecard has not graded, keeps the mandate's weight. An analyst is
    graded fund-wide, so a persona in two strategies moves the same way in
    both."""
    policy = spec.allocation
    if policy is None:
        raise ValueError(f"{spec.name}: the mandate has no allocation policy")
    pods = {s.name: s for s in score_strategies(records)} if records else {}
    analysts = {a.name: a for a in score_analysts(records)} if records else {}
    strategies: dict[str, Allocated] = {}
    models: dict[str, dict[str, Allocated]] = {}
    for strategy in spec.strategies:
        pod = pods.get(strategy.name)
        strategies[strategy.name] = _allocated(
            policy, strategy.weight,
            pod.t_stat if pod is not None else None, pod.n_periods if pod is not None else 0,
        )
        models[strategy.name] = {}
        for model in strategy.models:
            analyst = analysts.get(model.name)
            models[strategy.name][model.name] = _allocated(
                policy, model.weight,
                analyst.ic_t_stat if analyst is not None else None, analyst.n_dates if analyst is not None else 0,
            )
    return AllocationRecord(as_of=as_of, strategies=strategies, models=models)


def current_allocation(
    spec: FundSpec, state: FundState, session: str, records: Callable[[], list[SessionRecord]],
) -> AllocationRecord | None:
    """The allocation a decision at *session* uses: none when the mandate has
    no policy; the state's when it was scored on the same New York day, so a
    minute fund scores once a day and a daily or weekly fund at every
    decision; otherwise a fresh one from the ledger *records* returns."""
    if spec.allocation is None:
        return None
    if state.allocation is not None and state.allocation.as_of[:10] == session[:10]:
        return state.allocation
    return allocate(spec, records(), session)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _allocated(policy: AllocationPolicy, mandate: float, t_stat: float | None, n: int) -> Allocated:
    return Allocated(mandate=mandate, t_stat=t_stat, n=n, weight=mandate * policy.multiplier(t_stat, n))
