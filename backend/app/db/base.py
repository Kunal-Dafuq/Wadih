from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import models below to ensure they are registered with Base.metadata
from app.models.user import User  # noqa
from app.models.participant import ParticipantProfile  # noqa
from app.models.screening_case import ScreeningCase, SyntheticFinding  # noqa
from app.models.education import EducationAssessment, EducationalContent  # noqa
from app.models.referral import ReferralTask, CounsellorNote  # noqa
from app.models.shared_stubs import SharedConsentGrantStub, SharedAuditLogStub  # noqa
