import hashlib
import hmac
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.config import settings

auth_router = APIRouter()

COOKIE_NAME = "babytrack_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 90  # 90 días


class PinLoginRequest(BaseModel):
    pin: str = Field(..., min_length=1, max_length=20)
    activeParent: Optional[str] = Field("MAMA", description="MAMA o PAPA")


class AuthStatusResponse(BaseModel):
    authenticated: bool
    activeParent: str
    pinConfigured: bool


def create_session_token(pin: str, active_parent: str = "MAMA") -> str:
    parent = active_parent.upper() if active_parent and active_parent.upper() in {"MAMA", "PAPA"} else "MAMA"
    secret = (settings.FAMILY_ACCESS_PIN or "1419").encode("utf-8")
    msg = f"authenticated:{parent}".encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return f"{parent}.{sig}"


def verify_session_token(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    parent, sig = token.split(".", 1)
    if parent not in {"MAMA", "PAPA"}:
        return None
    expected = create_session_token(settings.FAMILY_ACCESS_PIN, parent).split(".", 1)[1]
    if hmac.compare_digest(sig, expected):
        return parent
    return None


@auth_router.post("/login", response_model=AuthStatusResponse)
def login_with_pin(payload: PinLoginRequest, response: Response):
    """Verifica el PIN familiar compartido y establece una cookie firmada HttpOnly."""
    expected_pin = (settings.FAMILY_ACCESS_PIN or "1419").strip()
    if payload.pin.strip() != expected_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN familiar incorrecto.",
        )

    parent = (payload.activeParent or "MAMA").upper()
    if parent not in {"MAMA", "PAPA"}:
        parent = "MAMA"

    token = create_session_token(expected_pin, parent)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return AuthStatusResponse(authenticated=True, activeParent=parent, pinConfigured=True)


@auth_router.post("/logout", response_model=AuthStatusResponse)
def logout_session(response: Response):
    """Cierra la sesión familiar eliminando la cookie HttpOnly."""
    response.delete_cookie(key=COOKIE_NAME)
    return AuthStatusResponse(authenticated=False, activeParent="MAMA", pinConfigured=True)


@auth_router.get("/status", response_model=AuthStatusResponse)
def get_auth_status(request: Request):
    """Devuelve si el dispositivo tiene una sesión familiar válida activa."""
    cookie_val = request.cookies.get(COOKIE_NAME)
    parent = verify_session_token(cookie_val)
    return AuthStatusResponse(
        authenticated=parent is not None,
        activeParent=parent or "MAMA",
        pinConfigured=bool(settings.FAMILY_ACCESS_PIN),
    )
