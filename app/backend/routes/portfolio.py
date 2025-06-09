from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.backend.services.portfolio import create_portfolio

router = APIRouter(prefix="/portfolio")

class CreatePortfolioRequest(BaseModel):
    initial_cash: float = 100000.0
    margin_requirement: float = 0.5
    tickers: List[str]

class PortfolioPosition(BaseModel):
    ticker: str
    long_shares: int = 0
    short_shares: int = 0
    long_cost_basis: float = 0.0
    short_cost_basis: float = 0.0

class UpdatePortfolioRequest(BaseModel):
    positions: List[PortfolioPosition]

# Store portfolio in memory (in production, use a database)
_portfolio_store: Dict[str, dict] = {}

@router.post("/create")
async def create_new_portfolio(request: CreatePortfolioRequest):
    """Create a new portfolio with initial cash and tickers"""
    try:
        portfolio = create_portfolio(
            initial_cash=request.initial_cash,
            margin_requirement=request.margin_requirement,
            tickers=request.tickers
        )
        
        # Store portfolio (use a unique ID in production)
        portfolio_id = "default"
        _portfolio_store[portfolio_id] = portfolio
        
        return {
            "portfolio_id": portfolio_id,
            "portfolio": portfolio,
            "message": "Portfolio created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
async def get_portfolio(portfolio_id: str = "default"):
    """Get current portfolio"""
    if portfolio_id not in _portfolio_store:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    return _portfolio_store[portfolio_id]

@router.put("/positions")
async def update_portfolio_positions(
    request: UpdatePortfolioRequest, 
    portfolio_id: str = "default"
):
    """Update portfolio positions"""
    if portfolio_id not in _portfolio_store:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    portfolio = _portfolio_store[portfolio_id]
    
    print(request.positions)
    print(portfolio)
    
    for position in request.positions:
        # Create position entry if it doesn't exist (for new tickers)
        if position.ticker not in portfolio["positions"]:
            portfolio["positions"][position.ticker] = {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            # Also initialize realized gains for new ticker
            portfolio["realized_gains"][position.ticker] = {
                "long": 0.0,
                "short": 0.0,
            }
        
        # Update position values
        portfolio["positions"][position.ticker]["long"] = position.long_shares
        portfolio["positions"][position.ticker]["short"] = position.short_shares
        portfolio["positions"][position.ticker]["long_cost_basis"] = position.long_cost_basis
        portfolio["positions"][position.ticker]["short_cost_basis"] = position.short_cost_basis
    
    return {
        "message": "Portfolio positions updated",
        "portfolio": portfolio
    }

@router.get("/summary")
async def get_portfolio_summary(portfolio_id: str = "default"):
    """Get portfolio summary with current values"""
    if portfolio_id not in _portfolio_store:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    portfolio = _portfolio_store[portfolio_id]
    
    # Calculate total positions value (you might want to fetch real-time prices)
    total_long_value = 0
    total_short_value = 0
    
    for ticker, position in portfolio["positions"].items():
        # For demo purposes, using cost basis. In production, use current market prices
        total_long_value += position["long"] * position["long_cost_basis"]
        total_short_value += position["short"] * position["short_cost_basis"]
    
    total_value = portfolio["cash"] + total_long_value - total_short_value
    
    return {
        "cash": portfolio["cash"],
        "total_long_value": total_long_value,
        "total_short_value": total_short_value,
        "total_portfolio_value": total_value,
        "margin_used": portfolio["margin_used"],
        "margin_requirement": portfolio["margin_requirement"],
        "positions_count": len([p for p in portfolio["positions"].values() if p["long"] > 0 or p["short"] > 0])
    } 