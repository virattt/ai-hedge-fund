import json

from langchain_core.messages import HumanMessage

from src.main import run_hedge_fund
from src.agents.portfolio_manager import PortfolioDecision, PortfolioManagerOutput


def test_mocked_e2e_flow_analyst_risk_portfolio(monkeypatch):
    def demo_analyst_agent(state, agent_id="demo_analyst_agent"):
        data = state["data"]
        data["analyst_signals"][agent_id] = {
            "AAPL": {
                "signal": "bearish",
                "confidence": 80,
                "reasoning": "Mock bearish signal",
            }
        }
        message = HumanMessage(content=json.dumps(data["analyst_signals"][agent_id]), name=agent_id)
        return {"messages": state["messages"] + [message], "data": data}

    def demo_risk_agent(state, agent_id="risk_management_agent"):
        data = state["data"]
        data["analyst_signals"][agent_id] = {
            "AAPL": {
                "remaining_position_limit": 2000.0,
                "current_price": 100.0,
                "reasoning": {"note": "Mock risk"},
            }
        }
        message = HumanMessage(content=json.dumps(data["analyst_signals"][agent_id]), name=agent_id)
        return {"messages": state["messages"] + [message], "data": data}

    def fake_call_llm(prompt, pydantic_model, agent_name=None, state=None, max_retries=3, default_factory=None):
        return PortfolioManagerOutput(
            decisions={
                "AAPL": PortfolioDecision(
                    action="sell",
                    quantity=3,
                    confidence=90,
                    reasoning="Mock LLM chose sell",
                )
            }
        )

    monkeypatch.setattr(
        "src.main.get_analyst_nodes",
        lambda: {"demo": ("demo_analyst_agent", demo_analyst_agent)},
    )
    monkeypatch.setattr("src.main.risk_management_agent", demo_risk_agent)
    monkeypatch.setattr("src.agents.portfolio_manager.call_llm", fake_call_llm)

    portfolio = {
        "cash": 10000.0,
        "margin_requirement": 0.5,
        "margin_used": 0.0,
        "positions": {
            "AAPL": {
                "long": 5,
                "short": 0,
                "long_cost_basis": 95.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {
            "AAPL": {
                "long": 0.0,
                "short": 0.0,
            }
        },
    }

    result = run_hedge_fund(
        tickers=["AAPL"],
        start_date="2026-03-01",
        end_date="2026-04-01",
        portfolio=portfolio,
        show_reasoning=False,
        selected_analysts=["demo"],
        model_name="qwen2.5:7b",
        model_provider="Ollama",
    )

    assert result["decisions"]["AAPL"]["action"] == "sell"
    assert result["decisions"]["AAPL"]["quantity"] == 3
    assert "demo_analyst_agent" in result["analyst_signals"]
    assert "risk_management_agent" in result["analyst_signals"]
