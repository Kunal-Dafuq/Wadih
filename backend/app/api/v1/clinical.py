from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.api.dependencies import get_current_user, require_roles
from app.schemas.clinical_record import (
    ClinicalProvenanceCreateRequest,
    ClinicalProvenanceResponse,
)
from app.services.clinical_provenance_service import ClinicalProvenanceService

router = APIRouter(prefix="/clinical", tags=["Clinical Provenance"])


@router.post(
    "/provenance",
    response_model=ClinicalProvenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record verified clinical residual-risk provenance (Clinician/Admin only)",
)
def record_clinical_provenance(
    request: ClinicalProvenanceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COUNSELLOR, UserRole.ADMIN])),
):
    """Record an authoritative, clinician-reviewed residual-risk assessment for a screening case.

    ACCESS RESTRICTIONS:
    - Restricted to COUNSELLOR and ADMIN roles.
    - Ordinary participants cannot create or confirm clinical provenance.
    - Bound to specific case ID, condition code, reviewing clinician, and laboratory detection source.
    """
    return ClinicalProvenanceService.record_provenance(
        db=db,
        clinician=current_user,
        req=request,
    )
