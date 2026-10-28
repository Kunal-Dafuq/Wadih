from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.seed.seed_demo import seed_database, DEMO_PASSWORD
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.referral import ReferralTask, ReferralStatus


def test_escalation_detection_and_creation(client: TestClient, db_session: Session):
    """Test deterministic clinical escalation workflow."""
    seed_database(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Add an uncertain finding (VUS) to Case 1
    vus_finding = SyntheticFinding(
        case_id=1,
        condition_code="GJB2_NONSYNDROMIC_HEARING_LOSS",
        condition_name="GJB2-related Hearing Loss",
        carrier_state="VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
        inheritance_mode="AUTOSOMAL_RECESSIVE",
        classification_state="VUS",
        reviewed_flag=False,
        summary_text="Novel synthetic missense alteration classified as VUS.",
    )
    db_session.add(vus_finding)
    db_session.commit()

    # Check escalation triggers for Case 1
    triggers_resp = client.get("/api/v1/counselling/escalations/check/1", headers=headers_a)
    assert triggers_resp.status_code == 200
    triggers = triggers_resp.json()
    assert "VARIANT_OF_UNCERTAIN_SIGNIFICANCE" in triggers
    assert "CLINICIAN_REVIEW_REQUIRED" in triggers

    # Create clinical escalation
    payload = {
        "case_id": 1,
        "trigger_reason": "VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
        "urgency_level": "PRIORITY",
        "clinical_rationale": "Participant requests clarification regarding ambiguous GJB2 VUS finding.",
    }
    create_resp = client.post("/api/v1/counselling/escalations", json=payload, headers=headers_a)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["case_id"] == 1
    assert data["trigger_reason"] == "VARIANT_OF_UNCERTAIN_SIGNIFICANCE"
    assert data["urgency_level"] == "PRIORITY"
    assert data["status"] == "PENDING"
    assert "Dr. Sarah Chen" in (data["assigned_counsellor_name"] or "")

    # Verify referral persisted in ReferralTask table
    referral_id = data["referral_id"]
    task = db_session.query(ReferralTask).filter(ReferralTask.id == referral_id).first()
    assert task is not None
    assert task.reason_code == "VARIANT_OF_UNCERTAIN_SIGNIFICANCE"
    assert task.urgency_level == "PRIORITY"
    assert task.status == ReferralStatus.PENDING
