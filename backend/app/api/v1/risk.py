from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user
from app.schemas.genetic_risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services.risk_engine import RiskEngineService

router = APIRouter(prefix="/risk", tags=["Genetic Risk Engine"])


@router.post(
    "/assess",
    response_model=RiskAssessmentResponse,
    summary="Calculate deterministic genetic risk and Mendelian recurrence probabilities",
)
def assess_genetic_risk(
    request: RiskAssessmentRequest,
    current_user: User = Depends(get_current_user),
):
    """Deterministic, testable risk calculation based on versioned Mendelian rules.

    Supports:
    - Autosomal recessive cross-carrier calculations (25% affected, 50% carrier, 25% non-carrier).
    - Single-carrier status with negative or missing partner data.
    - Negative screening scope explanations.
    - Clinical-safety escalation for VUS, inconclusive, or unsupported inheritance modes.
    """
    return RiskEngineService.assess_risk(request)


@router.get(
    "/cases/{case_id}",
    response_model=RiskAssessmentResponse,
    summary="Assess risk for a stored synthetic screening case and optional consented partner case",
)
def assess_risk_from_case(
    case_id: int,
    condition_code: str = Query(..., description="Condition code to evaluate (e.g. HBB_BETA_THAL)"),
    partner_case_id: Optional[int] = Query(
        None, description="Optional partner case ID (requires active partner consent grant)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate reproductive risk using stored screening findings.

    Enforces:
    - Primary case ownership or counsellor assignment.
    - Partner consent verification: partner_case_id access is strictly denied without an approved consent grant.
    """
    return RiskEngineService.assess_from_cases(
        db=db,
        case_1_id=case_id,
        condition_code=condition_code,
        user=current_user,
        partner_case_id=partner_case_id,
    )
