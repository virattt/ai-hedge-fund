from src.main import create_workflow, parse_hedge_fund_response
from src.agents.portfolio_manager import compute_allowed_actions


def test_workflow_has_core_nodes_and_selected_analyst():
    workflow = create_workflow(selected_analysts=["technical_analyst"])

    node_names = set(workflow.nodes.keys())
    assert "start_node" in node_names
    assert "technical_analyst_agent" in node_names
    assert "risk_management_agent" in node_names
    assert "portfolio_manager" in node_names


def test_parse_hedge_fund_response_valid_and_invalid_json():
    ok = parse_hedge_fund_response('{"AAPL": {"action": "hold"}}')
    assert ok == {"AAPL": {"action": "hold"}}

    bad = parse_hedge_fund_response("not-json")
    assert bad is None


def test_compute_allowed_actions_sell_and_hold():
    tickers = ["AAPL"]
    current_prices = {"AAPL": 100.0}
    max_shares = {"AAPL": 10}
    portfolio = {
        "cash": 0.0,
        "positions": {
            "AAPL": {
                "long": 5,
                "short": 0,
                "long_cost_basis": 90.0,
                "short_cost_basis": 0.0,
            }
        },
        "margin_requirement": 0.5,
        "margin_used": 0.0,
        "equity": 1000.0,
    }

    allowed = compute_allowed_actions(
        tickers=tickers,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
    )

    assert "AAPL" in allowed
    assert allowed["AAPL"]["hold"] == 0
    assert allowed["AAPL"]["sell"] == 5
