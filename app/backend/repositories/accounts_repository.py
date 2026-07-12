from sqlalchemy.orm import Session
from typing import Optional
from app.backend.database.models import Account


class AccountsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Account]:
        return self.db.query(Account).order_by(Account.owner_name).all()

    def get_by_id(self, account_id: int) -> Optional[Account]:
        return self.db.query(Account).filter(Account.id == account_id).first()

    def get_by_owner(self, owner_name: str) -> list[Account]:
        return self.db.query(Account).filter(Account.owner_name == owner_name).all()

    def create(self, owner_name: str, account_type: str = "ISA",
               provider: str = "AJ Bell", label: Optional[str] = None) -> Account:
        account = Account(
            owner_name=owner_name.strip(),
            account_type=account_type.strip(),
            provider=provider.strip(),
            label=label.strip() if label else None,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update(self, account_id: int, **kwargs) -> Optional[Account]:
        account = self.get_by_id(account_id)
        if not account:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(account, key, value.strip() if isinstance(value, str) else value)
        self.db.commit()
        self.db.refresh(account)
        return account

    def delete(self, account_id: int) -> bool:
        account = self.get_by_id(account_id)
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        return True
