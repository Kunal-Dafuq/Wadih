from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.referral import ReferralTask, ReferralStatus
from app.schemas.referral import ReferralTaskResponse
from app.services.referral_service import ReferralService
from app.services.audit_service import AuditService
from app.core.exceptions import NotFoundException, ValidationException


class EscalationRequest(BaseModel):
    case_id: int
    trigger_reason: str
    clinical_rationale: Optional[str] = None
    urgency_level: str = "ROUTINE"

    model_config = ConfigDict(from_attributes=True)


class EscalationResultResponse(BaseModel):
    referral_id: int
    case_id: int
    synthetic_case_code: str
    participant_user_id: int
    status: str
    urgency_level: str
    trigger_reason: str
    assigned_counsellor_name: Optional[str] = None
    guidance_note: str = (
        "Educational genetic counselling referral initiated. "
        "A certified genetic counsellor will review synthetic screening findings to address uncertain findings, "
        "unsupported inheritance patterns, or joint carrier implications."
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EscalationService:
    SUPPORTED_ESCALATION_REASONS = {
        "VARIANT_OF_UNCERTAIN_SIGNIFICANCE": "Variant of uncertain significance requires professional variant re-curation.",
        "UNSUPPORTED_INHERITANCE_PATTERN": "Non-recessive inheritance pattern requires specialized clinical pedigree analysis.",
        "DUAL_CARRIER_AUTOSOMAL_RECESSIVE": "Both partners carry pathogenic variants for the same autosomal recessive condition.",
        "AFFECTED_PARTNER_CLINICAL_REVIEW": "One or both partners are identified as clinically affected with genetic condition.",
        "INCOMPLETE_OR_CONFLICTING_FINDINGS": "Inconclusive or contradictory findings require laboratory clarification.",
        "CLINICIAN_REVIEW_REQUIRED": "Finding flagged for mandatory clinical review before final educational disclosure.",
    }

    @staticmethod
    def evaluate_case_escalation_needs(
        db: Session, case_id: int, user: User
    ) -> List[str]:
        """Inspect synthetic findings in a case and identify clinical escalation triggers deterministically."""
        case = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
        if not case:
            raise NotFoundException("Screening case not found.")

        # Demo session isolation: barred from non-synthetic cases
        if getattr(user, "is_demo_session", False):
            if not (case.synthetic_case_code and case.synthetic_case_code.startswith("SYN-")):
                raise NotFoundException("Screening case not found.")

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

        if not is_owner and not is_assigned_counsellor:
            raise NotFoundException("Screening case not found.")

        reasons = []
        for finding in case.findings:
            carrier_str = (finding.carrier_state or "").upper()
            class_str = (finding.classification_state or "").upper()
            mode_str = (finding.inheritance_mode or "").upper()

            if "UNCERTAIN" in carrier_str or "VUS" in class_str or "INCONCLUSIVE" in carrier_str:
                reasons.append("VARIANT_OF_UNCERTAIN_SIGNIFICANCE")

            if mode_str and "AUTOSOMAL_RECESSIVE" not in mode_str:
                reasons.append("UNSUPPORTED_INHERITANCE_PATTERN")

            if not finding.reviewed_flag:
                reasons.append("CLINICIAN_REVIEW_REQUIRED")

            if "AFFECTED" in carrier_str:
                reasons.append("AFFECTED_PARTNER_CLINICAL_REVIEW")

        return list(set(reasons))

    @staticmethod
    def create_escalation(
        db: Session, user: User, request_data: EscalationRequest
    ) -> EscalationResultResponse:
        """Create a structured clinical escalation and connect to ReferralTask."""
        case = db.query(ScreeningCase).filter(ScreeningCase.id == request_data.case_id).first()
        if not case or case.owner_user_id != user.id:
            raise NotFoundException("Screening case not found.")

        # Demo session isolation: barred from non-synthetic cases
        if getattr(user, "is_demo_session", False):
            if not (case.synthetic_case_code and case.synthetic_case_code.startswith("SYN-")):
                raise NotFoundException("Screening case not found.")

        reason = request_data.trigger_reason.strip()
        if reason not in EscalationService.SUPPORTED_ESCALATION_REASONS:
            # Allow custom with prefix
            if not reason.startswith("CLINICAL_"):
                reason = f"CLINICAL_{reason}"

        # Assign default available counsellor if exists
        counsellor = (
            db.query(User).filter(User.role == UserRole.COUNSELLOR, User.is_active == True).first()
        )
        counsellor_id = counsellor.id if counsellor else None

        urgency = request_data.urgency_level.strip().upper()
        if urgency not in ["ROUTINE", "PRIORITY", "URGENT"]:
            urgency = "ROUTINE"

        referral = ReferralTask(
            participant_user_id=user.id,
            case_id=case.id,
            assigned_counsellor_id=counsellor_id,
            reason_code=reason,
            status=ReferralStatus.PENDING,
            urgency_level=urgency,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(referral)
        db.flush()

        # Audit event in same atomic transaction
        AuditService.log_event(
            db=db,
            action="COUNSELLOR_ESCALATION_CREATED",
            resource_type="referral_task",
            resource_id=str(referral.id),
            actor_user_id=user.id,
            outcome="SUCCESS",
            details={
                "case_id": case.id,
                "reason_code": reason,
                "urgency_level": urgency,
            },
            commit=False,
        )
        db.commit()
        db.refresh(referral)

        counsellor_name = None
        if counsellor and counsellor.profile:
            counsellor_name = counsellor.profile.display_name

        return EscalationResultResponse(
            referral_id=referral.id,
            case_id=case.id,
            synthetic_case_code=case.synthetic_case_code,
            participant_user_id=user.id,
            status=referral.status.value if hasattr(referral.status, "value") else str(referral.status),
            urgency_level=referral.urgency_level,
            trigger_reason=referral.reason_code,
            assigned_counsellor_name=counsellor_name,
            created_at=referral.created_at,
        )
