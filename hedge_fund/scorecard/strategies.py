"""Strategy attribution — which sleeve made the money.

A period runs from one execution to the next. A sleeve's return over it is
its contribution to the book at the first execution (`final_contribution`,
a fraction of fund equity per name) times each name's move to the next
execution, at the exact prices both executions were filled at. Dollars are
that return on the equity the weights were sized against.

The sleeves are target weights, not the whole-share positions that were
actually bought, so they do not sum to the fund. The gap is reported as the
scorecard's `unattributed`, never spread over the sleeves.
"""

from __future__ import annotations

from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard.models import StrategyScore


def score_strategies(records: list[SessionRecord]) -> list[StrategyScore]:
    """One score per strategy that appeared in an execution followed by
    another, in the order they first appear. A name with no price at either
    end of a period earned the fund nothing and contributes nothing."""
    executions = [r for r in records if r.executed is not None]
    total = fund_pnl(records)
    period_returns: dict[str, list[float]] = {}
    dollars: dict[str, float] = {}
    for current, following in zip(executions, executions[1:]):
        equity = current.executed.equity_before
        for strategy in current.executed.strategies:
            period = 0.0
            for ticker, fraction in strategy.final_contribution.items():
                if fraction == 0:
                    continue
                price_now = current.price_at(ticker)
                price_next = following.price_at(ticker)
                if price_now is None or price_next is None:
                    continue
                period += fraction * (price_next / price_now - 1)
            period_returns.setdefault(strategy.name, []).append(period)
            dollars[strategy.name] = dollars.get(strategy.name, 0.0) + period * equity

    scores: list[StrategyScore] = []
    for name, returns in period_returns.items():
        scores.append(StrategyScore(
            name=name,
            n_periods=len(returns),
            pnl=dollars[name],
            return_pct=_compound(returns),
            win_rate=sum(1 for r in returns if r > 0) / len(returns),
            share_of_pnl=dollars[name] / total if total != 0 else None,
            max_drawdown_pct=_max_drawdown(returns),
        ))
    return scores


def fund_pnl(records: list[SessionRecord]) -> float:
    """Pre-fill equity at the last execution minus the first. Pre-fill at
    both ends so a cost model, once one exists, lands in `unattributed`."""
    executions = [r for r in records if r.executed is not None]
    if len(executions) < 2:
        return 0.0
    return executions[-1].executed.equity_before - executions[0].executed.equity_before


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compound(returns: list[float]) -> float:
    value = 1.0
    for r in returns:
        value *= 1 + r
    return value - 1


def _max_drawdown(returns: list[float]) -> float:
    value = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        value *= 1 + r
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > worst:
            worst = drawdown
    return worst
