from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.services.audit_service import AuditService
from app.models.audit import AuditLog
from app.models.user import User, UserRole
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


def test_counsellor_least_privilege_audit_scoping(client: TestClient, db_session: Session):
    """Least Privilege: Counsellors can only view audit logs for assigned cases and referrals.

    A counsellor MUST NOT retrieve events for unrelated cases or unrelated activities
    merely because the event actor is a participant assigned to that counsellor.
    Admins have global visibility.
    """
    from app.core.security import hash_password
    seed_database(db_session)

    # Create Admin user
    admin_user = User(
        email="admin@wadih.demo",
        hashed_password=hash_password(DEMO_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    # 1. Log an event for an assigned participant & assigned case (Patient A, Case 1, Referral 1)
    AuditService.log_event(
        db=db_session,
        action="ASSIGNED_CASE_EVENT",
        resource_type="screening_case",
        resource_id="1",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Assigned case event"},
    )

    # 2. Log an event where assigned participant (Patient A, id=1) interacts with an UNASSIGNED case (Case 999)
    AuditService.log_event(
        db=db_session,
        action="UNASSIGNED_CASE_BY_ASSIGNED_PARTICIPANT",
        resource_type="screening_case",
        resource_id="999",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Participant A viewed an unassigned case"},
    )

    # 3. Log an unrelated activity performed by assigned participant (Patient A, id=1) (e.g. profile edit, password change)
    AuditService.log_event(
        db=db_session,
        action="UNRELATED_ACTIVITY_BY_ASSIGNED_PARTICIPANT",
        resource_type="user_profile",
        resource_id="1",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Participant A updated profile settings"},
    )

    # 4. Log an event for an entirely unrelated patient and case (User 999, Case 999)
    AuditService.log_event(
        db=db_session,
        action="UNASSIGNED_CASE_EVENT",
        resource_type="screening_case",
        resource_id="999",
        actor_user_id=999,
        outcome="SUCCESS",
        details={"note": "Unassigned case event"},
    )

    # 5. Log an event performed by the Counsellor themself (User 3)
    AuditService.log_event(
        db=db_session,
        action="COUNSELLOR_OWN_ACTION",
        resource_type="counsellor_note",
        resource_id="1",
        actor_user_id=3,
        outcome="SUCCESS",
        details={"note": "Counsellor created session note"},
    )

    # Query as Counsellor (User 3, assigned to Case 1)
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    counsellor_resp = client.get("/api/v1/audit/events", headers=headers_c)
    assert counsellor_resp.status_code == 200
    c_events = counsellor_resp.json()["events"]
    c_actions = [e["action"] for e in c_events]

    # Permitted: Assigned case and counsellor's own action
    assert "ASSIGNED_CASE_EVENT" in c_actions
    assert "COUNSELLOR_OWN_ACTION" in c_actions

    # Strictly Denied: Unassigned case, even when performed by assigned participant!
    assert "UNASSIGNED_CASE_BY_ASSIGNED_PARTICIPANT" not in c_actions
    # Strictly Denied: Unrelated activity, even when performed by assigned participant!
    assert "UNRELATED_ACTIVITY_BY_ASSIGNED_PARTICIPANT" not in c_actions
    # Strictly Denied: Completely unassigned event
    assert "UNASSIGNED_CASE_EVENT" not in c_actions

    # Query as Admin (full platform visibility)
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_admin = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    admin_resp = client.get("/api/v1/audit/events", headers=headers_admin)
    assert admin_resp.status_code == 200
    admin_events = admin_resp.json()["events"]
    admin_actions = [e["action"] for e in admin_events]

    assert "ASSIGNED_CASE_EVENT" in admin_actions
    assert "COUNSELLOR_OWN_ACTION" in admin_actions
    assert "UNASSIGNED_CASE_BY_ASSIGNED_PARTICIPANT" in admin_actions
    assert "UNRELATED_ACTIVITY_BY_ASSIGNED_PARTICIPANT" in admin_actions
    assert "UNASSIGNED_CASE_EVENT" in admin_actions


def test_audit_log_immutability_blocks_updates_and_deletions(db_session: Session):
    """Integrity: AuditLog records are append-only. ORM-level event listeners block updates and deletes."""
    import pytest

    entry1 = AuditService.log_event(
        db=db_session,
        action="IMMUTABLE_TEST_EVENT_1",
        resource_type="screening_case",
        resource_id="101",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Initial audit entry 1"},
        commit=False,
    )
    db_session.flush()

    # 1. Attempt to update the audit record -> blocked by ORM listener
    entry1.action = "TAMPERED_ACTION"
    with pytest.raises(
        RuntimeError,
        match="AuditLog records are append-only and immutable. Updates are strictly prohibited.",
    ):
        db_session.flush()

    db_session.rollback()

    # 2. Attempt to delete an audit record -> blocked by ORM listener
    entry2 = AuditService.log_event(
        db=db_session,
        action="IMMUTABLE_TEST_EVENT_2",
        resource_type="screening_case",
        resource_id="102",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Initial audit entry 2"},
        commit=False,
    )
    db_session.flush()

    db_session.delete(entry2)
    with pytest.raises(
        RuntimeError,
        match="AuditLog records are append-only and immutable. Deletions are strictly prohibited.",
    ):
        db_session.flush()


def test_audit_log_bulk_orm_mutations_blocked(db_session: Session):
    """Integrity: SessionEvents.do_orm_execute blocks bulk ORM UPDATE and DELETE statements targeting AuditLog."""
    import pytest
    from sqlalchemy import update, delete

    entry = AuditService.log_event(
        db=db_session,
        action="BULK_TEST_EVENT",
        resource_type="screening_case",
        resource_id="103",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Initial bulk audit test entry"},
        commit=False,
    )
    db_session.flush()

    # 1. Attempt bulk ORM UPDATE targeting AuditLog
    with pytest.raises(
        RuntimeError,
        match="AuditLog records are append-only and immutable. Bulk UPDATE statements via ORM are strictly prohibited.",
    ):
        db_session.execute(update(AuditLog).where(AuditLog.id == entry.id).values(action="HACKED_ACTION"))

    db_session.rollback()

    # 2. Re-create and attempt bulk ORM DELETE targeting AuditLog
    entry2 = AuditService.log_event(
        db=db_session,
        action="BULK_TEST_EVENT_2",
        resource_type="screening_case",
        resource_id="104",
        actor_user_id=1,
        outcome="SUCCESS",
        details={"note": "Initial bulk audit test entry 2"},
        commit=False,
    )
    db_session.flush()

    with pytest.raises(
        RuntimeError,
        match="AuditLog records are append-only and immutable. Bulk DELETE statements via ORM are strictly prohibited.",
    ):
        db_session.execute(delete(AuditLog).where(AuditLog.id == entry2.id))

    db_session.rollback()



def test_transactional_atomic_rollback_on_audit_failure(db_session: Session, monkeypatch):
    """Transactional Consistency: If audit logging fails, the business action is rolled back.

    No orphan consent grant or escalation should exist in the database.
    """
    from app.services.consent_service import ConsentService
    from app.schemas.consent import ConsentGrantCreateRequest
    from app.models.consent import ConsentGrant
    from app.models.user import User, UserRole

    user_a = User(id=10, email="user.a@demo.com", hashed_password="dummy_hash", role=UserRole.PATIENT)
    user_b = User(id=11, email="user.b@demo.com", hashed_password="dummy_hash", role=UserRole.PATIENT)
    db_session.add_all([user_a, user_b])
    db_session.commit()

    req = ConsentGrantCreateRequest(
        grantee_user_id=11,
        scope="summary_only",
        purpose="preconception_carrier_screening",
    )

    # Monkeypatch log_event to simulate database error or failure
    def failing_log_event(*args, **kwargs):
        raise RuntimeError("Simulated audit write failure")

    monkeypatch.setattr(AuditService, "log_event", failing_log_event)

    import pytest

    with pytest.raises(RuntimeError, match="Simulated audit write failure"):
        try:
            ConsentService.create_consent_grant(db=db_session, granter=user_a, request_data=req)
        except Exception:
            db_session.rollback()
            raise

    # Verify no grant was persisted
    saved_grant = (
        db_session.query(ConsentGrant)
        .filter(ConsentGrant.granter_user_id == 10, ConsentGrant.grantee_user_id == 11)
        .first()
    )
    assert saved_grant is None

