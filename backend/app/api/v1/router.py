from fastapi import APIRouter, Depends
from app.api.v1 import auth
from app.schemas.auth import CurrentUserResponse
from app.models.user import User
from app.api.dependencies import get_current_user

api_router = APIRouter()

# Mount authentication router
api_router.include_router(auth.router)


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
    )
