from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from collections import defaultdict

from app.backend.database import get_db
from app.backend.database.models import Account
from app.backend.repositories.holdings_repository import HoldingsRepository
from app.backend.services.indicators_service import compute_indicators, determine_action_label, compute_risk_score
from app.backend.services.api_key_service import ApiKeyService
from app.backend.portfolio.sector_fallback import get_sector_fallback
from app.backend.models.holdings import (
    DashboardHolding, DashboardResponse,
    AllocationItem, AccountSummaryItem,
)

router = APIRouter(prefix="/dashboard")


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    portfolio: Optional[str] = Query(None, description="Filter by portfolio name"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    db: Session = Depends(get_db),
):
    repo = HoldingsRepository(db)
    holdings = repo.get_all(portfolio_name=portfolio, account_id=account_id)

    api_key_service = ApiKeyService(db)
    api_keys = api_key_service.get_api_keys_dict()
    financial_api_key = api_keys.get("FINANCIAL_DATASETS_API_KEY")

    # Pre-load account labels
    account_map: dict[int, Account] = {}
    account_ids = {h.account_id for h in holdings if h.account_id}
    if account_ids:
        accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        account_map = {a.id: a for a in accounts}

    dashboard_holdings: list[DashboardHolding] = []
    total_cost = 0.0
    total_value = 0.0
    risk_scores: list[int] = []

    # Allocation trackers
    sector_values: dict[str, float] = defaultdict(float)
    account_values: dict[int, float] = defaultdict(float)
    account_costs: dict[int, float] = defaultdict(float)
    account_counts: dict[int, int] = defaultdict(int)

    indicators_cache: dict[str, dict] = {}

    for h in holdings:
        quantity = float(h.quantity)
        buy_price = float(h.buy_price)
        cost_basis = float(h.cost_basis) if h.cost_basis else quantity * buy_price

        total_cost += cost_basis

        ticker = h.ticker
        if ticker not in indicators_cache:
            indicators_cache[ticker] = compute_indicators(ticker, api_key=financial_api_key)
        indicators = indicators_cache[ticker]

        current_price = indicators.get("current_price")
        current_value = quantity * current_price if current_price else None
        profit_loss = (current_value - cost_basis) if current_value else None
        profit_loss_pct = (profit_loss / cost_basis * 100) if profit_loss is not None and cost_basis > 0 else None

        holding_value = current_value if current_value else cost_basis
        total_value += holding_value

        # Risk score
        risk_score = compute_risk_score(
            indicators.get("rsi_14"),
            indicators.get("trend"),
            profit_loss_pct,
        )
        if risk_score is not None:
            risk_scores.append(risk_score)

        action_label = determine_action_label(
            indicators.get("rsi_14"),
            indicators.get("trend"),
        )

        # Allocation tracking
        sector = h.sector or get_sector_fallback(h.ticker)
        sector_values[sector] += holding_value

        if h.account_id:
            account_values[h.account_id] += holding_value
            account_costs[h.account_id] += cost_basis
            account_counts[h.account_id] += 1

        # Account label
        account_label = None
        if h.account_id and h.account_id in account_map:
            acct = account_map[h.account_id]
            account_label = acct.label or f"{acct.owner_name} {acct.account_type}"

        dashboard_holdings.append(DashboardHolding(
            id=h.id,
            portfolio_name=h.portfolio_name,
            account_id=h.account_id,
            account_label=account_label,
            ticker=ticker,
            investment_name=h.investment_name,
            quantity=quantity,
            buy_price=buy_price,
            cost_basis=cost_basis,
            currency=h.currency,
            sector=h.sector,
            current_price=current_price,
            current_value=round(current_value, 2) if current_value else None,
            profit_loss=round(profit_loss, 2) if profit_loss else None,
            profit_loss_pct=round(profit_loss_pct, 2) if profit_loss_pct else None,
            rsi_14=indicators.get("rsi_14"),
            sma_20=indicators.get("sma_20"),
            sma_50=indicators.get("sma_50"),
            trend=indicators.get("trend"),
            action_label=action_label,
            risk_score=risk_score,
        ))

    total_profit_loss = total_value - total_cost
    total_profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else None

    # Overall risk score (weighted average would be ideal, but simple mean works)
    overall_risk = round(sum(risk_scores) / len(risk_scores)) if risk_scores else None

    # Sector allocation
    allocation_by_sector = []
    if total_value > 0:
        for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
            allocation_by_sector.append(AllocationItem(
                label=sector,
                value=round(value, 2),
                percentage=round(value / total_value * 100, 1),
            ))

    # Account allocation
    allocation_by_account = []
    if total_value > 0:
        for acct_id, value in sorted(account_values.items(), key=lambda x: -x[1]):
            acct = account_map.get(acct_id)
            label = (acct.label or f"{acct.owner_name} {acct.account_type}") if acct else f"Account {acct_id}"
            allocation_by_account.append(AllocationItem(
                label=label,
                value=round(value, 2),
                percentage=round(value / total_value * 100, 1),
            ))

    # Account summaries
    account_summaries = []
    for acct_id in account_values:
        acct = account_map.get(acct_id)
        if not acct:
            continue
        acct_value = account_values[acct_id]
        acct_cost = account_costs[acct_id]
        acct_pl = acct_value - acct_cost
        acct_pl_pct = (acct_pl / acct_cost * 100) if acct_cost > 0 else None
        account_summaries.append(AccountSummaryItem(
            account_id=acct_id,
            label=acct.label or f"{acct.owner_name} {acct.account_type}",
            owner_name=acct.owner_name,
            total_cost=round(acct_cost, 2),
            total_value=round(acct_value, 2),
            profit_loss=round(acct_pl, 2),
            profit_loss_pct=round(acct_pl_pct, 2) if acct_pl_pct is not None else None,
            holdings_count=account_counts[acct_id],
        ))

    return DashboardResponse(
        holdings=dashboard_holdings,
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        total_profit_loss=round(total_profit_loss, 2),
        total_profit_loss_pct=round(total_profit_loss_pct, 2) if total_profit_loss_pct else None,
        overall_risk_score=overall_risk,
        allocation_by_sector=allocation_by_sector,
        allocation_by_account=allocation_by_account,
        account_summaries=account_summaries,
    )
