import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.genetic_risk import (
    InheritancePattern,
    ScreeningInterpretation,
    AssessmentStatus,
    RiskAssessmentRequest,
)
from app.services.risk_engine import RiskEngineService
from app.services.inheritance_rules import RULE_VERSION
from app.core.exceptions import ValidationException, ConsentRequiredException
from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope


def test_risk_engine_case_a_both_negative():
    """Case A: Neither partner has a relevant shared finding identified."""
    req = RiskAssessmentRequest(
        condition_code="CFTR_CYSTIC_FIBROSIS",
        condition_name="Cystic Fibrosis",
        gene_symbol="CFTR",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.EDUCATIONAL_RESULT
    assert res.rule_version == RULE_VERSION
    assert res.requires_genetic_counselor is False
    assert res.risk_estimate is not None
    assert res.risk_estimate.affected_probability == 0.0

    # Explicit clinical safety checks
    assert "does not guarantee zero risk" in res.explanation
    assert any("does not guarantee" in lim for lim in res.limitations)


def test_risk_engine_case_b_single_carrier_missing_partner():
    """Case B.1: One partner is carrier, partner result is missing / not performed."""
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=None,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.INSUFFICIENT_DATA
    # Must NOT calculate or imply couple-level risk
    assert res.risk_estimate is None
    assert "couple-level risk calculation cannot be performed" in res.explanation
    assert "carriers are generally healthy" in res.explanation


def test_risk_engine_case_b_single_carrier_confirmed_negative_partner():
    """Case B.2: One partner is carrier, other partner tested negative on panel."""
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.EDUCATIONAL_RESULT
    assert res.risk_estimate is not None
    assert res.risk_estimate.affected_probability == 0.0
    assert res.risk_estimate.carrier_probability == 0.50
    assert res.requires_genetic_counselor is False
    assert "50% chance the child will inherit the carrier copy" in res.explanation
    assert "reduced to the background residual risk" in res.explanation


def test_risk_engine_case_c_dual_carrier_autosomal_recessive():
    """Case C: Both partners are confirmed carriers for the same autosomal recessive condition."""
    req = RiskAssessmentRequest(
        case_id="SYN-DUAL-001",
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.CARRIER_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.EDUCATIONAL_RESULT
    assert res.rule_version == "v1.0.0-ar-deterministic"
    assert res.requires_genetic_counselor is True
    assert res.referral_reason == "DUAL_CARRIER_AUTOSOMAL_RECESSIVE"

    # Conventional per-pregnancy Mendelian distribution
    assert res.risk_estimate is not None
    assert res.risk_estimate.affected_probability == 0.25
    assert res.risk_estimate.carrier_probability == 0.50
    assert res.risk_estimate.unaffected_non_carrier_probability == 0.25

    # Recurrence independence explicit statement
    assert "separate and independent for each pregnancy" in res.explanation
    assert "not a forecast of an individual child's health outcome" in res.explanation


def test_risk_engine_case_d_variant_of_uncertain_significance():
    """Case D: Variant of uncertain significance (VUS) or ambiguous finding."""
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.UNCERTAIN_SIGNIFICANCE,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.REVIEW_REQUIRED
    # Definitive risk estimate must NOT be assigned for uncertain finding
    assert res.risk_estimate is None
    assert res.requires_genetic_counselor is True
    assert res.referral_reason == "VARIANT_OF_UNCERTAIN_SIGNIFICANCE"
    assert "variant of uncertain significance (VUS)" in res.explanation


def test_risk_engine_case_e_unsupported_inheritance_pattern():
    """Case E: Unsupported inheritance pattern (e.g. Autosomal Dominant, X-Linked)."""
    req = RiskAssessmentRequest(
        condition_code="HTT_HUNTINGTON",
        condition_name="Huntington Disease",
        gene_symbol="HTT",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_DOMINANT,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.UNSUPPORTED_INHERITANCE_PATTERN
    assert res.risk_estimate is None
    assert res.requires_genetic_counselor is True
    assert res.referral_reason == "UNSUPPORTED_INHERITANCE_PATTERN"
    assert "is not supported by this deterministic educational model" in res.explanation


def test_risk_engine_guardrails_unreviewed_and_insufficient():
    """Guardrails: Findings that are unreviewed or insufficient are escalated, not guessed."""
    # 1. Unreviewed findings
    req_unreviewed = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.CARRIER_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=False,
    )
    res_unreviewed = RiskEngineService.assess_risk(req_unreviewed)
    assert res_unreviewed.assessment_status == AssessmentStatus.REVIEW_REQUIRED
    assert res_unreviewed.referral_reason == "REPORT_REVIEW_PENDING"

    # 2. Insufficient laboratory data
    req_insufficient = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.CARRIER_DETECTED,
        findings_sufficient=False,
        is_clinician_reviewed=True,
    )
    res_insufficient = RiskEngineService.assess_risk(req_insufficient)
    assert res_insufficient.assessment_status == AssessmentStatus.INSUFFICIENT_DATA
    assert res_insufficient.referral_reason == "LAB_FINDINGS_INSUFFICIENT"


def test_risk_engine_validation_errors():
    """Validation: Empty condition code or condition name must fail cleanly."""
    with pytest.raises(ValidationException):
        RiskEngineService.assess_risk(
            RiskAssessmentRequest(
                condition_code="",
                condition_name="Beta Thalassemia",
                inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
                partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
            )
        )


def test_risk_engine_reproducibility():
    """Stability: Repeated calls with identical input produce identical output."""
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.CARRIER_DETECTED,
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res1 = RiskEngineService.assess_risk(req)
    res2 = RiskEngineService.assess_risk(req)

    assert res1.model_dump() == res2.model_dump()


def test_api_risk_assess_endpoint(client: TestClient, db_session: Session):
    """API Integration: POST /api/v1/risk/assess with valid auth token."""
    seed_database(db_session)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "condition_code": "HBB_BETA_THAL",
        "condition_name": "Beta Thalassemia",
        "gene_symbol": "HBB",
        "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
        "partner_1_finding": "CARRIER_DETECTED",
        "partner_2_finding": "CARRIER_DETECTED",
        "findings_sufficient": True,
        "is_clinician_reviewed": True,
    }
    resp = client.post("/api/v1/risk/assess", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data["risk_estimate"]["affected_probability"] == 0.25
    assert data["rule_version"] == "v1.0.0-ar-deterministic"


def test_api_risk_cases_with_and_without_partner_consent(client: TestClient, db_session: Session):
    """API Integration: GET /api/v1/risk/cases/{case_id} checks partner consent."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Case 1 (Patient A) without partner case: Single carrier assessment
    resp_single = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL",
        headers=headers_a,
    )
    assert resp_single.status_code == 200
    assert resp_single.json()["assessment_status"] == "INSUFFICIENT_DATA"

    # Case 1 with partner Case 2 (Patient B) WITHOUT consent: 403 CONSENT_REQUIRED
    resp_no_consent = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_no_consent.status_code == 403
    assert resp_no_consent.json()["error"]["code"] == "CONSENT_REQUIRED"

    # Patient B grants consent to Patient A
    grant = ConsentGrant(
        granter_user_id=2,  # Patient B
        grantee_user_id=1,  # Patient A
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # Now assess with partner Case 2: Succeeds and calculates joint status
    resp_consented = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_consented.status_code == 200
    assert resp_consented.json()["assessment_status"] == "EDUCATIONAL_RESULT"
