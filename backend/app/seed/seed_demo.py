"""Database seeder for demo accounts, synthetic screening cases, and educational content."""

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.participant import ParticipantProfile
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.education import EducationalContent
from app.models.referral import ReferralTask, ReferralStatus, CounsellorNote
from app.core.security import hash_password

DEMO_PASSWORD = "DemoPassword123!"


def seed_database(db: Session = None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Check if already seeded
        existing_patient = db.query(User).filter(User.email == "patient.a@wadih.demo").first()
        if existing_patient:
            print("Database already contains demo seed data.")
            return

        print("Seeding demo accounts...")
        hashed_pwd = hash_password(DEMO_PASSWORD)

        # 1. Patient A
        patient_a = User(
            email="patient.a@wadih.demo",
            hashed_password=hashed_pwd,
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add(patient_a)
        db.flush()

        profile_a = ParticipantProfile(
            user_id=patient_a.id,
            display_name="Patient A (Carrier)",
            preferred_language="en",
            literacy_mode="standard",
        )
        db.add(profile_a)

        # 2. Patient B
        patient_b = User(
            email="patient.b@wadih.demo",
            hashed_password=hashed_pwd,
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add(patient_b)
        db.flush()

        profile_b = ParticipantProfile(
            user_id=patient_b.id,
            display_name="Patient B (Partner)",
            preferred_language="en",
            literacy_mode="plain_language",
        )
        db.add(profile_b)

        # 3. Genetic Counsellor
        counsellor = User(
            email="counsellor@wadih.demo",
            hashed_password=hashed_pwd,
            role=UserRole.COUNSELLOR,
            is_active=True,
        )
        db.add(counsellor)
        db.flush()

        profile_c = ParticipantProfile(
            user_id=counsellor.id,
            display_name="Dr. Sarah Chen, MS CGC",
            preferred_language="en",
            literacy_mode="standard",
        )
        db.add(profile_c)
        db.flush()

        # Seed Synthetic Screening Cases for Patient A
        print("Seeding synthetic screening cases...")
        case_a = ScreeningCase(
            owner_user_id=patient_a.id,
            synthetic_case_code="SYN-CASE-101",
            status="ready",
            screening_scope_label="Comprehensive Expanded Carrier Screen (300+ genes)",
            source_reviewed=True,
        )
        db.add(case_a)
        db.flush()

        # Synthetic Findings for Patient A: Beta Thalassemia Carrier
        finding_a1 = SyntheticFinding(
            case_id=case_a.id,
            condition_code="HBB_BETA_THAL",
            condition_name="Beta Thalassemia",
            carrier_state="CARRIER_DETECTED",
            inheritance_mode="AUTOSOMAL_RECESSIVE",
            classification_state="PATHOGENIC_CARRIER",
            reviewed_flag=True,
            summary_text="Synthetic demonstration carrier finding: Heterozygous pathogenic variant in HBB gene.",
        )
        # Non-carrier finding for Cystic Fibrosis
        finding_a2 = SyntheticFinding(
            case_id=case_a.id,
            condition_code="CFTR_CYSTIC_FIBROSIS",
            condition_name="Cystic Fibrosis",
            carrier_state="NO_VARIANT_DETECTED",
            inheritance_mode="AUTOSOMAL_RECESSIVE",
            classification_state="NEGATIVE_SCREEN",
            reviewed_flag=True,
            summary_text="No pathogenic variants identified in CFTR gene panel.",
        )
        db.add_all([finding_a1, finding_a2])

        # Seed Synthetic Screening Cases for Patient B
        case_b = ScreeningCase(
            owner_user_id=patient_b.id,
            synthetic_case_code="SYN-CASE-202",
            status="ready",
            screening_scope_label="Comprehensive Expanded Carrier Screen (300+ genes)",
            source_reviewed=True,
        )
        db.add(case_b)
        db.flush()

        finding_b1 = SyntheticFinding(
            case_id=case_b.id,
            condition_code="HBB_BETA_THAL",
            condition_name="Beta Thalassemia",
            carrier_state="NO_VARIANT_DETECTED",
            inheritance_mode="AUTOSOMAL_RECESSIVE",
            classification_state="NEGATIVE_SCREEN",
            reviewed_flag=True,
            summary_text="No pathogenic variants identified in HBB gene panel.",
        )
        db.add(finding_b1)

        # Seed Reviewed Educational Content
        print("Seeding educational content...")
        edu_content_carrier = EducationalContent(
            content_key="AUTOSOMAL_RECESSIVE_CARRIER",
            language="en",
            version="1.0",
            title="Understanding Your Carrier Screening Result",
            body=(
                "Carrier screening identifies whether you carry a gene change for certain inherited genetic conditions. "
                "Being a carrier typically means you have one working copy of the gene and one altered copy. "
                "Carriers are generally healthy and do not develop symptoms of the condition.\n\n"
                "When both biological parents carry an altered copy of the same autosomal recessive gene, "
                "there is a 25% (1 in 4) chance with each pregnancy that the child could inherit both altered copies "
                "and have the condition. There is a 50% chance the child is a carrier like the parents, and a 25% chance "
                "the child inherits two working gene copies."
            ),
            key_takeaways=(
                "1. A carrier is healthy and has no disease symptoms.\n"
                "2. Reproductive risk occurs if both reproductive partners are carriers for the SAME condition.\n"
                "3. Carrier screening is educational and simulated for demonstration."
            ),
            approved_by_role="GENETIC_COUNSELLOR",
            source_refs="ACMG Carrier Screening Practice Resource (2021); ACOG Committee Opinion No. 690.",
            active=True,
        )

        edu_content_thal = EducationalContent(
            content_key="HBB_BETA_THAL",
            language="en",
            version="1.0",
            title="Beta Thalassemia Carrier Information",
            body=(
                "Beta thalassemia is an inherited red blood cell condition affecting hemoglobin production. "
                "Carriers (also known as having beta thalassemia trait or minor) may have slight microcytosis "
                "or mild anemia, but generally lead normal, healthy lives.\n\n"
                "If only one partner is a carrier and the other is not, there is no risk of having a child with "
                "beta thalassemia major."
            ),
            key_takeaways=(
                "1. Beta thalassemia trait is harmless for the individual in daily life.\n"
                "2. Partner testing provides clarity regarding joint reproductive risk.\n"
                "3. Consult a genetic counsellor for personalized pre-conception discussions."
            ),
            approved_by_role="GENETIC_COUNSELLOR",
            source_refs="National Institutes of Health (NIH) Genetic and Rare Diseases Information Center.",
            active=True,
        )
        db.add_all([edu_content_carrier, edu_content_thal])

        # Seed Sample Referral Task for Patient A
        print("Seeding referral task...")
        referral_a = ReferralTask(
            participant_user_id=patient_a.id,
            case_id=case_a.id,
            assigned_counsellor_id=counsellor.id,
            reason_code="CARRIER_RESULT_CONSULT",
            status=ReferralStatus.PENDING,
            urgency_level="ROUTINE",
        )
        db.add(referral_a)
        db.flush()

        note_a = CounsellorNote(
            referral_id=referral_a.id,
            author_user_id=counsellor.id,
            note_text="Participant requested simulated educational genetic counselling session regarding Beta Thalassemia carrier finding.",
        )
        db.add(note_a)

        db.commit()
        print("Seed completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    seed_database()
