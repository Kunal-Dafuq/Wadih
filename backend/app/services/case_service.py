from typing import List
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase
from app.models.referral import ReferralTask
from app.schemas.screening import (
    ScreeningCaseListItem,
    ScreeningCaseDetailResponse,
    SyntheticFindingResponse,
)
from app.core.exceptions import NotFoundException, ForbiddenException


class CaseService:
    @staticmethod
    def get_cases_for_user(
        db: Session, user: User, skip: int = 0, limit: int = 20
    ) -> List[ScreeningCaseListItem]:
        """Retrieve synthetic screening cases owned by the authenticated participant."""
        is_demo = getattr(user, "is_demo_session", False)
        if user.role == UserRole.COUNSELLOR:
            # Genetic counsellor can view cases linked to active referrals assigned to them
            assigned_case_ids = (
                db.query(ReferralTask.case_id)
                .filter(ReferralTask.assigned_counsellor_id == user.id)
                .subquery()
            )
            query = db.query(ScreeningCase).filter(ScreeningCase.id.in_(assigned_case_ids))
        else:
            # Participant can ONLY view their own cases
            query = db.query(ScreeningCase).filter(ScreeningCase.owner_user_id == user.id)

        # Demo sessions strictly view synthetic demonstration cases
        if is_demo:
            query = query.filter(ScreeningCase.synthetic_case_code.like("SYN-%"))

        cases = query.offset(skip).limit(limit).all()

        items = []
        for c in cases:
            items.append(
                ScreeningCaseListItem(
                    id=c.id,
                    synthetic_case_code=c.synthetic_case_code,
                    status=c.status,
                    screening_scope_label=c.screening_scope_label,
                    source_reviewed=c.source_reviewed,
                    findings_count=len(c.findings),
                    created_at=c.created_at,
                )
            )
        return items

    @staticmethod
    def get_case_detail_for_user(
        db: Session, case_id: int, user: User
    ) -> ScreeningCaseDetailResponse:
        """Retrieve full case details ensuring strict participant ownership or counsellor assignment."""
        case = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
        if not case:
            raise NotFoundException("Screening case not found.")

        # Demo session isolation: Demo sessions are strictly barred from non-synthetic cases
        if getattr(user, "is_demo_session", False):
            if not (case.synthetic_case_code and case.synthetic_case_code.startswith("SYN-")):
                raise NotFoundException("Screening case not found.")

        # Check access permission
        is_owner = case.owner_user_id == user.id
        is_assigned_counsellor = False
        if user.role == UserRole.COUNSELLOR:
            is_assigned_counsellor = (
                db.query(ReferralTask)
                .filter(
                    ReferralTask.case_id == case_id,
                    ReferralTask.assigned_counsellor_id == user.id,
                )
                .first()
                is not None
            )

        # Cross-account sharing is governed by Niharika's consent engine
        has_full_report_consent = False
        if not is_owner and not is_assigned_counsellor:
            from datetime import datetime, timezone
            from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
            from app.services.audit_service import AuditService

            grant = (
                db.query(ConsentGrant)
                .filter(
                    ConsentGrant.granter_user_id == case.owner_user_id,
                    ConsentGrant.grantee_user_id == user.id,
                    ConsentGrant.status == ConsentStatus.GRANTED.value,
                    ConsentGrant.scope == ConsentScope.FULL_REPORT.value,
                    ConsentGrant.revoked_at.is_(None),
                )
                .first()
            )
            if grant:
                now = datetime.now(timezone.utc)
                exp = grant.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if not exp or exp >= now:
                    has_full_report_consent = True
                    AuditService.log_event(
                        db=db,
                        action="SENSITIVE_RESULT_ACCESSED",
                        resource_type="screening_case",
                        resource_id=str(case.id),
                        actor_user_id=user.id,
                        outcome="SUCCESS",
                        details={"scope": "full_report", "access_type": "consented_case_detail"},
                    )

        if not is_owner and not is_assigned_counsellor and not has_full_report_consent:
            raise NotFoundException("Screening case not found.")

        findings_resp = [
            SyntheticFindingResponse.model_validate(f) for f in case.findings
        ]

        return ScreeningCaseDetailResponse(
            id=case.id,
            synthetic_case_code=case.synthetic_case_code,
            status=case.status,
            screening_scope_label=case.screening_scope_label,
            source_reviewed=case.source_reviewed,
            created_at=case.created_at,
            findings=findings_resp,
        )
