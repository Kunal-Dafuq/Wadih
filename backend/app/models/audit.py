from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "shared_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, index=True, nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=False)
    outcome = Column(String(32), default="SUCCESS", nullable=False)
    details = Column(Text, nullable=True)
    request_id = Column(String(64), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
