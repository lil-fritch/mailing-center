"""API endpoints for authentication."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import create_access_token
from app.core.settings import settings

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginErrorResponse(BaseModel):
    detail: str


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    responses={401: {"model": LoginErrorResponse}},
)
async def login(request: LoginRequest):
    """Exchange the shared site password for a short-lived JWT.

    There's one password for the whole dashboard, not per-user accounts —
    the token just lets every other route check "was the password supplied
    recently" without storing the password itself in the frontend.
    """
    if settings.site_password and request.password != settings.site_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    return LoginResponse(access_token=create_access_token())
