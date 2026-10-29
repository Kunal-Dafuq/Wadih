from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user
from app.schemas.consent import (
    SharingInvitationRequest,
    ConsentGrantResponse,
    SharedCaseSummaryResponse,
)
from app.services.consent_service import ConsentService

router = APIRouter(prefix="/sharing", tags=["Partner Sharing & Privacy Boundaries"])


@router.post(
    "/requests",
    response_model=ConsentGrantResponse,
    status_code=201,
    summary="Create partner sharing invitation request",
)
def create_sharing_request(
    request: SharingInvitationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initiate a partner sharing request.

    SECURITY RULE:
    An invitation request does NOT grant access to genetic data upon creation.
    It creates a PENDING authorization record that requires explicit approval.
    """
    return ConsentService.create_sharing_request(
        db=db, requester=current_user, request_data=request
    )


@router.get(
    "/shared-cases/{case_id}",
    response_model=SharedCaseSummaryResponse,
    summary="Access shared screening case findings under active consent",
)
def get_shared_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve shared screening findings.

    SECURITY ENFORCEMENT:
    - Verifies active GRANTED status from the case owner to the caller.
    - Denies access if revoked, expired, or non-existent (privacy-preserving 404).
    - Filters response content strictly by the granted scope (e.g. carrier_status_only strips summaries).
    """
    return ConsentService.get_shared_case(
        db=db, case_id=case_id, caller=current_user
    )
