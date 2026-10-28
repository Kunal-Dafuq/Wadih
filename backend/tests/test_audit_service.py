from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.services.audit_service import AuditService
from app.models.audit import AuditLog
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_audit_event_sanitization_removes_secrets_and_variants(db_session: Session):
    """Sanitization: Raw variants, passwords, and tokens must NEVER be stored in audit logs."""
    sensitive_payload = {
        "password": "MySecretPassword123!",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive",
        "raw_variant": "chr11:5225464:G>A",
        "c_dot": "c.92+5G>A",
        "p_dot": "p.Glu26Lys",
        "safe_summary": "Carrier finding for demonstration",
    }

    entry = AuditService.log_event(
        db=db_session,
        action="TEST_SENSITIVE_ACTION",
        resource_type="screening_report",
        resource_id="101",
        actor_user_id=1,
        outcome="SUCCESS",
        details=sensitive_payload,
    )

    saved_log = db_session.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert saved_log is not None
    assert "MySecretPassword123!" not in saved_log.details
    assert "eyJhbGciOiJIUzI1Ni" not in saved_log.details
    assert "chr11:5225464:G>A" not in saved_log.details
    assert "[REDACTED_SENSITIVE_DATA]" in saved_log.details
    assert "safe_summary" in saved_log.details


def test_denied_access_recorded_in_audit(client: TestClient, db_session: Session):
    """Audit Trail: Denied access attempts are logged with outcome='DENIED'."""
    seed_database(db_session)

    # Patient B attempts to access Patient A's case without consent
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    client.get("/api/v1/sharing/shared-cases/1", headers=headers_b)

    # Check that ACCESS_DENIED was logged in the database
    denied_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "ACCESS_DENIED", AuditLog.actor_user_id == 2)
        .first()
    )
    assert denied_log is not None
    assert denied_log.outcome == "DENIED"
    assert denied_log.resource_type == "screening_case"
    assert denied_log.resource_id == "1"


def test_consent_grant_and_revoke_logged_in_audit(client: TestClient, db_session: Session):
    """Audit Trail: Consent grant and revocation operations are recorded."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Create grant
    grant_resp = client.post(
        "/api/v1/consents",
        json={"grantee_user_id": 2, "scope": "summary_only"},
        headers=headers_a,
    )
    consent_id = grant_resp.json()["id"]

    # Verify CONSENT_GRANTED logged
    grant_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "CONSENT_GRANTED", AuditLog.actor_user_id == 1)
        .first()
    )
    assert grant_log is not None
    assert grant_log.outcome == "SUCCESS"

    # Revoke grant
    client.post(f"/api/v1/consents/{consent_id}/revoke", headers=headers_a)

    # Verify CONSENT_REVOKED logged
    revoke_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "CONSENT_REVOKED", AuditLog.actor_user_id == 1)
        .first()
    )
    assert revoke_log is not None
    assert revoke_log.outcome == "SUCCESS"
