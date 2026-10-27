from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_referral_crud_lifecycle(client: TestClient, db_session: Session):
    seed_database(db_session)

    # 1. Login Patient A
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 2. Login Counsellor
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # 3. Patient A lists referrals
    ref_list = client.get("/api/v1/referrals", headers=headers_a)
    assert ref_list.status_code == 200
    refs = ref_list.json()
    assert len(refs) >= 1
    seeded_ref_id = refs[0]["id"]
    assert refs[0]["reason_code"] == "CARRIER_RESULT_CONSULT"
    assert len(refs[0]["notes"]) >= 1

    # 4. Patient A creates new referral for Case 1
    create_resp = client.post(
        "/api/v1/referrals",
        headers=headers_a,
        json={
            "case_id": 1,
            "reason_code": "PARTNER_MATCHING_REVIEW",
            "urgency_level": "ROUTINE",
        },
    )
    assert create_resp.status_code == 201
    new_ref = create_resp.json()
    assert new_ref["status"] == "PENDING"
    assert new_ref["reason_code"] == "PARTNER_MATCHING_REVIEW"
    new_ref_id = new_ref["id"]

    # 5. Counsellor views the referral
    c_view = client.get(f"/api/v1/referrals/{new_ref_id}", headers=headers_c)
    assert c_view.status_code == 200
    assert c_view.json()["id"] == new_ref_id

    # 6. Counsellor adds note
    note_resp = client.post(
        f"/api/v1/referrals/{new_ref_id}/notes",
        headers=headers_c,
        json={"note_text": "Follow-up session scheduled with participant."},
    )
    assert note_resp.status_code == 201
    assert "Follow-up session" in note_resp.json()["note_text"]

    # 7. Counsellor updates status to SCHEDULED
    status_resp = client.patch(
        f"/api/v1/referrals/{new_ref_id}/status",
        headers=headers_c,
        json={"status": "SCHEDULED"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "SCHEDULED"


def test_referral_isolation_and_permissions(client: TestClient, db_session: Session):
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

    # Patient B attempts to access Patient A's referral (id 1) -> 404 NOT_FOUND
    b_access = client.get("/api/v1/referrals/1", headers=headers_b)
    assert b_access.status_code == 404
    assert b_access.json()["error"]["code"] == "NOT_FOUND"

    # Patient A attempts to add counsellor note -> 403 FORBIDDEN
    note_attempt = client.post(
        "/api/v1/referrals/1/notes",
        headers=headers_a,
        json={"note_text": "Participant attempting unauthorized clinician note."},
    )
    assert note_attempt.status_code == 403
    assert note_attempt.json()["error"]["code"] == "FORBIDDEN"

    # Patient B attempts to create referral using Patient A's case (case_id 1) -> 404 NOT_FOUND
    invalid_case_ref = client.post(
        "/api/v1/referrals",
        headers=headers_b,
        json={"case_id": 1, "reason_code": "UNAUTHORIZED_CASE_REF"},
    )
    assert invalid_case_ref.status_code == 404
    assert invalid_case_ref.json()["error"]["code"] == "NOT_FOUND"
