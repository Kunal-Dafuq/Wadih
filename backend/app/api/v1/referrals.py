from typing import List
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.referral import (
    ReferralTaskCreateRequest,
    ReferralTaskResponse,
    ReferralStatusUpdateRequest,
    CounsellorNoteCreateRequest,
    CounsellorNoteResponse,
)
from app.services.referral_service import ReferralService
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/referrals", tags=["Simulated Referral Navigation"])


@router.post("", response_model=ReferralTaskResponse, status_code=201)
def create_referral(
    payload: ReferralTaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate a simulated referral navigation task for carrier counselling."""
    return ReferralService.create_referral_task(db, current_user, payload)


@router.get("", response_model=List[ReferralTaskResponse])
def list_referrals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List referral tasks owned by the participant or assigned to the counsellor."""
    return ReferralService.get_referrals_for_user(db, current_user, skip=skip, limit=limit)


@router.get("/{referral_id}", response_model=ReferralTaskResponse)
def get_referral(
    referral_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and counsellor notes for a specific referral task."""
    return ReferralService.get_referral_by_id(db, referral_id, current_user)


@router.patch("/{referral_id}/status", response_model=ReferralTaskResponse)
def update_referral_status(
    payload: ReferralStatusUpdateRequest,
    referral_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update referral state (counsellor or participant cancellation)."""
    return ReferralService.update_referral_status(db, referral_id, current_user, payload)


@router.post("/{referral_id}/notes", response_model=CounsellorNoteResponse, status_code=201)
def add_counsellor_note(
    payload: CounsellorNoteCreateRequest,
    referral_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a counsellor note (restricted to assigned genetic counsellor)."""
    return ReferralService.add_note_to_referral(db, referral_id, current_user, payload)
