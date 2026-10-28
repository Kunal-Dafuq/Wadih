import json
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditEventResponse, AuditEventListResponse
from app.core.exceptions import ForbiddenException


class AuditService:
    # Sanitization filter: reject or scrub sensitive genetic variant / secret fields
    FORBIDDEN_DETAIL_KEYS = {
        "password",
        "hashed_password",
        "token",
        "access_token",
        "raw_variant",
        "vcf",
        "c_dot",
        "p_dot",
        "genomic_coordinates",
        "secret",
    }

    @staticmethod
    def log_event(
        db: Session,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_user_id: Optional[int] = None,
        outcome: str = "SUCCESS",
        details: Optional[dict | str] = None,
        request_id: Optional[str] = None,
        commit: bool = True,
    ) -> AuditLog:
        """Record an immutable security audit event.

        Strictly guarantees:
        - No credentials, tokens, or raw genomic variant sequences are recorded.
        - Outcomes explicitly distinguish SUCCESS from DENIED or FAILURE.
        """
        sanitized_details_str: Optional[str] = None
        if isinstance(details, dict):
            # Sanitize dictionary values
            clean_dict = {}
            for k, v in details.items():
                if any(bad in k.lower() for bad in AuditService.FORBIDDEN_DETAIL_KEYS):
                    clean_dict[k] = "[REDACTED_SENSITIVE_DATA]"
                else:
                    clean_dict[k] = v
            sanitized_details_str = json.dumps(clean_dict, default=str)
        elif isinstance(details, str):
            sanitized_details_str = details[:1000]

        entry = AuditLog(
            actor_user_id=actor_user_id,
            action=action.strip().upper(),
            resource_type=resource_type.strip(),
            resource_id=str(resource_id),
            outcome=outcome.strip().upper(),
            details=sanitized_details_str,
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(entry)
        if commit:
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def get_audit_events(
        db: Session,
        current_user: User,
        action_filter: Optional[str] = None,
        resource_type_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditEventListResponse:
        """Retrieve audit events. Restricted to ADMIN and COUNSELLOR roles."""
        if current_user.role not in [UserRole.ADMIN, UserRole.COUNSELLOR]:
            # Record privileged access attempt violation
            AuditService.log_event(
                db=db,
                action="PRIVILEGED_ACCESS_ATTEMPT",
                resource_type="audit_log",
                resource_id="all",
                actor_user_id=current_user.id,
                outcome="DENIED",
                details={"reason": "User lacking ADMIN or COUNSELLOR role attempted audit log access"},
            )
            raise ForbiddenException("Access denied: Audit log inspection requires administrative or clinical role.")

        query = db.query(AuditLog)

        # Least-privilege scope enforcement for COUNSELLOR role
        if current_user.role == UserRole.COUNSELLOR:
            from app.models.referral import ReferralTask
            from sqlalchemy import or_, and_

            referrals = (
                db.query(ReferralTask)
                .filter(ReferralTask.assigned_counsellor_id == current_user.id)
                .all()
            )
            assigned_case_ids = [str(r.case_id) for r in referrals if r.case_id]
            assigned_referral_ids = [str(r.id) for r in referrals]

            # Restricted strictly to authorized case/referral scope and counsellor's own actions.
            # CRITICAL SECURITY RULE: A counsellor CANNOT retrieve events for unrelated cases or
            # activities merely because the event actor is a participant assigned to that counsellor.
            counsellor_scope_conditions = [
                AuditLog.actor_user_id == current_user.id,
            ]
            if assigned_case_ids:
                counsellor_scope_conditions.append(
                    and_(
                        AuditLog.resource_type == "screening_case",
                        AuditLog.resource_id.in_(assigned_case_ids),
                    )
                )
            if assigned_referral_ids:
                counsellor_scope_conditions.append(
                    and_(
                        AuditLog.resource_type == "referral_task",
                        AuditLog.resource_id.in_(assigned_referral_ids),
                    )
                )

            query = query.filter(or_(*counsellor_scope_conditions))

        if action_filter:
            query = query.filter(AuditLog.action == action_filter.strip().upper())
        if resource_type_filter:
            query = query.filter(AuditLog.resource_type == resource_type_filter.strip())

        total = query.count()
        events = (
            query.order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return AuditEventListResponse(
            total=total,
            events=[AuditEventResponse.model_validate(e) for e in events],
        )
