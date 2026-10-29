import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt

from app.seed.seed_demo import seed_database
from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.referral import ReferralTask, ReferralStatus
from app.core.config import Settings
from app.core.rate_limit import demo_session_limiter
from app.core.security import decode_access_token


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset demo session rate limiter before each test."""
    demo_session_limiter.reset()
    yield
    demo_session_limiter.reset()


def test_production_cors_excludes_localhost():
    """Verify that in production environment, localhost and 127.0.0.1 are strictly removed."""
    s = Settings(ENVIRONMENT="production")
    for origin in s.ALLOWED_ORIGINS:
        assert "localhost" not in origin
        assert "127.0.0.1" not in origin
        assert "0.0.0.0" not in origin
    assert "https://frontend-five-psi-43.vercel.app" in s.ALLOWED_ORIGINS


def test_demo_token_claims_and_me_endpoint(client: TestClient, db_session: Session):
    """Verify demo token contains is_demo=True, scope='synthetic_demo', 30-min expiry, and /me reflects claims."""
    seed_database(db_session)

    resp = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_demo"] is True
    assert data["scope"] == "synthetic_demo"
    assert data["user"]["is_demo_session"] is True
    assert data["user"]["token_scope"] == "synthetic_demo"

    # Decode raw token and verify payload claims and 30-minute expiry
    raw_token = data["access_token"]
    payload = decode_access_token(raw_token)
    assert payload is not None
    assert payload["is_demo"] is True
    assert payload["scope"] == "synthetic_demo"
    assert payload["demo_persona"] == "patient_a"
    # 30 minutes = 1800 seconds
    assert payload["exp"] - payload["iat"] <= 1805

    # Verify GET /api/v1/auth/me returns demo flags
    headers = {"Authorization": f"Bearer {raw_token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["is_demo_session"] is True
    assert me_data["token_scope"] == "synthetic_demo"


def test_demo_session_rate_limiting(client: TestClient, db_session: Session):
    """Verify demo session endpoint triggers 429 when sliding-window rate limit (15 req/min) is exceeded."""
    seed_database(db_session)

    # First 15 calls should succeed
    for _ in range(15):
        resp = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
        assert resp.status_code == 200

    # 16th call should be rate-limited with HTTP 429
    blocked_resp = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    assert blocked_resp.status_code == 429
    data = blocked_resp.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Too many demo session requests" in data["error"]["message"]


def test_demo_sessions_blocked_from_audit_logs(client: TestClient, db_session: Session):
    """Verify that demo sessions (including demo counsellor) are strictly barred from audit log inspection."""
    seed_database(db_session)

    # 1. Patient A demo session
    resp_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    token_a = resp_a.json()["access_token"]
    audit_resp_a = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token_a}"})
    assert audit_resp_a.status_code == 403

    # 2. Counsellor demo session
    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    token_c = resp_c.json()["access_token"]
    audit_resp_c = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token_c}"})
    assert audit_resp_c.status_code == 403
    assert "Audit log inspection is restricted to non-demo authenticated administrative users." in audit_resp_c.json()["error"]["message"]


def test_demo_counsellor_provenance_isolated_to_synthetic_sandbox(client: TestClient, db_session: Session):
    """Verify demo counsellor provenance creation forces [SYNTHETIC_DEMO_SANDBOX] prefix and isolates writes."""
    seed_database(db_session)

    # Get demo counsellor session
    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    token_c = resp_c.json()["access_token"]
    headers = {"Authorization": f"Bearer {token_c}"}

    provenance_payload = {
        "case_id": 1,
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "residual_carrier_probability": 0.02,
        "clinical_source_reference": "LabCorp CF 97-Variant Carrier Panel",
        "notes": "Reviewed synthetic lab panel",
    }
    resp = client.post("/api/v1/clinical/provenance", json=provenance_payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    # Must be branded with [SYNTHETIC_DEMO_SANDBOX] and explicit server-controlled flag
    assert data["is_synthetic_sandbox"] is True
    assert data["clinical_source_reference"].startswith("[SYNTHETIC_DEMO_SANDBOX]")
    assert "LabCorp CF 97-Variant Carrier Panel" in data["clinical_source_reference"]


def test_demo_provenance_cannot_authorize_authoritative_clinical_assessment(client: TestClient, db_session: Session):
    """Verify demo-session provenance CANNOT authorize an authoritative clinical assessment.

    CRITICAL SECURITY CHECK:
    - Provenance created by a demo counsellor is marked is_synthetic_sandbox=True.
    - Authoritative clinical assessment (simulation_mode=False) strictly ignores sandbox records.
    - Resulting calculation suppresses numerical certainty and sets clinician_confirmed_provenance=False.
    - When simulation_mode=True is requested, calculation proceeds with explicit simulation metadata.
    """
    seed_database(db_session)

    # 1. Demo counsellor records provenance for negative partner (Case 2, HBB_BETA_THAL)
    # First create an assigned referral task for Case 2
    counsellor = db_session.query(User).filter(User.email == "counsellor@wadih.demo").first()
    referral = ReferralTask(
        case_id=2,
        participant_user_id=2,
        assigned_counsellor_id=counsellor.id,
        reason_code="CARRIER_CONSULTATION",
        status=ReferralStatus.PENDING,
    )
    db_session.add(referral)
    db_session.commit()

    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    headers_c = {"Authorization": f"Bearer {resp_c.json()['access_token']}"}

    prov_payload = {
        "case_id": 2,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "LabCorp Beta-Thal Panel",
        "notes": "Reviewed in synthetic demonstration sandbox",
    }
    prov_resp = client.post("/api/v1/clinical/provenance", json=prov_payload, headers=headers_c)
    assert prov_resp.status_code == 201
    assert prov_resp.json()["is_synthetic_sandbox"] is True

    # 2. Patient A calls authoritative case assessment (simulation_mode=False)
    # With partner Case 2 linked under active consent
    from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
    grant = ConsentGrant(
        granter_user_id=2,  # Patient B
        grantee_user_id=1,  # Patient A
        scope=ConsentScope.CARRIER_STATUS_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()

    resp_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

    assess_payload_authoritative = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp_auth = client.post("/api/v1/risk/cases/1/assess", json=assess_payload_authoritative, headers=headers_a)
    assert resp_auth.status_code == 200
    auth_data = resp_auth.json()

    # Authoritative assessment MUST NOT accept synthetic sandbox record as clinical provenance!
    # Provenance is unconfirmed -> numerical recurrence figure is suppressed and residual risk is unverified
    assert auth_data["is_case_linked_assessment"] is True
    assert auth_data["is_synthetic_sandbox"] is False
    assert auth_data["is_educational_simulation"] is False
    assert auth_data["is_authoritative_clinical_record"] is False
    assert auth_data["clinician_confirmed_provenance"] is False
    assert auth_data["risk_estimate"] is None
    assert auth_data["assessment_status"] in ("INSUFFICIENT_DATA", "REVIEW_REQUIRED")

    # 3. Dedicated educational demonstration path (simulation_mode=True)
    assess_payload_demo = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": True,
    }
    resp_demo = client.post("/api/v1/risk/cases/1/assess", json=assess_payload_demo, headers=headers_a)
    assert resp_demo.status_code == 200
    demo_data = resp_demo.json()

    # Demo path clearly separates simulation from authoritative records
    assert demo_data["is_synthetic_sandbox"] is True
    assert demo_data["is_educational_simulation"] is True
    assert demo_data["is_authoritative_clinical_record"] is False
    assert demo_data["risk_estimate"] is not None
    assert demo_data["risk_estimate"]["residual_carrier_probability_used"] == 0.01
    assert "Hypothetical educational demonstration using synthetic sandbox residual risk parameters" in demo_data["disclaimer"]


def test_demo_patient_cannot_access_unauthorized_or_non_synthetic_records(client: TestClient, db_session: Session):
    """Verify demo patient cannot access non-synthetic cases, referrals, explanations, or unconsented records."""
    seed_database(db_session)

    # Create a non-synthetic case
    real_case = ScreeningCase(
        owner_user_id=1,
        synthetic_case_code="REAL-PATIENT-123",
        status="COMPLETED",
        screening_scope_label="Comprehensive Diagnostic",
    )
    db_session.add(real_case)
    db_session.flush()

    resp_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

    # 1. Read non-synthetic case -> 404
    assert client.get(f"/api/v1/cases/{real_case.id}", headers=headers_a).status_code == 404

    # 2. Read Patient B's case (Case 2) without consent -> 404
    assert client.get("/api/v1/cases/2", headers=headers_a).status_code == 404

    # 3. Read explanation for non-synthetic case -> 404
    assert client.get(f"/api/v1/cases/{real_case.id}/explanation", headers=headers_a).status_code == 404

    # 4. Create referral for non-synthetic case -> 404
    referral_payload = {
        "case_id": real_case.id,
        "reason_code": "CARRIER_CONSULTATION",
    }
    assert client.post("/api/v1/referrals", json=referral_payload, headers=headers_a).status_code == 404

    # 5. Create escalation for non-synthetic case -> 404
    escalation_payload = {
        "case_id": real_case.id,
        "trigger_reason": "VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
    }
    assert client.post("/api/v1/counselling/escalations", json=escalation_payload, headers=headers_a).status_code == 404


def test_demo_counsellor_cannot_access_unassigned_cases_or_referrals(client: TestClient, db_session: Session):
    """Verify demo counsellor cannot access or mutate referrals and cases not assigned to them."""
    seed_database(db_session)

    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    headers_c = {"Authorization": f"Bearer {resp_c.json()['access_token']}"}

    # Create an unassigned referral (assigned to another counsellor or None)
    unassigned_referral = ReferralTask(
        participant_user_id=1,
        case_id=1,
        assigned_counsellor_id=999,  # Unrelated counsellor ID
        reason_code="EXTERNAL_CONSULT",
        status=ReferralStatus.PENDING,
    )
    db_session.add(unassigned_referral)
    db_session.commit()

    # 1. Read unassigned referral by ID -> 404
    assert client.get(f"/api/v1/referrals/{unassigned_referral.id}", headers=headers_c).status_code == 404

    # 2. Update unassigned referral status -> 404
    update_payload = {"status": "SCHEDULED"}
    assert client.patch(f"/api/v1/referrals/{unassigned_referral.id}/status", json=update_payload, headers=headers_c).status_code == 404

    # 3. Add note to unassigned referral -> 403 or 404
    note_payload = {"note_text": "Unauthorized counsellor attempt"}
    assert client.post(f"/api/v1/referrals/{unassigned_referral.id}/notes", json=note_payload, headers=headers_c).status_code in (403, 404)

    # 4. Assess risk for unassigned case (Case 2 is assigned to no counsellor) -> 404
    assess_payload = {"condition_code": "CFTR_CF"}
    assert client.post("/api/v1/risk/cases/2/assess", json=assess_payload, headers=headers_c).status_code == 404


def test_demo_counsellor_cannot_record_provenance_on_non_synthetic_case(client: TestClient, db_session: Session):
    """Verify demo counsellor cannot record provenance on any non-synthetic case."""
    seed_database(db_session)

    # Create a non-synthetic case
    counsellor = db_session.query(User).filter(User.email == "counsellor@wadih.demo").first()
    real_case = ScreeningCase(
        owner_user_id=1,
        synthetic_case_code="REAL-CLINICAL-999",
        status="COMPLETED",
        screening_scope_label="Comprehensive",
    )
    db_session.add(real_case)
    db_session.flush()

    finding = SyntheticFinding(
        case_id=real_case.id,
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        inheritance_mode="AUTOSOMAL_RECESSIVE",
        carrier_state="NEGATIVE",
        classification_state="NEGATIVE",
    )
    referral = ReferralTask(
        case_id=real_case.id,
        participant_user_id=1,
        assigned_counsellor_id=counsellor.id,
        reason_code="CARRIER_CONSULTATION",
        status=ReferralStatus.PENDING,
    )
    db_session.add(finding)
    db_session.add(referral)
    db_session.commit()

    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    token_c = resp_c.json()["access_token"]
    headers = {"Authorization": f"Bearer {token_c}"}

    payload = {
        "case_id": real_case.id,
        "condition_code": "HBB_BETA_THAL",
        "residual_carrier_probability": 0.01,
        "clinical_source_reference": "Hospital Clinical Lab",
    }
    resp = client.post("/api/v1/clinical/provenance", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "Demo sessions are strictly restricted to synthetic demonstration cases" in resp.json()["error"]["message"]


def test_demo_sessions_restricted_from_real_consent_exchanges(client: TestClient, db_session: Session):
    """Verify demo sessions can only exchange consent within demo accounts."""
    seed_database(db_session)

    # Create an arbitrary non-demo user
    external_user = User(
        email="real.person@external.hospital",
        hashed_password="somehashvalue",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(external_user)
    db_session.commit()

    resp_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    token_a = resp_a.json()["access_token"]
    headers = {"Authorization": f"Bearer {token_a}"}

    # Attempt to grant consent from demo session to external real account
    grant_payload = {
        "grantee_user_id": external_user.id,
        "scope": "carrier_status_only",
        "purpose": "carrier_screening",
    }
    resp = client.post("/api/v1/consents", json=grant_payload, headers=headers)
    assert resp.status_code == 403
    assert "Demo sessions are strictly restricted to synthetic demonstration accounts" in resp.json()["error"]["message"]

    # Attempt to invite external real account
    invite_payload = {
        "partner_email": "real.person@external.hospital",
        "scope": "carrier_status_only",
        "purpose": "carrier_screening",
    }
    resp_inv = client.post("/api/v1/sharing/requests", json=invite_payload, headers=headers)
    assert resp_inv.status_code == 403
    assert "Demo sessions are strictly restricted to synthetic demonstration accounts" in resp_inv.json()["error"]["message"]
