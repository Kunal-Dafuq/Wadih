from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope


def test_consent_grant_create_and_lifecycle(client: TestClient, db_session: Session):
    """Test standard consent grant creation by a participant."""
    seed_database(db_session)

    # Login Patient A (id=1)
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Patient A grants summary access to Patient B (id=2)
    payload = {
        "grantee_user_id": 2,
        "scope": "summary_only",
        "purpose": "preconception_carrier_screening",
        "case_id": 1,
    }
    grant_resp = client.post("/api/v1/consents", json=payload, headers=headers_a)
    assert grant_resp.status_code == 201
    grant_data = grant_resp.json()
    consent_id = grant_data["id"]
    assert grant_data["status"] == "GRANTED"
    assert grant_data["scope"] == "summary_only"
    assert grant_data["granter_user_id"] == 1
    assert grant_data["grantee_user_id"] == 2

    # Verify Patient B can view the shared case
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    shared_resp = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert shared_resp.status_code == 200
    shared_data = shared_resp.json()
    assert shared_data["case_id"] == 1
    assert shared_data["granted_scope"] == "summary_only"
    assert len(shared_data["findings"]) == 2

    # Patient A revokes consent
    revoke_resp = client.post(f"/api/v1/consents/{consent_id}/revoke", headers=headers_a)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"
    assert revoke_resp.json()["revoked_at"] is not None

    # Patient B attempts access AFTER revocation -> 403 CONSENT_REQUIRED
    revoked_access_resp = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert revoked_access_resp.status_code == 403
    assert revoked_access_resp.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_unauthorized_user_cannot_approve_another_users_consent(client: TestClient, db_session: Session):
    """Security: A user cannot approve another person's consent grant."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Patient A creates a partner invitation request (PENDING)
    invite_resp = client.post(
        "/api/v1/sharing/requests",
        json={"partner_email": "patient.b@wadih.demo", "scope": "summary_only"},
        headers=headers_a,
    )
    assert invite_resp.status_code == 201
    consent_id = invite_resp.json()["id"]
    assert invite_resp.json()["status"] == "PENDING"

    # Patient B (the grantee) attempts to approve the grant on Patient A's behalf -> 403 FORBIDDEN
    hijack_resp = client.post(f"/api/v1/consents/{consent_id}/approve", headers=headers_b)
    assert hijack_resp.status_code == 403
    assert hijack_resp.json()["error"]["code"] == "FORBIDDEN"

    # Patient A (the granter) approves own grant -> 200 OK
    legit_resp = client.post(f"/api/v1/consents/{consent_id}/approve", headers=headers_a)
    assert legit_resp.status_code == 200
    assert legit_resp.json()["status"] == "GRANTED"


def test_partner_invitation_does_not_grant_access_until_approved(client: TestClient, db_session: Session):
    """Privacy: A partner invitation does NOT grant immediate access to findings."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Create invitation for Case 1
    client.post(
        "/api/v1/sharing/requests",
        json={"partner_email": "patient.b@wadih.demo", "scope": "summary_only", "case_id": 1},
        headers=headers_a,
    )

    # Partner attempts access while invitation is PENDING -> 403 CONSENT_REQUIRED
    pending_access = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert pending_access.status_code == 403
    assert pending_access.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_consent_scope_filtering(client: TestClient, db_session: Session):
    """Scope Enforcement: carrier_status_only strips summary text; summary_only preserves summary."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Grant carrier_status_only
    client.post(
        "/api/v1/consents",
        json={"grantee_user_id": 2, "scope": "carrier_status_only", "case_id": 1},
        headers=headers_a,
    )

    resp_carrier_only = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert resp_carrier_only.status_code == 200
    findings = resp_carrier_only.json()["findings"]
    # All summary_text must be redacted/None
    for f in findings:
        assert f["summary_text"] is None
        assert f["carrier_state"] is not None


def test_expired_consent_denied(client: TestClient, db_session: Session):
    """Expiration: A consent grant whose expires_at is in the past is rejected."""
    seed_database(db_session)

    # Insert pre-expired grant in DB
    past_time = datetime.now(timezone.utc) - timedelta(days=2)
    expired_grant = ConsentGrant(
        granter_user_id=1,
        grantee_user_id=2,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        expires_at=past_time,
    )
    db_session.add(expired_grant)
    db_session.commit()

    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert resp.status_code == 403
    assert "expired" in resp.json()["error"]["message"].lower()
