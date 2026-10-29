from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    DemoSessionRequest,
    TokenResponse,
    CurrentUserResponse,
    LogoutResponse,
)
from app.services.auth_service import AuthService
from app.core.rate_limit import check_demo_session_rate_limit
from app.api.dependencies import get_current_user, get_token_from_header

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/demo-session", response_model=TokenResponse)
def create_demo_session(
    request: Request,
    payload: DemoSessionRequest,
    db: Session = Depends(get_db),
):
    """Launch a safe, least-privilege synthetic demonstration session for evaluators."""
    check_demo_session_rate_limit(request)
    user = AuthService.authenticate_demo_persona(db, payload.persona)
    return AuthService.create_token_for_user(user, is_demo=True, demo_persona=payload.persona)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate demo participant or counsellor with email and password."""
    user = AuthService.authenticate_user(db, payload.email, payload.password)
    return AuthService.create_token_for_user(user)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    token: str = Depends(get_token_from_header),
    current_user: User = Depends(get_current_user),
):
    """Server-side session invalidation / token blacklisting."""
    AuthService.logout_token(token)
    return LogoutResponse(message="Successfully logged out.")


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Return identity and preferences for the currently authenticated user."""
    display_name = (
        current_user.profile.display_name
        if current_user.profile
        else current_user.email.split("@")[0]
    )
    pref_lang = current_user.profile.preferred_language if current_user.profile else "en"
    lit_mode = current_user.profile.literacy_mode if current_user.profile else "standard"

    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        role=role_str,
        is_active=current_user.is_active,
        display_name=display_name,
        preferred_language=pref_lang,
        literacy_mode=lit_mode,
        is_demo_session=getattr(current_user, "is_demo_session", False),
        token_scope=getattr(current_user, "token_scope", "standard"),
    )
