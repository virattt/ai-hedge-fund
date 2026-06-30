from sqlalchemy.orm import Session
from typing import Optional
from app.backend.database.models import Holding


class HoldingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, portfolio_name: Optional[str] = None, account_id: Optional[int] = None) -> list[Holding]:
        query = self.db.query(Holding)
        if portfolio_name:
            query = query.filter(Holding.portfolio_name == portfolio_name)
        if account_id:
            query = query.filter(Holding.account_id == account_id)
        return query.order_by(Holding.portfolio_name, Holding.ticker).all()

    def get_by_id(self, holding_id: int) -> Optional[Holding]:
        return self.db.query(Holding).filter(Holding.id == holding_id).first()

    def create(self, portfolio_name: str, ticker: str, investment_name: str,
               quantity: float, buy_price: float, cost_basis: Optional[float],
               currency: str, account_id: Optional[int] = None,
               sector: Optional[str] = None) -> Holding:
        if cost_basis is None:
            cost_basis = quantity * buy_price
        holding = Holding(
            portfolio_name=portfolio_name,
            account_id=account_id,
            ticker=ticker.upper().strip(),
            investment_name=investment_name.strip(),
            quantity=str(quantity),
            buy_price=str(buy_price),
            cost_basis=str(cost_basis),
            currency=currency.upper().strip(),
            sector=sector.strip() if sector else None,
        )
        self.db.add(holding)
        self.db.commit()
        self.db.refresh(holding)
        return holding

    def update(self, holding_id: int, **kwargs) -> Optional[Holding]:
        holding = self.get_by_id(holding_id)
        if not holding:
            return None
        for key, value in kwargs.items():
            if value is not None:
                if key in ("quantity", "buy_price", "cost_basis"):
                    setattr(holding, key, str(value))
                elif key == "ticker":
                    setattr(holding, key, value.upper().strip())
                elif key == "currency":
                    setattr(holding, key, value.upper().strip())
                else:
                    setattr(holding, key, value)
        if "quantity" in kwargs or "buy_price" in kwargs:
            q = float(holding.quantity)
            p = float(holding.buy_price)
            holding.cost_basis = str(q * p)
        self.db.commit()
        self.db.refresh(holding)
        return holding

    def delete(self, holding_id: int) -> bool:
        holding = self.get_by_id(holding_id)
        if not holding:
            return False
        self.db.delete(holding)
        self.db.commit()
        return True

    def get_portfolios(self) -> list[str]:
        results = self.db.query(Holding.portfolio_name).distinct().all()
        return [r[0] for r in results]
