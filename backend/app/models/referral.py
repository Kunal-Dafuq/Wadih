import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReferralStatus(str, enum.Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReferralTask(Base):
    __tablename__ = "referral_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    participant_user_id = Column(
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
    assigned_counsellor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    reason_code = Column(String(64), nullable=False)
    status = Column(
        SQLEnum(ReferralStatus, native_enum=False),
        default=ReferralStatus.PENDING,
        nullable=False,
    )
    urgency_level = Column(String(32), default="ROUTINE", nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    participant = relationship(
        "User",
        foreign_keys=[participant_user_id],
        back_populates="referrals_as_participant",
    )
    assigned_counsellor = relationship(
        "User",
        foreign_keys=[assigned_counsellor_id],
        back_populates="referrals_as_counsellor",
    )
    case = relationship("ScreeningCase", back_populates="referrals")
    notes = relationship(
        "CounsellorNote",
        back_populates="referral",
        cascade="all, delete-orphan",
    )


class CounsellorNote(Base):
    __tablename__ = "counsellor_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    referral_id = Column(
        Integer,
        ForeignKey("referral_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    note_text = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    referral = relationship("ReferralTask", back_populates="notes")
    author = relationship("User")
