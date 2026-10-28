from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, event
from sqlalchemy.orm import Session

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


@event.listens_for(AuditLog, "before_update")
def _prevent_audit_log_update(mapper, connection, target):
    """Enforce ORM mapper-level immutability: Audit records must never be updated."""
    raise RuntimeError("AuditLog records are append-only and immutable. Updates are strictly prohibited.")


@event.listens_for(AuditLog, "before_delete")
def _prevent_audit_log_delete(mapper, connection, target):
    """Enforce ORM mapper-level immutability: Audit records must never be deleted."""
    raise RuntimeError("AuditLog records are append-only and immutable. Deletions are strictly prohibited.")


@event.listens_for(Session, "do_orm_execute")
def _prevent_audit_log_bulk_mutation(orm_execute_state):
    """Enforce Session-level bulk immutability: Intercept ORM bulk UPDATE and DELETE statements."""
    if orm_execute_state.is_update or orm_execute_state.is_delete:
        for mapper in orm_execute_state.all_mappers:
            if mapper and issubclass(mapper.class_, AuditLog):
                op_name = "Bulk UPDATE" if orm_execute_state.is_update else "Bulk DELETE"
                raise RuntimeError(
                    f"AuditLog records are append-only and immutable. {op_name} statements via ORM are strictly prohibited."
                )


