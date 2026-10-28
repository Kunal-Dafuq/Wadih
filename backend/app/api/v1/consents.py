from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user
from app.schemas.consent import (
    ConsentGrantCreateRequest,
    ConsentGrantResponse,
)
from app.services.consent_service import ConsentService

router = APIRouter(prefix="/consents", tags=["Consent Management"])


@router.post(
    "",
    response_model=ConsentGrantResponse,
    status_code=201,
    summary="Create a new scoped consent grant",
)
def create_consent_grant(
    request: ConsentGrantCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant scoped disclosure permissions (carrier_status_only, summary_only, full_report) to another user."""
    return ConsentService.create_consent_grant(
        db=db, granter=current_user, request_data=request
    )


@router.get(
    "",
    response_model=List[ConsentGrantResponse],
    summary="List consent grants involving the authenticated user",
)
def list_consents(
    as_granter: bool = Query(True, description="Include consents where caller is granter"),
    as_grantee: bool = Query(True, description="Include consents where caller is recipient"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all active, pending, or revoked consent records involving the caller."""
    return ConsentService.get_consents_for_user(
        db=db, user=current_user, as_granter=as_granter, as_grantee=as_grantee
    )


@router.get(
    "/{consent_id}",
    response_model=ConsentGrantResponse,
    summary="Get consent grant details",
)
def get_consent_detail(
    consent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inspect consent details. Restricted to the granter or grantee."""
    return ConsentService.get_consent_detail(
        db=db, consent_id=consent_id, user=current_user
    )


@router.post(
    "/{consent_id}/approve",
    response_model=ConsentGrantResponse,
    summary="Approve a pending consent grant",
)
def approve_consent(
    consent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending consent request. Only the granting participant may approve."""
    return ConsentService.approve_consent(
        db=db, consent_id=consent_id, user=current_user
    )


@router.post(
    "/{consent_id}/revoke",
    response_model=ConsentGrantResponse,
    summary="Revoke an existing consent grant",
)
def revoke_consent(
    consent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Immediately revoke consent. Blocks all subsequent platform access covered by this grant."""
    return ConsentService.revoke_consent(
        db=db, consent_id=consent_id, user=current_user
    )
