# Pre-Trade Governance Checklist

This project is for education and research, not live trading. If you extend the
agent pipeline toward execution, add a final governance gate between the risk
manager and any order-routing component. The gate should be independent from
the agent that proposed the trade and should make the decision auditable.

## Gate Outcomes

Use a small, explicit decision vocabulary:

- `approve`: no material governance concern was detected.
- `approve_with_concerns`: the trade can proceed only after the listed concerns
  are reviewed.
- `reject`: the trade should not be routed without a new analysis cycle.

Each outcome should include a short reason, the input snapshot used for the
decision, and the checks that were run.

## Minimum Checks

Before approving a proposed order, verify:

- Position size versus portfolio equity, available cash, and margin limits.
- Incremental exposure by ticker, sector, asset class, and strategy sleeve.
- Current drawdown, daily loss, and realized or unrealized loss limits.
- Liquidity, stale price, market-hours, and missing-data conditions.
- Correlation or concentration against existing holdings.
- Fee, spread, and slippage assumptions versus the expected edge.
- Agreement between the proposed action and the risk manager's max position
  limit for the ticker.
- Whether the proposal depends on incomplete analyst signals or missing
  financial data.

## Suggested Input Record

A governance gate should receive a compact, serializable record rather than raw
agent chat history:

```json
{
  "ticker": "DEMO",
  "proposed_action": "buy",
  "quantity": 100,
  "estimated_price": 25.5,
  "portfolio_equity": 100000,
  "current_position": 250,
  "risk_limit": 500,
  "analyst_signal_summary": {
    "bullish": 4,
    "neutral": 2,
    "bearish": 1
  },
  "risk_manager_reason": "Position remains below max exposure after trade."
}
```

Keep the schema stable so failed gates can be replayed during post-trade review.

## Audit Trail

For every proposed order, store:

- The governance outcome and reason.
- The input record hash or serialized input record.
- The timestamp and pipeline run ID.
- The model or deterministic rule version used by the gate.
- Any missing inputs that forced a conservative decision.

The audit record should make it possible to answer why a trade was allowed,
why it was blocked, and which data was available at the time.

## Failure Policy

For research simulations, a missing governance result can be logged and skipped.
For any system connected to execution, prefer fail-closed behavior: if the gate
times out, cannot parse inputs, or detects stale data, return `reject` or hold
the position until the issue is resolved.
