from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.education import (
    CaseExplanationResponse,
    KnowledgeCheckSubmission,
    KnowledgeCheckResultResponse,
)
from app.services.education_service import EducationService
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/cases/{case_id}", tags=["Educational Content & Comprehension"])


@router.get("/explanation", response_model=CaseExplanationResponse)
def get_case_explanation(
    case_id: int = Path(..., ge=1, description="Numeric case identifier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve reviewed educational explanation and teach-back questions for the case."""
    return EducationService.get_case_explanation(db, case_id, current_user)


@router.post("/knowledge-check", response_model=KnowledgeCheckResultResponse)
def submit_knowledge_check(
    submission: KnowledgeCheckSubmission,
    case_id: int = Path(..., ge=1, description="Numeric case identifier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit comprehension check answers for evaluation and record assessment attempt."""
    return EducationService.evaluate_knowledge_check(db, case_id, current_user, submission)
