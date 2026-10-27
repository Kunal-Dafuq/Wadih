from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def test_education_explanation_and_teach_back(client: TestClient, db_session: Session):
    seed_database(db_session)

    # Login Patient A
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 1. Retrieve explanation for Case 1 (SYN-CASE-101 owned by Patient A)
    exp_resp = client.get("/api/v1/cases/1/explanation", headers=headers_a)
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert "Understanding Your Carrier Screening Result" in exp_data["title"]
    assert len(exp_data["condition_guides"]) >= 1
    assert "limitations_disclaimer" in exp_data
    assert len(exp_data["teach_back_questions"]) == 3

    # 2. Submit perfect knowledge check answers
    submission = {
        "answers": [
            {"question_id": 1, "selected_option_id": "B"},
            {"question_id": 2, "selected_option_id": "B"},
            {"question_id": 3, "selected_option_id": "A"},
        ]
    }
    kc_resp = client.post(
        "/api/v1/cases/1/knowledge-check", headers=headers_a, json=submission
    )
    assert kc_resp.status_code == 200
    kc_data = kc_resp.json()
    assert kc_data["score"] == 3
    assert kc_data["total_questions"] == 3
    assert kc_data["passed"] is True
    assert kc_data["attempt_count"] == 1
    assert len(kc_data["evaluations"]) == 3
    for ev in kc_data["evaluations"]:
        assert ev["is_correct"] is True

    # 3. Retake knowledge check with 1 mistake -> attempt count increments to 2
    submission_attempt2 = {
        "answers": [
            {"question_id": 1, "selected_option_id": "A"},  # incorrect
            {"question_id": 2, "selected_option_id": "B"},  # correct
            {"question_id": 3, "selected_option_id": "A"},  # correct
        ]
    }
    kc_resp2 = client.post(
        "/api/v1/cases/1/knowledge-check", headers=headers_a, json=submission_attempt2
    )
    assert kc_resp2.status_code == 200
    kc_data2 = kc_resp2.json()
    assert kc_data2["score"] == 2
    assert kc_data2["passed"] is True  # 2 of 3 passes threshold
    assert kc_data2["attempt_count"] == 2


def test_education_unauthorized_case_access(client: TestClient, db_session: Session):
    seed_database(db_session)

    # Login Patient B
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.b@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Patient B attempts to access explanation for Case 1 (owned by Patient A)
    resp = client.get("/api/v1/cases/1/explanation", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    # Patient B attempts to submit assessment for Case 1
    submission = {
        "answers": [
            {"question_id": 1, "selected_option_id": "B"},
            {"question_id": 2, "selected_option_id": "B"},
            {"question_id": 3, "selected_option_id": "A"},
        ]
    }
    sub_resp = client.post(
        "/api/v1/cases/1/knowledge-check", headers=headers_b, json=submission
    )
    assert sub_resp.status_code == 404
    assert sub_resp.json()["error"]["code"] == "NOT_FOUND"


def test_knowledge_check_validation_error(client: TestClient, db_session: Session):
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Incomplete answers (missing Q3)
    incomplete_sub = {
        "answers": [
            {"question_id": 1, "selected_option_id": "B"},
            {"question_id": 2, "selected_option_id": "B"},
        ]
    }
    resp = client.post(
        "/api/v1/cases/1/knowledge-check", headers=headers_a, json=incomplete_sub
    )
    assert resp.status_code in [400, 422]
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
