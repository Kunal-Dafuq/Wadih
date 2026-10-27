from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class EducationAssessment(Base):
    __tablename__ = "education_assessments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    case_id = Column(
        Integer,
        ForeignKey("screening_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_version = Column(String(32), default="v1.0", nullable=False)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, default=3, nullable=False)
    attempt_count = Column(Integer, default=1, nullable=False)
    passed = Column(Boolean, default=True, nullable=False)
    completed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="education_assessments")
    case = relationship("ScreeningCase", back_populates="education_assessments")


class EducationalContent(Base):
    __tablename__ = "educational_content"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content_key = Column(String(100), index=True, nullable=False)
    language = Column(String(10), default="en", nullable=False)
    version = Column(String(20), default="1.0", nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    key_takeaways = Column(Text, nullable=True)
    approved_by_role = Column(String(64), default="GENETIC_COUNSELLOR", nullable=False)
    reviewed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    source_refs = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
