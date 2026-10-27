from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_auth_flow(client: TestClient, db_session: Session):
    # Seed demo database
    seed_database(db_session)

    # 1. Login with Patient A
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    user_info = login_data["user"]
    assert user_info["email"] == "patient.a@wadih.demo"
    assert user_info["role"] == "patient"
    assert user_info["display_name"] == "Patient A (Carrier)"

    token = login_data["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Access /api/v1/me with token
    me_resp = client.get("/api/v1/me", headers=auth_header)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "patient.a@wadih.demo"
    assert me_data["role"] == "patient"

    # 3. Access /api/v1/auth/me
    auth_me_resp = client.get("/api/v1/auth/me", headers=auth_header)
    assert auth_me_resp.status_code == 200
    assert auth_me_resp.json()["email"] == "patient.a@wadih.demo"

    # 4. Logout invalidates token
    logout_resp = client.post("/api/v1/auth/logout", headers=auth_header)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out."

    # 5. Subsequent request with revoked token fails with 401
    revoked_resp = client.get("/api/v1/me", headers=auth_header)
    assert revoked_resp.status_code == 401
    err = revoked_resp.json()["error"]
    assert err["code"] == "UNAUTHENTICATED"


def test_login_invalid_credentials(client: TestClient, db_session: Session):
    seed_database(db_session)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "UNAUTHENTICATED"


def test_login_nonexistent_user(client: TestClient, db_session: Session):
    seed_database(db_session)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@wadih.demo", "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "UNAUTHENTICATED"


def test_unauthenticated_access(client: TestClient):
    resp = client.get("/api/v1/me")
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "UNAUTHENTICATED"
    assert "request_id" in err


def test_counsellor_login(client: TestClient, db_session: Session):
    seed_database(db_session)

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "counsellor@wadih.demo", "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "counsellor"
    assert "Dr. Sarah Chen" in data["user"]["display_name"]
