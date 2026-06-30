from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.repositories.accounts_repository import AccountsRepository
from app.backend.models.accounts import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
)

router = APIRouter(prefix="/accounts")


@router.get("", response_model=list[AccountResponse])
async def list_accounts(db: Session = Depends(get_db)):
    repo = AccountsRepository(db)
    return repo.get_all()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: Session = Depends(get_db)):
    repo = AccountsRepository(db)
    account = repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    repo = AccountsRepository(db)
    account = repo.create(
        owner_name=data.owner_name,
        account_type=data.account_type,
        provider=data.provider,
        label=data.label,
    )
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    repo = AccountsRepository(db)
    update_data = data.model_dump(exclude_unset=True)
    account = repo.update(account_id, **update_data)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    repo = AccountsRepository(db)
    deleted = repo.delete(account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
