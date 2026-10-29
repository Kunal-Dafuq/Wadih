"""Regression test suite for Risk Assessment Metadata, API Semantics, and Provenance Boundaries.

Verifies the 5 required exact scenarios:
1. Verified non-synthetic clinical provenance yields authoritative clinical record.
2. Synthetic sandbox provenance:
   - Excluded when simulation_mode=False (fails closed: INSUFFICIENT_DATA, risk_estimate=None).
   - Accepted when simulation_mode=True with functional calculation, but clinician_confirmed_provenance=False.
3. Two synthetic demo cases (SYN-) that both have carrier findings cannot be labelled authoritative.
4. A valid educational dual-carrier simulation.
5. A valid, genuinely eligible authoritative assessment with non-synthetic clinical cases.
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.seed.seed_demo import seed_database, DEMO_PASSWORD


def _setup_cases_and_consent(db_session: Session):
    """Seed base demo data with synthetic demo cases (SYN-CASE-101 and SYN-CASE-202)."""
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


def _setup_non_synthetic_clinical_cases(db_session: Session):
    """Seed base data and convert cases 1 and 2 to genuine non-synthetic clinical cases (no SYN- prefix)."""
    seed_database(db_session)
    c1 = db_session.query(ScreeningCase).filter(ScreeningCase.id == 1).first()
    c2 = db_session.query(ScreeningCase).filter(ScreeningCase.id == 2).first()
    c1.synthetic_case_code = "CLINICAL-CASE-001"
    c2.synthetic_case_code = "CLINICAL-CASE-002"

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


def test_scenario_1_verified_non_synthetic_clinical_provenance(
    client: TestClient, db_session: Session
):
    """Scenario 1: Verified non-synthetic clinical provenance.

    When non-synthetic clinical cases are evaluated with verified non-synthetic clinical
    provenance, an authoritative assessment succeeds with is_authoritative_clinical_record=True,
    clinician_confirmed_provenance=True, and is_synthetic_sandbox=False.
    """
    _setup_non_synthetic_clinical_cases(db_session)

    # Insert an authoritative, NON-SYNTHETIC clinical residual risk record on Case 2
    clinical_rec = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.005,
        clinical_source_reference="Accredited Molecular Genetics Lab (CAP/CLIA #12345)",
        reviewing_clinician_id=3,
        notes="Official reviewed residual carrier probability.",
        is_active=True,
        is_synthetic_sandbox=False,  # NON-SYNTHETIC CLINICAL RECORD
        reviewed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(clinical_rec)
    db_session.commit()

    # Authenticate as Patient A via standard login
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
    assert login_a.status_code == 200
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

    # Verified non-synthetic provenance yields authoritative clinical record
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
    assert "Authoritative clinical risk assessment" in data["disclaimer"]


def test_scenario_2_synthetic_sandbox_provenance(
    client: TestClient, db_session: Session
):
    """Scenario 2: Synthetic sandbox provenance.

    - Excluded when simulation_mode=False (fails closed: INSUFFICIENT_DATA, risk_estimate=None,
      is_authoritative_clinical_record=False, clinician_confirmed_provenance=False).
    - Accepted when simulation_mode=True with functional calculation, but
      is_educational_simulation=True, is_synthetic_sandbox=True,
      is_authoritative_clinical_record=False, and clinician_confirmed_provenance=False.
    """
    _setup_cases_and_consent(db_session)

    # Insert a SYNTHETIC SANDBOX clinical record on Case 2
    sandbox_rec = ClinicalResidualRiskRecord(
        case_id=2,
        condition_code="HBB_BETA_THAL",
        residual_carrier_probability=0.008,
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
    assert login_a.status_code == 200
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 2A. Authoritative evaluation (simulation_mode=False) MUST exclude sandbox record
    req_authoritative = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": False,
    }
    resp_auth = client.post("/api/v1/risk/cases/1/assess", json=req_authoritative, headers=headers_a)
    assert resp_auth.status_code == 200
    data_auth = resp_auth.json()

    assert data_auth["is_case_linked_assessment"] is True
    assert data_auth["is_authoritative_clinical_record"] is False
    assert data_auth["clinician_confirmed_provenance"] is False
    assert data_auth["assessment_status"] == "INSUFFICIENT_DATA"
    assert data_auth["risk_estimate"] is None

    # 2B. Educational simulation (simulation_mode=True) accepts sandbox record for calculation
    req_simulation = {
        "condition_code": "HBB_BETA_THAL",
        "partner_case_id": 2,
        "simulation_mode": True,
    }
    resp_sim = client.post("/api/v1/risk/cases/1/assess", json=req_simulation, headers=headers_a)
    assert resp_sim.status_code == 200
    data_sim = resp_sim.json()

    assert data_sim["is_case_linked_assessment"] is True
    assert data_sim["is_authoritative_clinical_record"] is False
    assert data_sim["is_educational_simulation"] is True
    assert data_sim["is_synthetic_sandbox"] is True
    # CRITICAL: clinician_confirmed_provenance must be False when using synthetic sandbox
    assert data_sim["clinician_confirmed_provenance"] is False
    # Educational risk calculation remains fully functional:
    assert data_sim["risk_estimate"] is not None
    assert data_sim["risk_estimate"]["affected_probability"] == round(0.008 * 0.25, 6)
    assert "Hypothetical educational demonstration using synthetic sandbox residual risk parameters" in data_sim["disclaimer"]


def test_scenario_3_two_synthetic_demo_cases_with_carrier_findings(
    client: TestClient, db_session: Session
):
    """Scenario 3: Two synthetic demo cases that both have carrier findings.

    Screening findings from explicitly identified synthetic demo cases (SYN-) cannot be labelled
    authoritative merely because residual-risk provenance is unnecessary for the 25% Mendelian arithmetic.
    """
    _setup_cases_and_consent(db_session)

    # Set Case 2 finding to CARRIER_DETECTED on synthetic demo case SYN-CASE-202
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

    # Even though both partners are carriers (25% risk), synthetic demo cases cannot be authoritative
    assert data["is_case_linked_assessment"] is True
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["clinician_confirmed_provenance"] is False
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == 0.25
    assert data["risk_estimate"]["carrier_probability"] == 0.50
    assert "Educational demonstration using synthetic screening cases" in data["disclaimer"]


def test_scenario_4_valid_educational_dual_carrier_simulation(
    client: TestClient, db_session: Session
):
    """Scenario 4: A valid educational dual-carrier simulation.

    Verifies hypothetical simulation endpoint POST /api/v1/risk/assess produces
    accurate 25% Mendelian calculation with simulation flags and without claiming authoritative status.
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
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == 0.25
    assert data["risk_estimate"]["carrier_probability"] == 0.50
    assert "Hypothetical educational simulation only" in data["disclaimer"]


def test_scenario_5_valid_genuinely_eligible_authoritative_assessment(
    client: TestClient, db_session: Session
):
    """Scenario 5: A valid, genuinely eligible authoritative assessment.

    When both screening cases are verified non-synthetic clinical records (no SYN- prefix),
    both findings are clinician-reviewed, and both partners are confirmed carriers,
    the assessment is an authoritative clinical record.
    """
    _setup_non_synthetic_clinical_cases(db_session)

    # Set both findings on non-synthetic cases to CARRIER_DETECTED with reviewed_flag=True
    f2 = db_session.query(SyntheticFinding).filter(
        SyntheticFinding.case_id == 2,
        SyntheticFinding.condition_code == "HBB_BETA_THAL",
    ).first()
    f2.carrier_state = "CARRIER_DETECTED"
    f2.classification_state = "PATHOGENIC_CARRIER"
    f2.reviewed_flag = True
    db_session.commit()

    # Authenticate as Patient A via standard login
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
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
    assert data["clinician_confirmed_provenance"] is False  # Not required/used for dual-carrier
    assert data["risk_estimate"] is not None
    assert data["risk_estimate"]["affected_probability"] == 0.25
    assert data["risk_estimate"]["carrier_probability"] == 0.50
    assert "Authoritative clinical risk assessment" in data["disclaimer"]


def test_authoritative_assessment_missing_provenance_fails_closed(
    client: TestClient, db_session: Session
):
    """Negative check: Non-synthetic cases lacking clinical provenance fail closed.

    If non-synthetic cases have single carrier + negative partner but lack a clinical
    provenance record, it must return INSUFFICIENT_DATA and is_authoritative_clinical_record=False.
    """
    _setup_non_synthetic_clinical_cases(db_session)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "patient.a@wadih.demo", "password": DEMO_PASSWORD},
    )
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
    assert data["is_authoritative_clinical_record"] is False
    assert data["is_educational_simulation"] is False
    assert data["is_synthetic_sandbox"] is False
    assert data["clinician_confirmed_provenance"] is False
    assert data["assessment_status"] == "INSUFFICIENT_DATA"
    assert data["risk_estimate"] is None
