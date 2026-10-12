"""JWT issuing and verification for the dashboard API.

A single shared site password (checked against settings.site_password) is
still the credential — this isn't per-user auth — but access to every route
beyond /auth/login and /health now requires a valid, unexpired bearer token
instead of the frontend just remembering it got a "success": true once.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import settings

ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token() -> str:
    """Issue a token proving the caller supplied the correct site password.

    No per-user claims exist yet (there's no user model), so the payload only
    carries a subject marker and expiry.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": "dashboard", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """FastAPI dependency: raise 401 unless a valid bearer token is present."""
    if settings.site_password is None:
        return  # auth disabled in this environment (e.g. local dev), same as before
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _decode(credentials.credentials)
