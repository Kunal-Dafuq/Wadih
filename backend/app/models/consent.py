import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class ConsentStatus(str, enum.Enum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ConsentScope(str, enum.Enum):
    CARRIER_STATUS_ONLY = "carrier_status_only"
    SUMMARY_ONLY = "summary_only"
    FULL_REPORT = "full_report"


class ConsentGrant(Base):
    __tablename__ = "shared_consent_grants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    granter_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    grantee_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    scope = Column(String(64), default=ConsentScope.SUMMARY_ONLY.value, nullable=False)
    status = Column(String(32), default=ConsentStatus.PENDING.value, nullable=False)
    purpose = Column(String(128), default="preconception_carrier_screening", nullable=True)
    terms_version = Column(String(32), default="v1.0", nullable=True)
    case_id = Column(
        Integer,
        ForeignKey("screening_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    granter = relationship("User", foreign_keys=[granter_user_id])
    grantee = relationship("User", foreign_keys=[grantee_user_id])
    case = relationship("ScreeningCase")
