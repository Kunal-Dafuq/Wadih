from fastapi import APIRouter, Depends
from app.api.v1 import (
    auth,
    users,
    cases,
    education,
    referrals,
    risk,
    consents,
    sharing,
    audit,
    counselling,
    clinical,
)
from app.schemas.auth import CurrentUserResponse
from app.models.user import User
from app.api.dependencies import get_current_user

api_router = APIRouter()

# Foundational modular routers (Kunal)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(cases.router)
api_router.include_router(education.router)
api_router.include_router(referrals.router)

# Advanced backend modular routers (Niharika)
api_router.include_router(risk.router)
api_router.include_router(consents.router)
api_router.include_router(sharing.router)
api_router.include_router(audit.router)
api_router.include_router(counselling.router)
api_router.include_router(clinical.router)


@api_router.get("/me", response_model=CurrentUserResponse, tags=["Authentication"])
def get_me(current_user: User = Depends(get_current_user)):
    """Top-level /api/v1/me shortcut for authenticated participant information."""
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
