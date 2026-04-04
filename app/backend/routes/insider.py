"""FastAPI routes for insider trading data.

NOTE: This file is being rewritten in Phase 2.1 to add /summary and /detail endpoints.
The old /transactions endpoint has been removed along with the schemas it depended on.
"""
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider", tags=["insider"])
