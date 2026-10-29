"""Regression test suite for Risk Assessment Metadata, API Semantics, and Provenance Boundaries.

Verifies:
1. Authoritative assessment with verified non-synthetic clinical provenance.
2. Authoritative assessment with missing clinical provenance (fails closed: INSUFFICIENT_DATA, risk_estimate=None, is_authoritative=False).
3. Authoritative assessment excludes synthetic sandbox provenance when simulation_mode=False.
4. Educational simulation accepts synthetic sandbox provenance with explicit simulation metadata.
5. Standalone hypothetical assessment (/risk/assess) is marked is_case_linked_assessment=False and is_authoritative=False.
6. Dual-carrier case-linked assessment satisfies authoritative criteria without needing residual risk.
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.seed.seed_demo import seed_database


def _setup_cases_and_consent(db_session: Session):
    """Seed base demo data and active consent from Patient B to Patient A for Case 2."""
    seed_database(db_session)
    consent = ConsentGrant(
        granter_user_id=2,  # Patient B (owner of Case 2)
        grantee_user_id=1,  # Patient A (owner of Case 1)
        case_id=2,
        scope=ConsentScope.SUMMARY_ONLY.value,
        status=ConsentStatus.GRANTED.value,
        purpose="preconception_carrier_screening",
        terms_version="v1.0",
    )
    db_session.add(consent)
    db_session.commit()


def test_1_authoritative_assessment_with_verified_clinical_provenance(
    client: TestClient, db_session: Session
):
    """1. When verified, non-synthetic clinical provenance is present, an authoritative
    assessment succeeds with is_authoritative_clinical_record=True and calculated risk.
    """
    _setup_cases_and_consent(db_session)

    # Insert an authoritative, NON-SYNTHETIC clinical residual risk record on Case 2
    clinical_rec = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.005,
        clinical_source_reference="Accredited Molecular Genetics Lab (CAP/CLIA #12345)",
        reviewing_clinician_id=3,
        notes="Official reviewed residual carrier probability.",
        is_active=True,
        is_synthetic_sandbox=False,  # AUTHORITATIVE CLINICAL RECORD
        reviewed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(clinical_rec)
    db_session.commit()

    # Authenticate as Patient A
    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Evaluate in authoritative mode
    req = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=req, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Verified clinical provenance yields authoritative clinical record
    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is True
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["clinician_confirmed_provenance"] is True
    assert data["assessment_status"] == "EDUCATIONAL_RESULT"
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == round(0.005 * 0.25, 6)
    assert data["risk_estimate"]["carrier_probability"] == 0.50
    assert data["risk_estimate"]["residual_carrier_probability_used"] == 0.005


def test_2_authoritative_assessment_with_missing_provenance(
    client: TestClient, db_session: Session
):
    """2. If case-linked assessment lacks valid clinical provenance, it must return
    INSUFFICIENT_DATA, risk_estimate=None, and is_authoritative_clinical_record=False.
    """
    _setup_cases_and_consent(db_session)

    # No clinical record added to db

    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    req = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=req, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Must fail closed: not authoritative, no risk estimate
    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["clinician_confirmed_provenance"] is False
    assert data["assessment_status"] == "INSUFFICIENT_DATA"
    assert data["risk_estimate"] is None


def test_3_authoritative_assessment_excludes_synthetic_only_provenance(
    client: TestClient, db_session: Session
):
    """3. If only a synthetic sandbox record exists and simulation_mode=False,
    the sandbox record MUST be excluded, returning INSUFFICIENT_DATA, risk_estimate=None,
    and is_authoritative_clinical_record=False.
    """
    _setup_cases_and_consent(db_session)

    # Insert a SYNTHETIC SANDBOX clinical record on Case 2
    sandbox_rec = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.01,
        clinical_source_reference="[SYNTHETIC_DEMO_SANDBOX] Synthetic Reference Lab",
        reviewing_clinician_id=3,
        notes="Synthetic demonstration sandbox record.",
        is_active=True,
        is_synthetic_sandbox=True,  # SYNTHETIC DEMO SANDBOX
        reviewed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sandbox_rec)
    db_session.commit()

    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Authoritative evaluation (simulation_mode=False)
    req = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=req, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Synthetic sandbox excluded from authoritative evaluation
    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["clinician_confirmed_provenance"] is False
    assert data["assessment_status"] == "INSUFFICIENT_DATA"
    assert data["risk_estimate"] is None


def test_4_educational_simulation_with_synthetic_sandbox_provenance(
    client: TestClient, db_session: Session
):
    """4. When simulation_mode=True, synthetic sandbox records are accepted for educational
    calculation with explicit simulation flags (is_educational_simulation=True,
    is_authoritative_clinical_record=False, is_synthetic_sandbox=True).
    """
    _setup_cases_and_consent(db_session)

    # Insert synthetic sandbox record
    sandbox_rec = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.008,
        clinical_source_reference="[SYNTHETIC_DEMO_SANDBOX] Synthetic Reference Lab",
        reviewing_clinician_id=3,
        notes="Synthetic demonstration sandbox record.",
        is_active=True,
        is_synthetic_sandbox=True,
        reviewed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sandbox_rec)
    db_session.commit()

    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Simulation mode explicitly requested
    req = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": True,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=req, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    # Explicit educational simulation flags
    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_educational_simulation"] is True
    assert data["is_synthetic_sandbox"] is True
    assert data["clinician_confirmed_provenance"] is True
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == round(0.008 * 0.25, 6)
    assert "Hypothetical educational demonstration using synthetic sandbox residual risk parameters" in data["disclaimer"]


def test_5_standalone_hypothetical_assessment_not_case_linked(
    client: TestClient, db_session: Session
):
    """5. Standalone endpoint POST /api/v1/risk/assess without database cases is marked
    is_case_linked_assessment=False, is_educational_simulation=True, is_authoritative=False.
    """
    seed_database(db_session)
    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    scenario_payload = {
        "condition_code": "CFTR_CYSTIC_FIBROSIS",
        "condition_name": "Cystic Fibrosis",
        "inheritance_pattern": "AUTOSOMAL_RECESSIVE",
        "partner_1_finding": "CARRIER_DETECTED",
        "partner_2_finding": "CARRIER_DETECTED",
    }
    resp = client.post("/api/v1/risk/assess", json=scenario_payload, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["case_id"] is None
    assert data["is_case_linked_assessment"] is False
    assert data["is_educational_simulation"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == 0.25


def test_6_dual_carrier_case_linked_authoritative(
    client: TestClient, db_session: Session
):
    """6. When both partners in linked cases are confirmed carriers, residual risk is not required,
    and the assessment is an authoritative clinical record.
    """
    _setup_cases_and_consent(db_session)

    # Update Case 2 finding to CARRIER_DETECTED as well
    f2 = db_session.query(SyntheticFinding).filter(
        SyntheticFinding.case_id == 2,
        SyntheticFinding.condition_code == "HBB_BETA_THAL",
    ).first()
    f2.carrier_state = "CARRIER_DETECTED"
    f2.classification_state = "PATHOGENIC_CARRIER"
    f2.reviewed_flag = True
    db_session.commit()

    login_a = client.post("/api/v1/auth/demo-session", json={"persona": "patient_a"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    req = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp = client.post("/api/v1/risk/cases/1/assess", json=req, headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is True
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == 0.25
    assert data["risk_estimate"]["carrier_probability"] == 0.50
