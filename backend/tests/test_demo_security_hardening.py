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

    # Must be branded with [SYNTHETIC_DEMO_SANDBOX]
    assert data["clinical_source_reference"].startswith("[SYNTHETIC_DEMO_SANDBOX]")
    assert "LabCorp CF 97-Variant Carrier Panel" in data["clinical_source_reference"]


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
