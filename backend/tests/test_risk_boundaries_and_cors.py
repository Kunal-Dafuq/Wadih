import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed.seed_demo import seed_database
from app.models.user import User, UserRole
from app.core.security import hash_password


def test_cors_preflight_and_headers(client: TestClient):
    """Verify CORS preflight allows exact production frontend origin and required headers."""
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://frontend-five-psi-43.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://frontend-five-psi-43.vercel.app"
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()
    assert "content-type" in resp.headers["access-control-allow-headers"].lower()


def test_cors_preflight_rejects_arbitrary_unapproved_origins(client: TestClient):
    """Verify wildcard *.vercel.app is removed; arbitrary preview/external domains are rejected."""
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://arbitrary-unapproved-preview.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    # FastAPI CORSMiddleware returns 400 Disallowed CORS origin for unlisted origins
    assert resp.status_code == 400


def test_generic_risk_assess_rejects_case_id_bypass(client: TestClient, db_session: Session):
    """Verify POST /api/v1/risk/assess rejects case_id to prevent bypassing case-level provenance & consent."""
    seed_database(db_session)
    login_resp = client.post(
        "/api/v1/auth/demo-session",
        json={"persona": "patient_a"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to supply case_id to generic assess endpoint
    bypass_payload = {
        "case_id": "SYN-CASE-101",
        "condition_code": "HBB_BETA_THAL",
        "condition_name": "Beta Thalassemia",
        "gene_symbol": "HBB",
        "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
        "partner_1_finding": "CARRIER_DETECTED",
        "partner_2_finding": "CARRIER_DETECTED",
    }
    resp = client.post("/api/v1/risk/assess", json=bypass_payload, headers=headers)
    assert resp.status_code == 422
    data = resp.json()
    assert "generic /risk/assess endpoint is an educational simulator" in data["error"]["message"]


def test_generic_risk_assess_educational_simulation_flags(client: TestClient, db_session: Session):
    """Verify valid educational scenario simulation marks output as simulation and not authoritative record."""
    seed_database(db_session)
    login_resp = client.post(
        "/api/v1/auth/demo-session",
        json={"persona": "patient_a"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    scenario_payload = {
        "condition_code": "HBB_BETA_THAL",
        "condition_name": "Beta Thalassemia",
        "gene_symbol": "HBB",
        "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
        "partner_1_finding": "CARRIER_DETECTED",
        "partner_2_finding": "CARRIER_DETECTED",
    }
    resp = client.post("/api/v1/risk/assess", json=scenario_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] is None
    assert data["is_educational_simulation"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert "Hypothetical educational simulation only" in data["disclaimer"]


def test_case_linked_risk_assessment_authoritative_flags(client: TestClient, db_session: Session):
    """Verify case-linked endpoint POST /api/v1/risk/cases/{case_id}/assess marks result as authoritative."""
    seed_database(db_session)
    login_resp = client.post(
        "/api/v1/auth/demo-session",
        json={"persona": "patient_a"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    case_payload = {
        "condition_code": "HBB_BETA_THAL",
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=case_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "SYN-CASE-101"
    assert data["is_educational_simulation"] is False
    assert data["is_authoritative_clinical_record"] is True


def test_demo_session_authentication_flow(client: TestClient, db_session: Session):
    """Verify demo-session endpoint issues tokens for synthetic personas and blocks administrative escalation."""
    seed_database(db_session)

    # 1. Patient A
    resp_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    assert resp_a.status_code == 200
    assert resp_a.json()["user"]["email"] == "patient.a@wadih.demo"
    assert resp_a.json()["user"]["role"] == "patient"

    # 2. Patient B
    resp_b = client.post("/api/v1/auth/demo-session", json={"persona": "patient_b"})
    assert resp_b.status_code == 200
    assert resp_b.json()["user"]["email"] == "patient.b@wadih.demo"

    # 3. Counsellor
    resp_c = client.post("/api/v1/auth/demo-session", json={"persona": "counsellor"})
    assert resp_c.status_code == 200
    assert resp_c.json()["user"]["email"] == "counsellor@wadih.demo"
    assert resp_c.json()["user"]["role"] == "counsellor"

    # 4. Admin escalation attempt -> strictly forbidden
    # Create an admin user to test that demo session refuses to grant admin access
    admin_user = User(
        email="admin@wadih.demo",
        hashed_password=hash_password("adminSecret123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    resp_admin = client.post("/api/v1/auth/demo-session", json={"persona": "admin"})
    assert resp_admin.status_code in (403, 422)

    # 5. Invalid persona -> validation error
    resp_invalid = client.post("/api/v1/auth/demo-session", json={"persona": "super_hacker"})
    assert resp_invalid.status_code == 422
