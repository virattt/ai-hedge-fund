"""Settings routes — persist app-wide configuration (e.g. selected LLM)."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.database.models import AppSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

_DEFAULT_MODEL_NAME = "qwen3:latest"
_DEFAULT_MODEL_PROVIDER = "Ollama"


class LLMSettingResponse(BaseModel):
    model_name: str
    model_provider: str


class LLMSettingRequest(BaseModel):
    model_name: str
    model_provider: str


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


@router.get("/llm", response_model=LLMSettingResponse)
def get_llm_setting(db: Session = Depends(get_db)) -> LLMSettingResponse:
    model_name = _get_setting(db, "llm_model_name") or _DEFAULT_MODEL_NAME
    model_provider = _get_setting(db, "llm_model_provider") or _DEFAULT_MODEL_PROVIDER
    return LLMSettingResponse(model_name=model_name, model_provider=model_provider)


@router.put("/llm", response_model=LLMSettingResponse)
def set_llm_setting(request: LLMSettingRequest, db: Session = Depends(get_db)) -> LLMSettingResponse:
    _upsert_setting(db, "llm_model_name", request.model_name)
    _upsert_setting(db, "llm_model_provider", request.model_provider)
    db.commit()
    return LLMSettingResponse(model_name=request.model_name, model_provider=request.model_provider)
