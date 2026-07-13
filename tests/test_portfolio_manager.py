from src.agents.portfolio_manager import compute_allowed_actions


def test_allowed_actions_exclude_restricted_short_proceeds() -> None:
    portfolio = {
        "cash": 2_000.0,
        "margin_requirement": 0.5,
        "margin_used": 500.0,
        "positions": {
            "AAPL": {
                "long": 0,
                "short": 10,
                "short_cost_basis": 100.0,
            }
        },
    }

    actions = compute_allowed_actions(
        ["AAPL"], {"AAPL": 100.0}, {"AAPL": 100}, portfolio,
    )

    assert actions["AAPL"]["buy"] == 5
    assert actions["AAPL"]["short"] == 10
