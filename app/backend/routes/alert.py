"""Alert routes — list, mark-read, settings, telegram-test, manual scan."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.models.alert_schemas import (
    AlertListResponse,
    AlertSettingsRequest,
    AlertSettingsResponse,
    ScanResponse,
    TelegramTestResponse,
)
from app.backend.services.alert_service import (
    get_alert_settings,
    list_alerts,
    mark_all_read,
    mark_alert_read,
    scan_now,
    test_telegram as service_test_telegram,
    update_alert_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=AlertListResponse)
def list_alerts_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    return list_alerts(db, limit, offset, unread_only)


@router.post("/{alert_id}/read", response_model=dict)
def mark_read_endpoint(alert_id: int, db: Session = Depends(get_db)) -> dict:
    if not mark_alert_read(db, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}


@router.post("/read-all", response_model=dict)
def mark_all_read_endpoint(db: Session = Depends(get_db)) -> dict:
    n = mark_all_read(db)
    return {"ok": True, "marked": n}


@router.post("/scan", response_model=ScanResponse)
async def scan_endpoint() -> ScanResponse:
    try:
        return await scan_now()
    except Exception as exc:
        logger.exception("Manual alert scan failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/settings", response_model=AlertSettingsResponse)
def get_settings_endpoint(db: Session = Depends(get_db)) -> AlertSettingsResponse:
    return get_alert_settings(db)


@router.put("/settings", response_model=AlertSettingsResponse)
def update_settings_endpoint(
    req: AlertSettingsRequest,
    db: Session = Depends(get_db),
) -> AlertSettingsResponse:
    return update_alert_settings(db, req)


@router.post("/test-telegram", response_model=TelegramTestResponse)
async def test_telegram_endpoint(db: Session = Depends(get_db)) -> TelegramTestResponse:
    return await service_test_telegram(db)
