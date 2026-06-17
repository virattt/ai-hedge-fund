from sqlalchemy.orm import Session
from typing import Optional
from app.backend.database.models import Watchlist


class WatchlistRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Watchlist]:
        return self.db.query(Watchlist).order_by(Watchlist.ticker).all()

    def get_by_id(self, item_id: int) -> Optional[Watchlist]:
        return self.db.query(Watchlist).filter(Watchlist.id == item_id).first()

    def create(self, ticker: str, investment_name: Optional[str] = None, notes: Optional[str] = None) -> Watchlist:
        item = Watchlist(
            ticker=ticker.upper().strip(),
            investment_name=investment_name.strip() if investment_name else None,
            notes=notes,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: int) -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True
