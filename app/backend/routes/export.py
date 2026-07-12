import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.backend.database import get_db
from app.backend.database.models import Account
from app.backend.repositories.holdings_repository import HoldingsRepository

router = APIRouter(prefix="/export")


@router.get("/csv")
async def export_csv(
    portfolio: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    repo = HoldingsRepository(db)
    holdings = repo.get_all(portfolio_name=portfolio, account_id=account_id)

    # Load account info
    account_map: dict[int, Account] = {}
    account_ids = {h.account_id for h in holdings if h.account_id}
    if account_ids:
        accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        account_map = {a.id: a for a in accounts}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Account", "Portfolio", "Ticker", "Investment Name",
        "Quantity", "Buy Price", "Cost Basis", "Currency", "Sector", "Date Added"
    ])

    for h in holdings:
        account_label = ""
        if h.account_id and h.account_id in account_map:
            acct = account_map[h.account_id]
            account_label = acct.label or f"{acct.owner_name} {acct.account_type}"

        writer.writerow([
            account_label,
            h.portfolio_name,
            h.ticker,
            h.investment_name,
            h.quantity,
            h.buy_price,
            h.cost_basis or "",
            h.currency,
            h.sector or "",
            h.created_at.strftime("%Y-%m-%d") if h.created_at else "",
        ])

    output.seek(0)
    filename = f"portfolio_export_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
