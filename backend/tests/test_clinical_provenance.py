"""Regression test suite for server-controlled clinical provenance, case-level authorization, and residual-risk validation.

Verifies:
1. A counsellor can create provenance for an explicitly assigned case.
2. A referral for Case A cannot authorize an unrelated Case B owned by the same participant.
3. An unscoped consent grant (case_id=None) cannot authorize arbitrary case access.
4. Consent for Case A cannot authorize Case B unless a separately defined and valid permission explicitly covers Case B.
5. A valid couple-level authorization works for the cases and purpose it explicitly covers.
6. Non-reproductive or unauthorized purposes on consent grants fail closed.
7. Expired, revoked, pending, cancelled, and incorrectly scoped permissions fail closed.
8. Unassigned counsellors and patients are strictly forbidden.
9. Administrators follow the established operational policy.
10. Denied attempts are audited without exposing raw genetic data.
11. Existing valid risk calculations continue to work after authorized provenance creation.
"""

import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.referral import ReferralTask, ReferralStatus
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.core.security import hash_password


def test_1_counsellor_can_create_provenance_for_explicitly_assigned_case(
    client: TestClient, db_session: Session
):
    """1. A counsellor can create provenance for an explicitly assigned case."""
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


def test_2_referral_for_case_a_cannot_authorize_unrelated_case_b_same_participant(
    client: TestClient, db_session: Session
):
    """2. A referral assigned for Case A must NOT automatically authorize provenance creation
    for an unrelated Case B owned by the same participant.
    """
    seed_database(db_session)

    # Patient A (id=1) already has Case 1 (which has an assigned referral to Counsellor 3).
    # Create an unrelated second case (Case 3) for Patient A with NO referral.
    case_3 = ScreeningCase(
        owner_user_id=1,
        synthetic_case_code="SYN-CASE-103-UNRELATED",
        status="ready",
        screening_scope_label="Unrelated Historical Screen",
        source_reviewed=True,
    )
    db_session.add(case_3)
    db_session.flush()

    finding_3 = SyntheticFinding(
        case_id=case_3.id,
        condition_code="CFTR_CYSTIC_FIBROSIS",
        condition_name="Cystic Fibrosis",
        carrier_state="NO_VARIANT_DETECTED",
        inheritance_mode="AUTOSOMAL_RECESSIVE",
        classification_state="NEGATIVE_SCREEN",
        reviewed_flag=True,
        summary_text="Negative historical screen.",
    )
    db_session.add(finding_3)
    db_session.commit()

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Attempt to record provenance for Case 3 (unrelated case owned by same participant)
    payload = {
        "case_id": case_3.id,
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "residual_carrier_probability": 0.02,
        "clinical_source_reference": "LabCorp CF 97-Variant Carrier Panel",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    # MUST FAIL CLOSED: Counsellor is assigned to Case 1, NOT Case 3
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert "not authorized to record clinical provenance" in resp.json()["error"]["message"]


def test_3_unscoped_consent_grant_cannot_authorize_arbitrary_case_access(
    client: TestClient, db_session: Session
):
    """3. An unscoped consent grant (case_id=None) must NOT automatically authorize access
    to screening cases. Exact target-case binding is required.
    """
    seed_database(db_session)

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Patient B grants an UNSCOPED consent grant (case_id=None) to Patient A
    unscoped_grant = ConsentGrant(
        granter_user_id=2,  # Patient B
        grantee_user_id=1,  # Patient A
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=None,  # UNSCOPED / BLANKET
    )
    db_session.add(unscoped_grant)
    db_session.commit()

    payload = {
        "case_id": 2,  # Case owned by Patient B
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Accredited Lab Beta Thal Panel",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    # MUST FAIL CLOSED: Unscoped grant does not explicitly authorize Case 2
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_4_consent_for_case_a_cannot_authorize_case_b(
    client: TestClient, db_session: Session
):
    """4. Consent for Case A cannot authorize Case B unless a separately defined and valid
    permission explicitly covers Case B.
    """
    seed_database(db_session)

    # Patient B owns Case 2 (Beta Thal) and an unrelated second case Case 4
    case_4 = ScreeningCase(
        owner_user_id=2,
        synthetic_case_code="SYN-CASE-204-PARTNER-OTHER",
        status="ready",
        screening_scope_label="Partner Separate Screen",
        source_reviewed=True,
    )
    db_session.add(case_4)
    db_session.flush()

    finding_4 = SyntheticFinding(
        case_id=case_4.id,
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        carrier_state="NO_VARIANT_DETECTED",
        inheritance_mode="AUTOSOMAL_RECESSIVE",
        classification_state="NEGATIVE_SCREEN",
        reviewed_flag=True,
        summary_text="Negative finding.",
    )
    db_session.add(finding_4)

    # Patient B issues a consent grant specifically and ONLY for Case 2
    grant_case_2 = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=2,  # Bound strictly to Case 2
    )
    db_session.add(grant_case_2)
    db_session.commit()

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Step A: Counsellor attempts to record provenance on Case 4 using Case 2's grant -> 403
    payload_4 = {
        "case_id": case_4.id,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Panel 4",
    }
    resp_case_4 = client.post("/api/v1/clinical/provenance", json=payload_4, headers=headers_c)
    assert resp_case_4.status_code == 403

    # Step B: Patient B issues a separate, explicit consent grant for Case 4
    grant_case_4 = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=case_4.id,  # Bound explicitly to Case 4
    )
    db_session.add(grant_case_4)
    db_session.commit()

    # Step C: Re-attempt on Case 4 -> now authorized -> 201 CREATED
    resp_case_4_authorized = client.post("/api/v1/clinical/provenance", json=payload_4, headers=headers_c)
    assert resp_case_4_authorized.status_code == 201
    assert resp_case_4_authorized.json()["case_id"] == case_4.id


def test_5_valid_couple_level_authorization_works_for_explicit_case_and_purpose(
    client: TestClient, db_session: Session
):
    """5. A valid couple-level authorization works for the cases and purpose it explicitly covers."""
    seed_database(db_session)

    # Valid couple grant explicitly binding Case 2 for preconception screening
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(grant)
    db_session.commit()

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Accredited Lab Beta Thal Panel",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert resp.status_code == 201
    assert resp.json()["case_id"] == 2
    assert resp.json()["condition_code"] == "HBB_BETA_THAL"


def test_6_unauthorized_purpose_on_consent_fails_closed(
    client: TestClient, db_session: Session
):
    """6. Consent grant for an unrelated purpose (e.g. general research) must NOT authorize
    preconception carrier risk provenance.
    """
    seed_database(db_session)

    # Consent grant with unrelated purpose
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="unrelated_consumer_marketing_survey",
        case_id=2,
    )
    db_session.add(grant)
    db_session.commit()

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Accredited Lab Beta Thal Panel",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c)
    assert resp.status_code == 403


def test_7_expired_revoked_pending_cancelled_permissions_fail_closed(
    client: TestClient, db_session: Session
):
    """7. Missing, expired, revoked, pending, and cancelled permissions fail closed."""
    seed_database(db_session)

    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Valid Source",
    }

    # A. Revoked consent -> 403
    revoked = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.REVOKED.value,
        revoked_at=datetime.now(timezone.utc),
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(revoked)
    db_session.commit()
    assert client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c).status_code == 403

    # B. Expired consent -> 403
    db_session.delete(revoked)
    expired = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(expired)
    db_session.commit()
    assert client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c).status_code == 403

    # C. Pending consent -> 403
    db_session.delete(expired)
    pending = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.PENDING.value,
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(pending)
    db_session.commit()
    assert client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c).status_code == 403

    # D. Cancelled referral -> 403
    db_session.delete(pending)
    valid_grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(valid_grant)
    ref = db_session.query(ReferralTask).filter(ReferralTask.participant_user_id == 1).first()
    ref.status = ReferralStatus.CANCELLED
    db_session.commit()
    assert client.post("/api/v1/clinical/provenance", json=payload, headers=headers_c).status_code == 403


def test_8_unassigned_counsellor_and_patient_rejected(
    client: TestClient, db_session: Session
):
    """8. Unassigned counsellors and patients are strictly rejected."""
    seed_database(db_session)

    # 1. Patient attempt -> 403
    login_p = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_p = {"Authorization": f"Bearer {login_p.json()['access_token']}"}
    resp_p = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 1,
            "condition_code": "CFTR_CYSTIC_FIBROSIS",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Patient Claim",
        },
        headers=headers_p,
    )
    assert resp_p.status_code == 403

    # 2. Unassigned counsellor attempt -> 403
    unassigned = User(
        email="unassigned@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.COUNSELLOR,
        is_active=True,
    )
    db_session.add(unassigned)
    db_session.commit()

    login_u = client.post(
        "/api/v1/auth/login",
        json={"email": "unassigned@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_u = {"Authorization": f"Bearer {login_u.json()['access_token']}"}
    resp_u = client.post(
        "/api/v1/clinical/provenance",
        json={
            "case_id": 1,
            "condition_code": "CFTR_CYSTIC_FIBROSIS",
            "residual_carrier_probability": 0.01,
            "clinical_source_reference": "Panel",
        },
        headers=headers_u,
    )
    assert resp_u.status_code == 403


def test_9_admin_follows_administrative_policy(
    client: TestClient, db_session: Session
):
    """9. Administrator follows explicit administrative review policy."""
    seed_database(db_session)

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

    payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Admin Central Ingestion QA",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers_adm)
    assert resp.status_code == 201
    assert resp.json()["reviewing_clinician_id"] == admin_user.id


def test_10_denied_attempts_are_audited_without_raw_genetic_data(
    client: TestClient, db_session: Session
):
    """10. Denied attempts are logged to audit trail without sensitive genetic data."""
    seed_database(db_session)

    unassigned = User(
        email="unassigned@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.COUNSELLOR,
        is_active=True,
    )
    db_session.add(unassigned)
    db_session.commit()

    login_u = client.post(
        "/api/v1/auth/login",
        json={"email": "unassigned@wadih.demo", "password": DEMO_PASSWORD},
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

    denied_audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "UNAUTHORIZED_PROVENANCE_ATTEMPT",
            AuditLog.actor_user_id == unassigned.id,
            AuditLog.outcome == "DENIED",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert denied_audit is not None
    raw_details = denied_audit.details or {}
    details = json.loads(raw_details) if isinstance(raw_details, str) else raw_details
    assert "sequence" not in str(details).lower()
    assert "genotype" not in str(details).lower()
    assert "variant" not in str(details).lower()
    assert "cftr" not in str(details).lower()
    assert details.get("case_id") == 1


def test_11_existing_valid_risk_calculations_continue_to_work(
    client: TestClient, db_session: Session
):
    """11. Existing valid risk calculations continue to work after authorized provenance creation."""
    seed_database(db_session)

    # Couple consent binding Case 2 specifically for preconception carrier screening
    grant = ConsentGrant(
        granter_user_id=2,
        grantee_user_id=1,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        case_id=2,
    )
    db_session.add(grant)
    db_session.commit()

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

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Assess via POST
    resp_post = client.post(
        "/api/v1/risk/cases/1/assess",
        json={"condition_code": "HBB_BETA_THAL", "partner_case_id": 2},
        headers=headers_a,
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data_post["risk_estimate"]["affected_probability"] == 0.0025

    # Assess via legacy GET
    resp_get = client.get(
        "/api/v1/risk/cases/1?condition_code=HBB_BETA_THAL&partner_case_id=2",
        headers=headers_a,
    )
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data_get["risk_estimate"]["affected_probability"] == 0.0025
