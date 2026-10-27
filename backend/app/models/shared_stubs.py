"""Shared entity definitions and contract placeholders.

NOTICE:
Advanced business logic for consent grants, partner-sharing access enforcement,
revocation lifecycle, and audit policy enforcement is strictly owned by
Niharika (niharika/advanced-backend).
These minimal definitions exist solely to document shared schema contracts without
implementing unassigned business logic.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from app.db.base import Base


class SharedConsentGrantStub(Base):
    """Minimal contract placeholder for Consent Grants (Owned by Niharika)."""

    __tablename__ = "shared_consent_grants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    granter_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    grantee_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scope = Column(String(64), nullable=False)  # e.g., 'carrier_status_only', 'full_report'
    status = Column(String(32), default="ACTIVE", nullable=False)  # e.g., 'ACTIVE', 'REVOKED'
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SharedAuditLogStub(Base):
    """Minimal contract placeholder for Security Audit (Owned by Niharika)."""

    __tablename__ = "shared_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
