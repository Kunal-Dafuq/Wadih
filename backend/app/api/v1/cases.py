from typing import List
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.screening import ScreeningCaseListItem, ScreeningCaseDetailResponse
from app.services.case_service import CaseService
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/cases", tags=["Synthetic Screening Cases"])


@router.get("", response_model=List[ScreeningCaseListItem])
def list_cases(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List synthetic screening cases accessible to the authenticated user."""
    return CaseService.get_cases_for_user(db, current_user, skip=skip, limit=limit)


@router.get("/{case_id}", response_model=ScreeningCaseDetailResponse)
def get_case(
    case_id: int = Path(..., ge=1, description="Numeric case identifier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and synthetic findings for a specific screening case with strict ownership validation."""
    return CaseService.get_case_detail_for_user(db, case_id, current_user)
