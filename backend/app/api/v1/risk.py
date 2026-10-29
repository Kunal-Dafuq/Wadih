from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.dependencies import get_current_user
from app.core.exceptions import ValidationException
from app.schemas.genetic_risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    CaseRiskAssessmentRequest,
)
from app.services.risk_engine import RiskEngineService

router = APIRouter(prefix="/risk", tags=["Genetic Risk Engine"])


@router.post(
    "/assess",
    response_model=RiskAssessmentResponse,
    summary="Calculate deterministic genetic risk for educational scenario simulation",
)
def assess_genetic_risk(
    request: RiskAssessmentRequest,
    current_user: User = Depends(get_current_user),
):
    """Educational scenario simulator for deterministic Mendelian recurrence probabilities.

    SAFETY & BOUNDARY ENFORCEMENT:
    - This generic endpoint is strictly an educational 'what if' calculator for hypothetical scenarios.
    - Supplying a case_id is strictly rejected to prevent confusing hypothetical simulations with
      authoritative patient screening cases or bypassing case-level clinical provenance checks.
    - Stored case assessments MUST use POST /api/v1/risk/cases/{case_id}/assess, which enforces
      case ownership, partner consent grants, and certified clinical provenance records.
    """
    if request.case_id is not None and str(request.case_id).strip():
        raise ValidationException(
            "The generic /risk/assess endpoint is an educational simulator for hypothetical scenarios "
            "and does not evaluate patient screening cases. For authoritative case-linked screening "
            "assessments, call POST /api/v1/risk/cases/{case_id}/assess."
        )
    return RiskEngineService.assess_risk(request, is_educational_simulation=True)


@router.post(
    "/cases/{case_id}/assess",
    response_model=RiskAssessmentResponse,
    summary="Assess risk for stored cases via validated POST body (recommended & privacy-hardened)",
)
@router.post(
    "/cases/{case_id}",
    response_model=RiskAssessmentResponse,
    summary="Assess risk for stored cases via validated POST body",
)
def assess_risk_from_case_secure(
    case_id: int,
    request: CaseRiskAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate reproductive risk using stored screening findings via POST body.

    PRIVACY & SECURITY ADVANTAGES:
    - Moving clinical inputs (condition code, partner case ID, residual carrier probabilities)
      into the POST request body prevents sensitive health parameters from leaking into web server
      access logs, reverse-proxy logs, browser histories, and network monitoring tools.
    - Enforces clinical provenance: Syntactic numerical validity alone is not accepted as proof
      of an accredited laboratory detection rate. Clinician confirmation is verified.
    - Enforces strict object-level authorization and partner consent grant verification.
    """
    return RiskEngineService.assess_from_cases(
        db=db,
        case_1_id=case_id,
        condition_code=request.condition_code,
        user=current_user,
        partner_case_id=request.partner_case_id,
        partner_residual_carrier_probability=request.partner_residual_carrier_probability,
        residual_risk_source=request.residual_risk_source,
        clinician_confirmed_provenance=request.clinician_confirmed_provenance,
    )


@router.get(
    "/cases/{case_id}",
    response_model=RiskAssessmentResponse,
    summary="Assess risk from stored case (GET legacy endpoint - DEPRECATED due to URL log leakage)",
    deprecated=True,
)
def assess_risk_from_case(
    case_id: int,
    condition_code: str = Query(..., description="Condition code to evaluate (e.g. HBB_BETA_THAL)"),
    partner_case_id: Optional[int] = Query(
        None, description="Optional partner case ID (requires active partner consent grant)"
    ),
    partner_residual_carrier_probability: Optional[float] = Query(
        None,
        description="Validated residual carrier probability for negative-screening partner (0.0 < r < 1.0). DEPRECATED: Use POST body to avoid access log leakage.",
    ),
    clinician_confirmed_provenance: bool = Query(
        False,
        description="Attestation that residual risk was extracted from an accredited clinician-reviewed report",
    ),
    residual_risk_source: Optional[str] = Query(
        None,
        description="Optional laboratory panel and detection rate documentation",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate reproductive risk using stored screening findings.

    NOTE: This GET endpoint is preserved for backward compatibility with frontend clients.
    Callers are advised to migrate to POST /api/v1/risk/cases/{case_id}/assess to prevent
    sensitive clinical identifiers from persisting in HTTP access logs.
    """
    return RiskEngineService.assess_from_cases(
        db=db,
        case_1_id=case_id,
        condition_code=condition_code,
        user=current_user,
        partner_case_id=partner_case_id,
        partner_residual_carrier_probability=partner_residual_carrier_probability,
        residual_risk_source=residual_risk_source,
        clinician_confirmed_provenance=clinician_confirmed_provenance,
    )
