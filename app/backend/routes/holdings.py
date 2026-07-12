from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.backend.database import get_db
from app.backend.repositories.holdings_repository import HoldingsRepository
from app.backend.services.holdings_service import HoldingsService
from app.backend.models.holdings import (
    HoldingCreate,
    HoldingUpdate,
    HoldingResponse,
    HoldingImportRequest,
    HoldingImportResponse,
)

router = APIRouter(prefix="/holdings")


def _to_response(holding) -> HoldingResponse:
    return HoldingResponse(
        id=holding.id,
        portfolio_name=holding.portfolio_name,
        account_id=holding.account_id,
        ticker=holding.ticker,
        investment_name=holding.investment_name,
        quantity=float(holding.quantity),
        buy_price=float(holding.buy_price),
        cost_basis=float(holding.cost_basis) if holding.cost_basis else None,
        currency=holding.currency,
        sector=holding.sector,
        created_at=holding.created_at,
        updated_at=holding.updated_at,
    )


@router.get("", response_model=list[HoldingResponse])
async def list_holdings(
    portfolio: Optional[str] = Query(None, description="Filter by portfolio name"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    db: Session = Depends(get_db),
):
    repo = HoldingsRepository(db)
    holdings = repo.get_all(portfolio_name=portfolio, account_id=account_id)
    return [_to_response(h) for h in holdings]


@router.get("/portfolios", response_model=list[str])
async def list_portfolios(db: Session = Depends(get_db)):
    repo = HoldingsRepository(db)
    return repo.get_portfolios()


@router.get("/{holding_id}", response_model=HoldingResponse)
async def get_holding(holding_id: int, db: Session = Depends(get_db)):
    repo = HoldingsRepository(db)
    holding = repo.get_by_id(holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")
    return _to_response(holding)


@router.post("", response_model=HoldingResponse, status_code=201)
async def create_holding(data: HoldingCreate, db: Session = Depends(get_db)):
    repo = HoldingsRepository(db)
    holding = repo.create(
        portfolio_name=data.portfolio_name,
        account_id=data.account_id,
        ticker=data.ticker,
        investment_name=data.investment_name,
        quantity=data.quantity,
        buy_price=data.buy_price,
        cost_basis=data.cost_basis,
        currency=data.currency,
        sector=data.sector,
    )
    return _to_response(holding)


@router.put("/{holding_id}", response_model=HoldingResponse)
async def update_holding(holding_id: int, data: HoldingUpdate, db: Session = Depends(get_db)):
    repo = HoldingsRepository(db)
    update_data = data.model_dump(exclude_unset=True)
    holding = repo.update(holding_id, **update_data)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")
    return _to_response(holding)


@router.delete("/{holding_id}", status_code=204)
async def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    repo = HoldingsRepository(db)
    deleted = repo.delete(holding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Holding not found")


@router.post("/import-csv", response_model=HoldingImportResponse)
async def import_csv(data: HoldingImportRequest, db: Session = Depends(get_db)):
    service = HoldingsService(db)
    rows, errors = service.parse_csv_text(data.csv_text)
    if not rows and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    imported = service.import_holdings(data.portfolio_name, rows)
    return HoldingImportResponse(imported=imported, errors=errors)
