from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.api.dependencies import get_current_user, require_roles
from app.schemas.audit import AuditEventListResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Security Audit Trail"])


@router.get(
    "/events",
    response_model=AuditEventListResponse,
    summary="List security audit events (Admin or Counsellor role required)",
)
def list_audit_events(
    action: Optional[str] = Query(None, description="Filter by event action (e.g. CONSENT_REVOKED)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve immutable audit events.

    PRIVILEGE ENFORCEMENT:
    Restricted to ADMIN and COUNSELLOR roles. Normal participants receive 403 Forbidden.
    All events exclude raw genetic variant sequences and authentication credentials.
    """
    return AuditService.get_audit_events(
        db=db,
        current_user=current_user,
        action_filter=action,
        resource_type_filter=resource_type,
        skip=skip,
        limit=limit,
    )
