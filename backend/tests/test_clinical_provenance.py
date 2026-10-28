"""Regression test suite for server-controlled clinical provenance, case-level authorization, and residual-risk validation.

Verifies:
1. An assigned counsellor can record provenance for an authorized case.
2. An unassigned counsellor cannot record provenance for another person's case.
3. A counsellor assigned to one partner's referral can access the other partner's case only when the existing model explicitly authorizes that couple-level relationship.
4. A patient cannot record provenance.
5. An administrator follows the established administrative policy.
6. Missing or ambiguous assignments fail closed (revoked, expired, pending, mismatched case, cancelled referral).
7. Denied attempts are audited without exposing raw genetic data.
8. Existing valid risk calculations continue to work after authorized provenance is recorded.
"""

import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.models.referral import ReferralTask, ReferralStatus
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.core.security import hash_password


def test_regression_point_1_assigned_counsellor_can_record_provenance_for_authorized_case(
    client: TestClient, db_session: Session
):
    """1. An assigned counsellor can record provenance for an authorized case."""
    seed_database(db_session)

    # In seed_demo: Counsellor (id=3) has referral_a for Case 1 (Patient A)
    # Case 1 has a negative screening finding for CFTR_CYSTIC_FIBROSIS
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    payload = {
        "case_id": 1,
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "residual_carrier_probability": 0.02,
        "clinical_source_reference": "LabCorp CF 97-Variant Carrier Panel",
        "notes": "Verified by assigned counsellor for routine preconception consult.",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_id"] == 1
    assert data["condition_code"] == "CFTR_CYSTIC_FIBROSIS"
    assert data["residual_carrier_probability"] == 0.02
    assert data["reviewing_clinician_id"] == 3
    assert data["is_active"] is True


def test_regression_point_2_unassigned_counsellor_cannot_record_provenance(
    client: TestClient, db_session: Session
):
    """2. An unassigned counsellor cannot record provenance for another person's case."""
    seed_database(db_session)

    # Create a secondary counsellor with NO assigned referrals
    unassigned_counsellor = User(
        email="unassigned.counsellor@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.COUNSELLOR,
        is_active=True,
    )
    db_session.add(unassigned_counsellor)
    db_session.commit()

    login_u = client.post(
        "/api/v1/auth/login",
        json={"email": "unassigned.counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_u = {"Authorization": f"Bearer {login_u.json()['access_token']}"}

    # Attempt to record provenance for Case 1 (assigned to Counsellor 1, NOT unassigned counsellor)
    payload = {
        "case_id": 1,
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "residual_carrier_probability": 0.02,
        "clinical_source_reference": "Unauthorized External Source",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_u)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert "not authorized to record clinical provenance" in resp.json()["error"]["message"]


def test_regression_point_3_couple_referral_relationship_authorization(
    client: TestClient, db_session: Session
):
    """3. A counsellor assigned to one partner's referral can access the other partner's case
    only when the existing model explicitly authorizes that couple-level relationship.
    """
    seed_database(db_session)

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    payload = {
        "case_id": 2,  # Owned by Patient B
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Accredited Lab Beta Thal Panel",
    }

    # Step A: Counsellor is assigned to Patient A's referral, but Patient B has NOT granted consent yet -> 403
    resp_unauthorized = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert resp_unauthorized.status_code == 403
    assert resp_unauthorized.json()["error"]["code"] == "FORBIDDEN"

    # Step B: Patient B grants active preconception screening consent to Patient A
    grant = ConsentGrant(
        granter_user_id=2,  # Patient B
        grantee_user_id=1,  # Patient A
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # Step C: Counsellor re-attempts -> couple-level referral relationship is now established -> 201 CREATED
    resp_authorized = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert resp_authorized.status_code == 201
    assert resp_authorized.json()["case_id"] == 2
    assert resp_authorized.json()["condition_code"] == "HBB_BETA_THAL"


def test_regression_point_4_patient_cannot_record_provenance(
    client: TestClient, db_session: Session
):
    """4. A patient cannot record provenance."""
    seed_database(db_session)

    login_p = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_p = {"Authorization": f"Bearer {login_p.json()['access_token']}"}

    payload = {
        "case_id": 1,
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Self-submitted patient claim",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_p)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_regression_point_5_admin_follows_administrative_policy(
    client: TestClient, db_session: Session
):
    """5. An administrator follows the established administrative policy."""
    seed_database(db_session)

    # Create admin user
    admin_user = User(
        email="admin@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    login_adm = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_adm = {"Authorization": f"Bearer {login_adm.json()['access_token']}"}

    # Admin records clinical provenance for Case 2
    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Clinical QA Central Ingestion Panel",
        "notes": "Admin operational data ingestion.",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_adm)
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_id"] == 2
    assert data["reviewing_clinician_id"] == admin_user.id


def test_regression_point_6_missing_or_ambiguous_assignments_fail_closed(
    client: TestClient, db_session: Session
):
    """6. Missing or ambiguous assignments fail closed."""
    seed_database(db_session)

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # A. Non-existent case -> 404
    resp_404 = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 9999,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_404.status_code == 404

    # B. Revoked consent grant -> fails closed (403)
    revoked_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.REVOKED.value,
        revoked_at=datetime.now(timezone.utc),
        purpose="preconception_carrier_screening",
    )
    db_session.add(revoked_grant)
    db_session.commit()

    resp_revoked = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_revoked.status_code == 403

    # C. Expired consent grant -> fails closed (403)
    db_session.delete(revoked_grant)
    expired_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Yesterday
        purpose="preconception_carrier_screening",
    )
    db_session.add(expired_grant)
    db_session.commit()

    resp_expired = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_expired.status_code == 403

    # D. Pending consent grant -> fails closed (403)
    db_session.delete(expired_grant)
    pending_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.PENDING.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(pending_grant)
    db_session.commit()

    resp_pending = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_pending.status_code == 403

    # E. Consent grant tied to a DIFFERENT case_id -> fails closed (403)
    db_session.delete(pending_grant)
    different_case_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        case_id=8888,  # Different case
        purpose="preconception_carrier_screening",
    )
    db_session.add(different_case_grant)
    db_session.commit()

    resp_different_case = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_different_case.status_code == 403

    # F. Counsellor referral is CANCELLED -> fails closed (403)
    db_session.delete(different_case_grant)
    valid_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(valid_grant)
    # Cancel the referral for Patient A
    ref_a = db_session.query(ReferralTask).filter(ReferralTask.participant_user_id == 1).first()
    ref_a.status = ReferralStatus.CANCELLED
    db_session.commit()

    resp_cancelled_ref = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 2,
            "condition_code": "HBB_BETA_THAL",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Valid Source",
        },
        headers=headers_c,
    )
    assert resp_cancelled_ref.status_code == 403


def test_regression_point_7_denied_attempts_are_audited_without_raw_genetic_data(
    client: TestClient, db_session: Session
):
    """7. Denied attempts are audited without exposing raw genetic data."""
    seed_database(db_session)

    # Secondary unassigned counsellor attempts access
    unassigned_counsellor = User(
        email="unassigned.counsellor@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.COUNSELLOR,
        is_active=True,
    )
    db_session.add(unassigned_counsellor)
    db_session.commit()

    login_u = client.post(
        "/api/v1/auth/login",
        json={"email": "unassigned.counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_u = {"Authorization": f"Bearer {login_u.json()['access_token']}"}

    client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 1,
            "condition_code": "CFTR_CYSTIC_FIBROSIS",
            "residual_carrier_probability": 0.02,
            "clinical_source_reference": "Valid Lab",
        },
        headers=headers_u,
    )

    # Verify audit entry
    denied_audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "UNAUTHORIZED_PROVENANCE_ATTEMPT",
            AuditLog.actor_user_id == unassigned_counsellor.id,
            AuditLog.outcome == "DENIED",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert denied_audit is not None
    assert denied_audit.resource_type == "clinical_provenance"
    assert denied_audit.resource_id == "1"

    # CRITICAL: Verify details does NOT contain raw sequences, coordinates, or clinical findings
    raw_details = denied_audit.details or {}
    details = json.loads(raw_details) if isinstance(raw_details, str) else raw_details
    assert "sequence" not in str(details).lower()
    assert "genotype" not in str(details).lower()
    assert "variant" not in str(details).lower()
    assert "cftr" not in str(details).lower()
    assert details.get("case_id") == 1
    assert "not assigned" in details.get("reason", "")


def test_regression_point_8_existing_valid_risk_calculations_continue_to_work(
    client: TestClient, db_session: Session
):
    """8. Existing valid risk calculations continue to work after authorized provenance is recorded."""
    seed_database(db_session)

    # Couple-level consent from Patient B to Patient A
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    # Authorized counsellor (assigned to Patient A referral) records provenance for Case 2
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
            "clinical_source_reference": "LabCorp ECS v3 (99% detection rate)",
        },
        headers=headers_c,
    )
    assert prov_resp.status_code == 201

    # Patient A runs assessment
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 1. Via secure POST endpoint
    resp_post = client.post(
        "/api/v1/risk/cases/1/assess",
        json={"condition_code": "HBB_BETA_THAL", "partner_case_id": 2},
        headers=headers_a,
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data_post["risk_estimate"]["affected_probability"] == 0.0025

    # 2. Via GET endpoint (backward compatibility)
    resp_get = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data_get["risk_estimate"]["affected_probability"] == 0.0025
