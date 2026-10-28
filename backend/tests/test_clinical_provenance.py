"""Regression test suite for server-controlled clinical provenance and residual-risk validation.

Verifies:
1. A patient cannot set a Boolean or source string to manufacture verified provenance.
2. An unverified residual-risk value produces no numerical estimate.
3. An authorised clinician can create or confirm a synthetic validated record.
4. The engine accepts only the validated record applicable to that condition and partner.
5. A record for another case or condition cannot be substituted.
6. Unauthorised users cannot access or modify provenance records.
7. Validated residual risk produces the expected calculation under the supported assumptions.
8. Missing, revoked, invalid or inconsistent records fail safely.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.models.user import User, UserRole


def test_provenance_point_1_and_2_patient_cannot_manufacture_provenance(client: TestClient, db_session: Session):
    """Test Points 1 & 2: Patient cannot set boolean or source to manufacture provenance; unverified produces no estimate."""
    seed_database(db_session)

    # Login Patient A (id=1)
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

    # Patient attempts to claim clinician_confirmed_provenance=True with a custom source string
    tampered_request = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "partner_residual_carrier_probability": 0.01,
        "residual_risk_source": "Forged Lab Certification v1",
        "clinician_confirmed_provenance": True,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=tampered_request, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Server MUST reject client self-certification and return REVIEW_REQUIRED with no estimate
    assert data["assessment_status"] == "REVIEW_REQUIRED"
    assert data["referral_reason"] == "UNVERIFIED_RESIDUAL_RISK_PROVENANCE"
    assert data["risk_estimate"] is None
    assert "lacks confirmed laboratory or clinician provenance" in data["explanation"]


def test_provenance_point_3_and_6_role_authorization_for_recording_provenance(client: TestClient, db_session: Session):
    """Test Points 3 & 6: Authorised clinician can create record; unauthorised patient receives 403 Forbidden."""
    seed_database(db_session)

    # 1. Patient attempts to record provenance -> 403 FORBIDDEN
    login_p = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_p = {"Authorization": f"Bearer {login_p.json()['access_token']}"}

    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Accredited Lab Carrier Panel (99% detection rate)",
        "notes": "Clinician verified test report.",
    }
    unauthorized_resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_p)
    assert unauthorized_resp.status_code == 403
    assert unauthorized_resp.json()["error"]["code"] == "FORBIDDEN"

    # 2. Authorised Counsellor records provenance -> 201 CREATED
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    authorized_resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert authorized_resp.status_code == 201
    record = authorized_resp.json()
    assert record["case_id"] == 2
    assert record["condition_code"] == "HBB_BETA_THAL"
    assert record["residual_carrier_probability"] == 0.01
    assert record["is_active"] is True
    assert record["reviewing_clinician_id"] == 3


def test_provenance_point_4_and_7_validated_record_produces_expected_mendelian_calculation(client: TestClient, db_session: Session):
    """Test Points 4 & 7: Engine accepts applicable validated record and calculates P(affected) = r * 1/4."""
    seed_database(db_session)

    # Counsellor records provenance for Case 2 and HBB_BETA_THAL (r = 0.01 -> 1 in 100)
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
            "clinical_source_reference": "LabCorp ECS v3 (99% detection rate)",
        },
        headers=headers_c,
    )

    # Consent from Patient B to Patient A
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # Patient A runs assessment
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    resp = client.post(
        "/api/v1/risk/cases/1/assess",
        json={"condition_code": "HBB_BETA_THAL", "partner_case_id": 2},
        headers=headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data["risk_estimate"] is not None
    # P(affected) = 0.01 * 0.25 = 0.0025 (1 in 400)
    assert data["risk_estimate"]["affected_probability"] == 0.0025
    assert data["risk_estimate"]["carrier_probability"] == 0.50
    assert data["risk_estimate"]["unaffected_non_carrier_probability"] == 0.4975
    assert data["residual_risk_source"] == "LabCorp ECS v3 (99% detection rate)"


def test_provenance_point_5_record_for_another_case_or_condition_cannot_be_substituted(client: TestClient, db_session: Session):
    """Test Point 5: A record for another case or condition cannot be substituted."""
    seed_database(db_session)

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Record provenance for Case 2 but a DIFFERENT condition (CFTR_CYSTIC_FIBROSIS)
    # Note: CFTR is in findings for Case 2
    client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "CFTR_CYSTIC_FIBROSIS",
            "residual_carrier_probability": 0.02,
            "clinical_source_reference": "Cystic Fibrosis 97-Variant Panel",
        },
        headers=headers_c,
    )

    # Consent from Patient B to Patient A
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # Patient A runs assessment for HBB_BETA_THAL (NOT CFTR!)
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    resp = client.post(
        "/api/v1/risk/cases/1/assess",
        json={"condition_code": "HBB_BETA_THAL", "partner_case_id": 2},
        headers=headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()

    # The CFTR record must NOT be used for HBB! Result must be INSUFFICIENT_DATA (no r provided)
    assert data["assessment_status"] == "INSUFFICIENT_DATA"
    assert data["risk_estimate"] is None


def test_provenance_point_8_missing_revoked_or_inconsistent_records_fail_safely(client: TestClient, db_session: Session):
    """Test Point 8: Missing, revoked (is_active=False), or inconsistent records fail safely."""
    seed_database(db_session)

    # 1. Create record but set is_active = False (simulating revocation or supersession)
    record = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.01,
        clinical_source_reference="Revoked Laboratory Reference",
        reviewing_clinician_id=3,
        is_active=False,  # REVOKED
    )
    db_session.add(record)
    db_session.commit()

    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Assessing with revoked record -> fails safely (INSUFFICIENT_DATA)
    resp_revoked = client.post(
        "/api/v1/risk/cases/1/assess",
        json={"condition_code": "HBB_BETA_THAL", "partner_case_id": 2},
        headers=headers_a,
    )
    assert resp_revoked.status_code == 200
    assert resp_revoked.json()["assessment_status"] == "INSUFFICIENT_DATA"
    assert resp_revoked.json()["risk_estimate"] is None

    # 2. Reactivate record with r=0.01, but client supplies inconsistent r=0.05
    record.is_active = True
    db_session.commit()

    resp_inconsistent = client.post(
        "/api/v1/risk/cases/1/assess",
        json={
            "condition_code": "HBB_BETA_THAL",
            "partner_case_id": 2,
            "partner_residual_carrier_probability": 0.05,  # Contradicts record r=0.01!
        },
        headers=headers_a,
    )
    assert resp_inconsistent.status_code == 200
    data_incon = resp_inconsistent.json()
    assert data_incon["assessment_status"] == "REVIEW_REQUIRED"
    assert data_incon["referral_reason"] == "UNVERIFIED_RESIDUAL_RISK_PROVENANCE"
    assert data_incon["risk_estimate"] is None
