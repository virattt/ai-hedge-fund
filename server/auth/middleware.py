"""Bearer token authentication middleware (F4b).

If ``AHF_APP_TOKEN`` is set, all protected endpoints require
``Authorization: Bearer <token>``.  When unset, the server runs in
open-access dev mode.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings

_security = HTTPBearer(auto_error=False)


async def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> None:
    """FastAPI dependency that enforces bearer token auth.

    Designed to be attached to routers via ``dependencies=[Depends(require_token)]``.
    """
    settings = get_settings()
    if not settings.app_token:
        # No token configured -> open access (dev mode)
        return
    if not credentials or credentials.credentials != settings.app_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
