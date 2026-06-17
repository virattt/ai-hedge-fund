import hashlib
import secrets
import os
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# The app password is stored as a SHA-256 hash in the environment variable APP_PASSWORD_HASH.
# If not set, auth is disabled (development mode).
# To generate a hash: python -c "import hashlib; print(hashlib.sha256(b'your-password').hexdigest())"


def _get_password_hash() -> str | None:
    return os.environ.get("APP_PASSWORD_HASH")


def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> bool:
    password_hash = _get_password_hash()
    if password_hash is None:
        return True  # Auth disabled in dev mode

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    provided_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if not secrets.compare_digest(provided_hash, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return True
