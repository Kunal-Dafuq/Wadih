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


def test_risk_engine_case_a_both_negative_no_zero_risk_claim():
    """Case A: Neither partner has a relevant shared finding identified.

    Clinical Safety Guarantee: A negative carrier screen reduces risk significantly,
    but does NOT eliminate it. Numerical probability must NOT be reported as 0.0.
    """
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
    # Clinical Safety: Numerical zero-risk probability is NOT assigned
    assert res.risk_estimate is None

    # Explicit clinical safety checks in explanation and limitations
    assert "does not guarantee zero risk" in res.explanation
    assert "does not assign a zero-risk numerical probability" in res.explanation
    assert any("does not guarantee" in lim for lim in res.limitations)
    assert any("No numerical zero-risk probability is assigned" in lim for lim in res.limitations)


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


def test_risk_engine_case_b_single_carrier_negative_partner_without_residual_risk():
    """Case B.2a: One partner is carrier, other tested negative, but residual risk is unavailable.

    Clinical Safety: When validated laboratory residual carrier probability (r) is unavailable,
    the engine MUST NOT invent default numbers. It returns INSUFFICIENT_DATA with risk_estimate=None.
    """
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        partner_2_residual_carrier_probability=None,  # Not provided
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.INSUFFICIENT_DATA
    # Safety: No fabricated numerical probabilities
    assert res.risk_estimate is None
    assert "residual carrier probability (r)" in res.explanation
    assert "P(affected child) = r × 1/4" in res.explanation
    assert "couple-level numerical risk cannot be calculated" in res.explanation


def test_risk_engine_case_b_single_carrier_negative_partner_with_validated_residual_risk():
    """Case B.2b: One partner is carrier, other tested negative WITH validated residual risk r = 0.01 (1 in 100).

    Mathematical Relationship:
    Under Mendelian model: P(affected child per pregnancy) = r × 1/4 = 0.01 × 0.25 = 0.0025 (1 in 400).
    Carrier probability = 50.00%.
    Unaffected non-carrier = 0.50 - 0.25 * r = 0.4975.
    """
    req = RiskAssessmentRequest(
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        gene_symbol="HBB",
        inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
        partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
        partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
        partner_2_residual_carrier_probability=0.01,  # 1 in 100 validated residual carrier probability
        findings_sufficient=True,
        is_clinician_reviewed=True,
    )
    res = RiskEngineService.assess_risk(req)

    assert res.assessment_status == AssessmentStatus.EDUCATIONAL_RESULT
    assert res.risk_estimate is not None
    assert res.risk_estimate.residual_carrier_probability_used == 0.01
    assert res.risk_estimate.affected_probability == 0.0025  # exactly r * 0.25
    assert res.risk_estimate.carrier_probability == 0.50
    assert res.risk_estimate.unaffected_non_carrier_probability == 0.4975
    assert res.requires_genetic_counselor is False
    assert "P(affected child) = r × 1/4 = 0.2500%" in res.explanation
    assert "approx. 1 in 400" in res.explanation


def test_risk_engine_residual_risk_mathematical_consistency():
    """Verify mathematical relationship P(affected) = r × 1/4 across multiple validated r values."""
    test_cases = [
        (0.04, 0.0100),   # r = 1/25  -> affected = 1/100 (0.01)
        (0.02, 0.0050),   # r = 1/50  -> affected = 1/200 (0.005)
        (0.008, 0.0020),  # r = 1/125 -> affected = 1/500 (0.002)
        (0.001, 0.00025), # r = 1/1000-> affected = 1/4000 (0.00025)
    ]

    for r_val, expected_affected in test_cases:
        req = RiskAssessmentRequest(
            condition_code="CFTR_CYSTIC_FIBROSIS",
            condition_name="Cystic Fibrosis",
            gene_symbol="CFTR",
            inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
            partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
            partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
            partner_2_residual_carrier_probability=r_val,
            findings_sufficient=True,
            is_clinician_reviewed=True,
        )
        res = RiskEngineService.assess_risk(req)
        assert res.assessment_status == AssessmentStatus.EDUCATIONAL_RESULT
        assert res.risk_estimate is not None
        assert abs(res.risk_estimate.affected_probability - expected_affected) < 1e-6
        assert res.risk_estimate.carrier_probability == 0.50
        expected_non_carrier = round(0.50 - 0.25 * r_val, 6)
        assert abs(res.risk_estimate.unaffected_non_carrier_probability - expected_non_carrier) < 1e-6


def test_risk_engine_residual_risk_boundary_and_invalid_values():
    """Boundary values: r <= 0.0 or r >= 1.0 must be rejected with ValidationException."""
    invalid_r_values = [-0.05, 0.0, 1.0, 1.05]

    for bad_r in invalid_r_values:
        with pytest.raises(ValidationException):
            RiskEngineService.assess_risk(
                RiskAssessmentRequest(
                    condition_code="HBB_BETA_THAL",
                    condition_name="Beta Thalassemia",
                    inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
                    partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
                    partner_2_finding=ScreeningInterpretation.NO_VARIANT_DETECTED,
                    partner_2_residual_carrier_probability=bad_r,
                )
            )


def test_risk_engine_residual_risk_inappropriate_partner_state():
    """Safety: Providing residual carrier risk for a partner who is CARRIER_DETECTED must be rejected."""
    with pytest.raises(ValidationException):
        RiskEngineService.assess_risk(
            RiskAssessmentRequest(
                condition_code="HBB_BETA_THAL",
                condition_name="Beta Thalassemia",
                inheritance_pattern=InheritancePattern.AUTOSOMAL_RECESSIVE,
                partner_1_finding=ScreeningInterpretation.CARRIER_DETECTED,
                partner_2_finding=ScreeningInterpretation.CARRIER_DETECTED,
                partner_2_residual_carrier_probability=0.01,  # Inappropriate for confirmed carrier
            )
        )


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
    assert res_unreviewed.risk_estimate is None

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
    assert res_insufficient.risk_estimate is None


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


def test_api_risk_assess_endpoint_with_residual_risk(client: TestClient, db_session: Session):
    """API Integration: POST /api/v1/risk/assess with residual carrier probability."""
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
        "partner_2_finding": "NO_VARIANT_DETECTED",
        "partner_2_residual_carrier_probability": 0.01,
        "findings_sufficient": True,
        "is_clinician_reviewed": True,
    }
    resp = client.post("/api/v1/risk/assess", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data["risk_estimate"]["affected_probability"] == 0.0025
    assert data["risk_estimate"]["residual_carrier_probability_used"] == 0.01


def test_api_risk_cases_with_and_without_partner_consent(client: TestClient, db_session: Session):
    """API Integration: GET /api/v1/risk/cases/{case_id} checks partner consent and accepts residual risk."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Case 1 (Patient A) without partner case: Single carrier assessment (untested partner -> INSUFFICIENT_DATA)
    resp_single = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL",
        headers=headers_a,
    )
    assert resp_single.status_code == 200
    assert resp_single.json()["assessment_status"] == "INSUFFICIENT_DATA"
    assert resp_single.json()["risk_estimate"] is None

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

    # Now assess with partner Case 2 without residual risk: INSUFFICIENT_DATA with risk_estimate=None
    resp_consented_no_r = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_consented_no_r.status_code == 200
    assert resp_consented_no_r.json()["assessment_status"] == "INSUFFICIENT_DATA"
    assert resp_consented_no_r.json()["risk_estimate"] is None

    # Now assess with partner Case 2 WITH residual risk r = 0.01 BUT unconfirmed provenance -> REVIEW_REQUIRED
    resp_consented_unprovenanced = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2&partner_residual_carrier_probability=0.01",
        headers=headers_a,
    )
    assert resp_consented_unprovenanced.status_code == 200
    data_unprov = resp_consented_unprovenanced.json()
    assert data_unprov["assessment_status"] == "REVIEW_REQUIRED"
    assert data_unprov["referral_reason"] == "UNVERIFIED_RESIDUAL_RISK_PROVENANCE"
    assert data_unprov["risk_estimate"] is None

    # Counsellor logs in and records authoritative clinical provenance in the database for Case 2
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}
    client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Accredited Lab Carrier Panel (99% detection rate)",
            "notes": "Verified against clinician-reviewed synthetic laboratory report.",
        },
        headers=headers_c,
    )

    # Now assess with partner Case 2 with server-verified clinician provenance:
    resp_consented_with_r = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_consented_with_r.status_code == 200
    data_with_r = resp_consented_with_r.json()
    assert data_with_r["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data_with_r["risk_estimate"]["affected_probability"] == 0.0025


def test_secure_post_risk_assessment_endpoint_and_provenance(client: TestClient, db_session: Session):
    """API Security: Moving risk inputs to POST body prevents URL log leakage and enforces server-controlled provenance."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Grant consent from Patient B to Patient A
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # 1. Patient attempts to self-certify provenance via POST body without server record -> REVIEW_REQUIRED
    post_unprov_payload = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "partner_residual_carrier_probability": 0.01,
        "residual_risk_source": "Patient-Claimed Source",
        "clinician_confirmed_provenance": True,  # Client tries to claim true!
    }
    resp_post_unprov = client.post(
        "/api/v1/risk/cases/1/assess",
        json=post_unprov_payload,
        headers=headers_a,
    )
    assert resp_post_unprov.status_code == 200
    res_unprov = resp_post_unprov.json()
    assert res_unprov["assessment_status"] == "REVIEW_REQUIRED"
    assert res_unprov["referral_reason"] == "UNVERIFIED_RESIDUAL_RISK_PROVENANCE"
    assert res_unprov["risk_estimate"] is None

    # 2. Authorised Counsellor creates persisted clinical provenance record
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}
    prov_resp = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Accredited Lab Carrier Panel (99% detection rate)",
        },
        headers=headers_c,
    )
    assert prov_resp.status_code == 201

    # 3. Now assess via POST body with server-verified provenance -> EDUCATIONAL_RESULT with 0.0025
    post_prov_payload = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
    }
    resp_post_prov = client.post(
        "/api/v1/risk/cases/1/assess",
        json=post_prov_payload,
        headers=headers_a,
    )
    assert resp_post_prov.status_code == 200
    res_prov = resp_post_prov.json()
    assert res_prov["assessment_status"] == "EDUCATIONAL_RESULT"
    assert res_prov["risk_estimate"]["affected_probability"] == 0.0025
    assert res_prov["residual_risk_source"] == "Accredited Lab Carrier Panel (99% detection rate)"
    assert any("Accredited Lab Carrier Panel" in a for a in res_prov["assumptions"])


