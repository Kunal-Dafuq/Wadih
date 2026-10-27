import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    COUNSELLOR = "counsellor"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, native_enum=False), default=UserRole.PATIENT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    profile = relationship(
        "ParticipantProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    screening_cases = relationship(
        "ScreeningCase",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    referrals_as_participant = relationship(
        "ReferralTask",
        foreign_keys="ReferralTask.participant_user_id",
        back_populates="participant",
    )
    referrals_as_counsellor = relationship(
        "ReferralTask",
        foreign_keys="ReferralTask.assigned_counsellor_id",
        back_populates="assigned_counsellor",
    )
    education_assessments = relationship(
        "EducationAssessment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
