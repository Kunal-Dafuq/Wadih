from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_user_and_profile_endpoints(client: TestClient, db_session: Session):
    seed_database(db_session)

    # Login as Patient A
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/v1/users/me
    me_resp = client.get("/api/v1/users/me", headers=headers)
    assert me_resp.status_code == 200
    user_detail = me_resp.json()
    assert user_detail["email"] == "patient.a@wadih.demo"
    assert user_detail["profile"]["display_name"] == "Patient A (Carrier)"
    assert user_detail["profile"]["literacy_mode"] == "standard"

    # GET /api/v1/users/me/profile
    profile_resp = client.get("/api/v1/users/me/profile", headers=headers)
    assert profile_resp.status_code == 200
    profile_data = profile_resp.json()
    assert profile_data["preferred_language"] == "en"

    # PATCH /api/v1/users/me/profile - Update literacy mode & language
    patch_resp = client.patch(
        "/api/v1/users/me/profile",
        headers=headers,
        json={
            "display_name": "Patient A (Updated)",
            "preferred_language": "ar",
            "literacy_mode": "plain_language",
        },
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["display_name"] == "Patient A (Updated)"
    assert updated_data["preferred_language"] == "ar"
    assert updated_data["literacy_mode"] == "plain_language"


def test_update_profile_validation_error(client: TestClient, db_session: Session):
    seed_database(db_session)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Invalid literacy_mode
    invalid_patch = client.patch(
        "/api/v1/users/me/profile",
        headers=headers,
        json={"literacy_mode": "invalid_literacy_mode"},
    )
    assert invalid_patch.status_code == 422
    err = invalid_patch.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "request_id" in err
