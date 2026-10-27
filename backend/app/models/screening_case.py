from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ScreeningCase(Base):
    __tablename__ = "screening_cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    synthetic_case_code = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="ready", nullable=False)
    screening_scope_label = Column(String(255), nullable=False)
    source_reviewed = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner = relationship("User", back_populates="screening_cases")
    findings = relationship(
        "SyntheticFinding",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    referrals = relationship(
        "ReferralTask",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    education_assessments = relationship(
        "EducationAssessment",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class SyntheticFinding(Base):
    __tablename__ = "synthetic_findings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("screening_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    condition_code = Column(String(64), index=True, nullable=False)
    condition_name = Column(String(255), nullable=False)
    carrier_state = Column(String(64), nullable=False)
    inheritance_mode = Column(String(64), nullable=False)
    classification_state = Column(String(64), nullable=False)
    reviewed_flag = Column(Boolean, default=True, nullable=False)
    summary_text = Column(Text, nullable=True)

    # Relationships
    case = relationship("ScreeningCase", back_populates="findings")
