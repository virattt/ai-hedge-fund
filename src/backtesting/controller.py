from __future__ import annotations

from typing import Callable, Sequence, Dict, Any

from .types import AgentOutput, AgentDecisions, PortfolioSnapshot, ActionLiteral, Action
from .portfolio import Portfolio


class AgentController:
    """Responsible for invoking the trading agent and normalizing outputs."""

    def run_agent(
        self,
        agent: Callable[..., AgentOutput],
        *,
        tickers: Sequence[str],
        start_date: str,
        end_date: str,
        portfolio: Portfolio | PortfolioSnapshot,
        model_name: str,
        model_provider: str,
        selected_analysts: Sequence[str] | None,
    ) -> AgentOutput:
        # Ensure we pass a plain snapshot dict to preserve legacy expectations
        if isinstance(portfolio, Portfolio):
            portfolio_payload: PortfolioSnapshot = portfolio.get_snapshot()
        else:
            portfolio_payload = portfolio

        output = agent(
            tickers=list(tickers),
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio_payload,
            model_name=model_name,
            model_provider=model_provider,
            selected_analysts=list(selected_analysts) if selected_analysts is not None else None,
        )

        # Normalize outputs to avoid None/missing keys
        decisions_in: Dict[str, Any] = dict(output.get("decisions", {})) if isinstance(output, dict) else {}
        analyst_signals_in: Dict[str, Any] = dict(output.get("analyst_signals", {})) if isinstance(output, dict) else {}

        normalized_decisions: AgentDecisions = {}
        for ticker in tickers:
            d = decisions_in.get(ticker, {})
            action = d.get("action", "hold")
            qty = d.get("quantity", 0)
            # Basic coercions mirroring Backtester expectations
            try:
                qty_val = float(qty)
            except Exception:
                qty_val = 0.0
            try:
                action = Action(action).value  # validate/coerce
            except Exception:
                action = Action.HOLD.value  # type: ignore[assignment]
            normalized_decisions[ticker] = {"action": action, "quantity": qty_val}  # type: ignore[assignment]

        # Preserve any agent-provided analyst signals without modification
        normalized_output: AgentOutput = {
            "decisions": normalized_decisions,
            "analyst_signals": analyst_signals_in,
        }
        return normalized_output


