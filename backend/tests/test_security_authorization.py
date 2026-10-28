from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope


def test_idor_protection_case_access(client: TestClient, db_session: Session):
    """IDOR Prevention: Accessing another user's case via URL parameter returns uniform 404 NOT_FOUND."""
    seed_database(db_session)

    # Login Patient B
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Case 1 belongs to Patient A. Patient B requests Case 1 via /api/v1/cases/1 -> 404
    resp = client.get("/api/v1/cases/1", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    # Same for /api/v1/sharing/shared-cases/1 without consent -> 404
    resp_shared = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert resp_shared.status_code == 404
    assert resp_shared.json()["error"]["code"] == "NOT_FOUND"


def test_unauthenticated_requests_rejected(client: TestClient):
    """Security: Protected endpoints reject requests with missing or invalid tokens."""
    # 1. No token provided
    resp_no_token = client.get("/api/v1/cases")
    assert resp_no_token.status_code == 401
    assert resp_no_token.json()["error"]["code"] == "UNAUTHENTICATED"

    # 2. Malformed token provided
    resp_bad_token = client.get(
        "/api/v1/cases", headers={"Authorization": "Bearer malformed.fake.token"}
    )
    assert resp_bad_token.status_code == 401
    assert resp_bad_token.json()["error"]["code"] == "UNAUTHENTICATED"


def test_privileged_audit_endpoint_role_enforcement(client: TestClient, db_session: Session):
    """RBAC: /api/v1/audit/events requires ADMIN or COUNSELLOR role."""
    seed_database(db_session)

    # 1. Normal Patient attempts to view audit logs -> 403 FORBIDDEN
    login_p = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_p = {"Authorization": f"Bearer {login_p.json()['access_token']}"}

    resp_denied = client.get("/api/v1/audit/events", headers=headers_p)
    assert resp_denied.status_code == 403
    assert resp_denied.json()["error"]["code"] == "FORBIDDEN"

    # 2. Counsellor views audit logs -> 200 OK
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    resp_allowed = client.get("/api/v1/audit/events", headers=headers_c)
    assert resp_allowed.status_code == 200
    assert "events" in resp_allowed.json()


def test_unauthorized_consent_revocation_attempt(client: TestClient, db_session: Session):
    """Security: A user cannot revoke a consent grant granted by another participant."""
    seed_database(db_session)

    # Patient A grants consent to Patient B
    grant = ConsentGrant(
        granter_user_id=1,
        grantee_user_id=2,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
    )
    db_session.add(grant)
    db_session.commit()
    db_session.refresh(grant)

    # Patient B attempts to revoke Patient A's grant -> 403 FORBIDDEN
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = client.post(f"/api/v1/consents/{grant.id}/revoke", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_case_detail_access_with_full_report_vs_summary_only(client: TestClient, db_session: Session):
    """Object-Level Access Control: Only explicit full_report consent permits direct /api/v1/cases/{id} access.

    Holders of summary_only receive 404 NOT_FOUND on direct case lookup (IDOR protection),
    but can access via /api/v1/sharing/shared-cases/{id}.
    """
    from app.models.audit import AuditLog

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

    # 1. Patient A grants summary_only to Patient B
    grant_summary = client.post(
        "/api/v1/consents",
        json={"grantee_user_id": 2, "scope": "summary_only", "case_id": 1},
        headers=headers_a,
    )
    assert grant_summary.status_code == 201

    # Patient B attempts direct case detail -> 404 NOT_FOUND (summary_only is not full_report)
    resp_direct_denied = client.get("/api/v1/cases/1", headers=headers_b)
    assert resp_direct_denied.status_code == 404
    assert resp_direct_denied.json()["error"]["code"] == "NOT_FOUND"

    # Patient B accesses via shared-cases endpoint -> 200 OK
    resp_shared_ok = client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)
    assert resp_shared_ok.status_code == 200

    # 2. Patient A now grants full_report to Patient B
    grant_full = client.post(
        "/api/v1/consents",
        json={"grantee_user_id": 2, "scope": "full_report", "case_id": 1},
        headers=headers_a,
    )
    assert grant_full.status_code == 201

    # Patient B attempts direct case detail now -> 200 OK
    resp_direct_ok = client.get("/api/v1/cases/1", headers=headers_b)
    assert resp_direct_ok.status_code == 200
    assert resp_direct_ok.json()["id"] == 1
    assert "findings" in resp_direct_ok.json()

    # Verify audit log recorded SENSITIVE_RESULT_ACCESSED
    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "SENSITIVE_RESULT_ACCESSED",
            AuditLog.actor_user_id == 2,
            AuditLog.resource_id == "1",
        )
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.outcome == "SUCCESS"

