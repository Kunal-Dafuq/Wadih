from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_screening_cases_ownership_and_access(client: TestClient, db_session: Session):
    seed_database(db_session)

    # 1. Login Patient A
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 2. Login Patient B
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Patient A lists cases -> receives case SYN-CASE-101
    cases_a_resp = client.get("/api/v1/cases", headers=headers_a)
    assert cases_a_resp.status_code == 200
    cases_a = cases_a_resp.json()
    assert len(cases_a) == 1
    case_a_id = cases_a[0]["id"]
    assert cases_a[0]["synthetic_case_code"] == "SYN-CASE-101"

    # Patient A views detail of own case
    detail_a_resp = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_a)
    assert detail_a_resp.status_code == 200
    detail_a = detail_a_resp.json()
    assert detail_a["synthetic_case_code"] == "SYN-CASE-101"
    assert len(detail_a["findings"]) == 2
    assert detail_a["findings"][0]["condition_code"] == "HBB_BETA_THAL"
    assert "educational_disclaimer" in detail_a

    # Patient B lists cases -> receives case SYN-CASE-202
    cases_b_resp = client.get("/api/v1/cases", headers=headers_b)
    assert cases_b_resp.status_code == 200
    cases_b = cases_b_resp.json()
    assert len(cases_b) == 1
    case_b_id = cases_b[0]["id"]
    assert cases_b[0]["synthetic_case_code"] == "SYN-CASE-202"

    # STRICT ISOLATION: Patient B attempts to access Patient A's case -> 404 NOT_FOUND
    unauthorized_b = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_b)
    assert unauthorized_b.status_code == 404
    err_b = unauthorized_b.json()["error"]
    assert err_b["code"] == "NOT_FOUND"

    # STRICT ISOLATION: Patient A attempts to access Patient B's case -> 404 NOT_FOUND
    unauthorized_a = client.get(f"/api/v1/cases/{case_b_id}", headers=headers_a)
    assert unauthorized_a.status_code == 404
    err_a = unauthorized_a.json()["error"]
    assert err_a["code"] == "NOT_FOUND"


def test_counsellor_assigned_case_access(client: TestClient, db_session: Session):
    seed_database(db_session)

    # Login Counsellor (Dr. Sarah Chen, who is assigned to Patient A's referral)
    login_c = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Counsellor can view Patient A's assigned case (case_id 1)
    case_resp = client.get("/api/v1/cases/1", headers=headers_c)
    assert case_resp.status_code == 200
    assert case_resp.json()["synthetic_case_code"] == "SYN-CASE-101"


def test_nonexistent_case(client: TestClient, db_session: Session):
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    resp = client.get("/api/v1/cases/9999", headers=headers_a)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
