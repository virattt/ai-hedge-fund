
from typing import Optional, List
from app.backend.models.schemas import PortfolioPosition


def create_portfolio(initial_cash: float, margin_requirement: float, tickers: list[str], portfolio_positions: Optional[List[PortfolioPosition]] = None) -> dict:
    # Initialize base portfolio structure
    portfolio = {
        "cash": initial_cash,  # Initial cash amount
        "margin_requirement": margin_requirement,  # Initial margin requirement
        "margin_used": 0.0,  # total margin usage across all short positions
        "positions": {
            ticker: {
                "long": 0,  # Number of shares held long
                "short": 0,  # Number of shares held short
                "long_cost_basis": 0.0,  # Average cost basis for long positions
                "short_cost_basis": 0.0,  # Average price at which shares were sold short
                "short_margin_used": 0.0,  # Dollars of margin used for this ticker's short
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,  # Realized gains from long positions
                "short": 0.0,  # Realized gains from short positions
            }
            for ticker in tickers
        },
    }
    
    # If portfolio positions are provided, populate them
    if portfolio_positions:
        for position in portfolio_positions:
            ticker = position.ticker
            quantity = position.quantity
            trade_price = position.trade_price
            
            # Ensure ticker exists in portfolio (it should from tickers list)
            if ticker in portfolio["positions"]:
                if quantity > 0:
                    # Positive quantity means long position
                    portfolio["positions"][ticker]["long"] = quantity
                    portfolio["positions"][ticker]["long_cost_basis"] = trade_price
                elif quantity < 0:
                    # Negative quantity means short position
                    portfolio["positions"][ticker]["short"] = abs(quantity)
                    portfolio["positions"][ticker]["short_cost_basis"] = trade_price
                    # Calculate margin used for short position
                    portfolio["positions"][ticker]["short_margin_used"] = abs(quantity) * trade_price * margin_requirement
                    portfolio["margin_used"] += portfolio["positions"][ticker]["short_margin_used"]
    
    return portfolio