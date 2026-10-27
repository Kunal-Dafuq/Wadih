from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.participant import ParticipantProfile
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.education import EducationAssessment, EducationalContent
from app.models.referral import ReferralTask, ReferralStatus, CounsellorNote


def test_user_and_profile_creation(db_session: Session):
    user = User(
        email="test.user@wadih.org",
        hashed_password="hashed_secret_test",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.PATIENT

    profile = ParticipantProfile(
        user_id=user.id,
        display_name="Test Participant",
        preferred_language="en",
        literacy_mode="standard",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.id is not None
    assert profile.user.email == "test.user@wadih.org"
    assert user.profile.display_name == "Test Participant"


def test_screening_case_and_findings(db_session: Session):
    user = User(
        email="carrier.user@wadih.org",
        hashed_password="hashed_password",
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    case = ScreeningCase(
        owner_user_id=user.id,
        synthetic_case_code="SYN-TEST-001",
        status="ready",
        screening_scope_label="Carrier Screening Panel (Standard)",
        source_reviewed=True,
    )
    db_session.add(case)
    db_session.commit()

    finding = SyntheticFinding(
        case_id=case.id,
        condition_code="HBB_BETA_THAL",
        condition_name="Beta Thalassemia",
        carrier_state="CARRIER_DETECTED",
        inheritance_mode="AUTOSOMAL_RECESSIVE",
        classification_state="PATHOGENIC_CARRIER",
        reviewed_flag=True,
        summary_text="One copy of pathogenic variant detected. Typical carrier status.",
    )
    db_session.add(finding)
    db_session.commit()

    assert case.id is not None
    assert len(case.findings) == 1
    assert case.findings[0].condition_code == "HBB_BETA_THAL"


def test_education_content_and_assessment(db_session: Session):
    user = User(
        email="learner@wadih.org",
        hashed_password="hashed_password",
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    case = ScreeningCase(
        owner_user_id=user.id,
        synthetic_case_code="SYN-TEST-002",
        status="ready",
        screening_scope_label="Comprehensive Panel",
    )
    db_session.add(case)
    db_session.commit()

    content = EducationalContent(
        content_key="CARRIER_OVERVIEW",
        language="en",
        version="1.0",
        title="Understanding Carrier Screening",
        body="Being a carrier means having one changed copy of a gene without health symptoms.",
        approved_by_role="GENETIC_COUNSELLOR",
        active=True,
    )
    db_session.add(content)

    assessment = EducationAssessment(
        user_id=user.id,
        case_id=case.id,
        content_version="1.0",
        score=3,
        total_questions=3,
        attempt_count=1,
        passed=True,
    )
    db_session.add(assessment)
    db_session.commit()

    assert content.id is not None
    assert assessment.id is not None
    assert assessment.user_id == user.id
    assert assessment.score == 3


def test_referral_task_and_counsellor_note(db_session: Session):
    participant = User(
        email="patient.referral@wadih.org",
        hashed_password="hashed_password",
        role=UserRole.PATIENT,
    )
    counsellor = User(
        email="gc.specialist@wadih.org",
        hashed_password="hashed_password",
        role=UserRole.COUNSELLOR,
    )
    db_session.add_all([participant, counsellor])
    db_session.commit()

    case = ScreeningCase(
        owner_user_id=participant.id,
        synthetic_case_code="SYN-TEST-003",
        status="ready",
        screening_scope_label="Pre-conception Carrier Screen",
    )
    db_session.add(case)
    db_session.commit()

    referral = ReferralTask(
        participant_user_id=participant.id,
        case_id=case.id,
        assigned_counsellor_id=counsellor.id,
        reason_code="CARRIER_CONSULT",
        status=ReferralStatus.PENDING,
        urgency_level="ROUTINE",
    )
    db_session.add(referral)
    db_session.commit()

    note = CounsellorNote(
        referral_id=referral.id,
        author_user_id=counsellor.id,
        note_text="Initial intake scheduled with participant.",
    )
    db_session.add(note)
    db_session.commit()

    assert referral.id is not None
    assert referral.status == ReferralStatus.PENDING
    assert len(referral.notes) == 1
    assert referral.notes[0].note_text == "Initial intake scheduled with participant."
