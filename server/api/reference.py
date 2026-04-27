"""Reference data endpoints — analysts and models.

Pulls from the existing canonical sources:
  - ``ANALYST_CONFIG`` at ``src/utils/analysts.py:16``
  - ``AVAILABLE_MODELS`` at ``src/llm/models.py:46``
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

# Ensure the repo's ``src/`` is importable. The CLI uses bare imports like
# ``from utils.analysts import ...`` (no ``src.`` prefix), so we extend
# sys.path the same way both ``src/main.py`` and ``src/backtester.py`` do
# implicitly when run from the project root.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from llm.models import AVAILABLE_MODELS  # noqa: E402
from utils.analysts import ANALYST_CONFIG  # noqa: E402

from ..schemas import AnalystInfo, ModelInfo

router = APIRouter()


@router.get("/analysts", response_model=list[AnalystInfo])
def list_analysts() -> list[AnalystInfo]:
    return [
        AnalystInfo(key=key, display_name=cfg["display_name"], order=cfg["order"])
        for key, cfg in sorted(ANALYST_CONFIG.items(), key=lambda kv: kv[1]["order"])
    ]


@router.get("/models", response_model=list[ModelInfo])
def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(
            display_name=m.display_name,
            model_name=m.model_name,
            provider=m.provider.value,
        )
        for m in AVAILABLE_MODELS
    ]
