from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user
from app.services.escalation_service import (
    EscalationService,
    EscalationRequest,
    EscalationResultResponse,
)

router = APIRouter(prefix="/counselling", tags=["Genetic Counselling & Escalations"])


@router.post(
    "/escalations",
    response_model=EscalationResultResponse,
    status_code=201,
    summary="Create clinical escalation to genetic counselling",
)
def create_counselling_escalation(
    request: EscalationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically route ambiguous, VUS, unsupported, or dual-carrier findings to counselling."""
    return EscalationService.create_escalation(
        db=db, user=current_user, request_data=request
    )


@router.get(
    "/escalations/check/{case_id}",
    response_model=List[str],
    summary="Check if a case contains deterministic escalation triggers",
)
def check_case_escalation_triggers(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan case findings and return list of active escalation trigger codes."""
    return EscalationService.evaluate_case_escalation_needs(
        db=db, case_id=case_id, user=current_user
    )
