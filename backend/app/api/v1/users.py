from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserDetailResponse,
    ParticipantProfileResponse,
    ParticipantProfileUpdateRequest,
)
from app.services.user_service import UserService
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users & Profiles"])


@router.get("/me", response_model=UserDetailResponse)
def get_current_user_details(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve authenticated user details and associated participant profile."""
    profile = UserService.get_or_create_profile(db, current_user)
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    return UserDetailResponse(
        id=current_user.id,
        email=current_user.email,
        role=role_str,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        profile=ParticipantProfileResponse.model_validate(profile),
    )


@router.get("/me/profile", response_model=ParticipantProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve authenticated participant profile and communication preferences."""
    profile = UserService.get_or_create_profile(db, current_user)
    return profile


@router.patch("/me/profile", response_model=ParticipantProfileResponse)
def update_my_profile(
    payload: ParticipantProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update communication preferences (display_name, preferred_language, literacy_mode)."""
    updated = UserService.update_profile(db, current_user, payload)
    return updated
