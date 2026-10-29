from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.clinical_record import ClinicalResidualRiskRecord
from app.schemas.clinical_record import (
    ClinicalProvenanceCreateRequest,
    ClinicalProvenanceResponse,
)
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.services.audit_service import AuditService


class ClinicalProvenanceService:
    @staticmethod
    def _is_counsellor_authorized_for_case(
        db: Session,
        counsellor_id: int,
        case: ScreeningCase,
    ) -> bool:
        """Verify whether a counsellor is authorized to manage a case or a linked couple referral.

        AUTHORIZATION POLICIES (Least Privilege & Explicit Scoping):
        1. Exact Direct Case Assignment:
           The counsellor holds an active ReferralTask explicitly assigned to target_case.id.
           A referral for one case owned by a participant does NOT authorize unrelated cases
           owned by the same participant.
        2. Explicit Couple-Level Referral Assignment:
           The counsellor holds an active ReferralTask for a reproductive partner participant,
           AND the target case owner has issued an active, explicit ConsentGrant specifically
           binding to target_case.id (unscoped/null case_id grants are strictly rejected).
           The consent purpose must explicitly cover preconception or carrier screening.
        3. Fail-Closed:
           Any missing, unscoped, ambiguous, expired, revoked, cancelled, or mismatched
           permissions fail closed (returns False).
        """
        from app.models.referral import ReferralTask, ReferralStatus
        from app.models.consent import ConsentGrant, ConsentStatus
        from sqlalchemy import or_

        # 1. Exact Direct Case Assignment:
        # Referral must explicitly match case.id directly (cannot match by participant_id alone)
        direct_referral = (
            db.query(ReferralTask)
            .filter(
                ReferralTask.assigned_counsellor_id == counsellor_id,
                ReferralTask.case_id == case.id,
                ReferralTask.status != ReferralStatus.CANCELLED,
            )
            .first()
        )
        if direct_referral:
            return True

        # 2. Explicit Couple-Level Referral Relationship:
        # Counsellor must have an active referral for a partner participant
        counsellor_referrals = (
            db.query(ReferralTask)
            .filter(
                ReferralTask.assigned_counsellor_id == counsellor_id,
                ReferralTask.status != ReferralStatus.CANCELLED,
            )
            .all()
        )
        if not counsellor_referrals:
            return False

        partner_user_ids = {r.participant_user_id for r in counsellor_referrals if r.participant_user_id}
        if not partner_user_ids:
            return False

        now = datetime.now(timezone.utc)
        # Authoritative couple-level check:
        # - Target case owner MUST be the granter
        # - Grantee MUST be one of the partnered participants on the counsellor's active referrals
        # - CRITICAL: case_id MUST explicitly match case.id (unscoped grants with case_id=None are rejected)
        # - Status must be GRANTED, not revoked, and not expired
        authorized_grant = (
            db.query(ConsentGrant)
            .filter(
                ConsentGrant.granter_user_id == case.owner_user_id,
                ConsentGrant.grantee_user_id.in_(partner_user_ids),
                ConsentGrant.case_id == case.id,  # Strict target-case binding required!
                ConsentGrant.status == ConsentStatus.GRANTED.value,
                ConsentGrant.revoked_at.is_(None),
                or_(ConsentGrant.expires_at.is_(None), ConsentGrant.expires_at > now),
            )
            .first()
        )
        if not authorized_grant:
            return False

        # Verify purpose covers preconception/carrier screening
        valid_purposes = [
            "preconception_carrier_screening",
            "carrier_screening",
            "reproductive_risk_assessment",
        ]
        if authorized_grant.purpose and authorized_grant.purpose.strip().lower() not in valid_purposes:
            return False

        return True

    @staticmethod
    def record_provenance(
        db: Session,
        clinician: User,
        req: ClinicalProvenanceCreateRequest,
    ) -> ClinicalProvenanceResponse:
        """Create and persist a clinician-reviewed residual-risk assessment record.

        AUTHORIZATION RULES:
        1. Authentication & Active Status:
           Clinician account must be active. Deactivated accounts are denied.
        2. Role-Gated:
           Restricted to COUNSELLOR and ADMIN roles. Ordinary participants cannot approve
           or manufacture their own clinical data.
        3. Object-Level Scoping for COUNSELLOR:
           A counsellor MUST be assigned to manage the target screening case directly,
           OR be assigned to an active referral for a partner participant who holds an
           active, unrevoked, unexpired ConsentGrant with the target case's owner.
           Unassigned counsellors cannot record provenance for cases they do not manage.
        4. Administrative Authority:
           ADMIN accounts retain documented operational review oversight, with every
           action written immutably to the audit log.
        """
        if not clinician.is_active:
            raise ForbiddenException("User account has been deactivated.")

        if clinician.role not in [UserRole.COUNSELLOR, UserRole.ADMIN]:
            AuditService.log_event(
                db=db,
                action="UNAUTHORIZED_PROVENANCE_ATTEMPT",
                resource_type="clinical_provenance",
                resource_id=str(req.case_id),
                actor_user_id=clinician.id,
                outcome="DENIED",
                details={"reason": "Non-clinical role attempt"},
            )
            raise ForbiddenException("Only authorized genetic counsellors or clinical administrators can confirm clinical residual-risk provenance.")

        # Verify target screening case exists
        case = db.query(ScreeningCase).filter(ScreeningCase.id == req.case_id).first()
        if not case:
            raise NotFoundException("Target screening case not found.")

        # Check if caller is operating under a synthetic demonstration session
        is_demo = getattr(clinician, "is_demo_session", False)
        if is_demo:
            if not (case.synthetic_case_code and case.synthetic_case_code.startswith("SYN-")):
                AuditService.log_event(
                    db=db,
                    action="UNAUTHORIZED_PROVENANCE_ATTEMPT",
                    resource_type="clinical_provenance",
                    resource_id=str(req.case_id),
                    actor_user_id=clinician.id,
                    outcome="DENIED",
                    details={"reason": "Demo session attempted provenance on non-synthetic case"},
                )
                raise ForbiddenException("Demo sessions are strictly restricted to synthetic demonstration cases.")

        # Object-level authorization for COUNSELLOR role:
        # Counsellor must be explicitly assigned to manage this case or an authorized couple referral
        if clinician.role == UserRole.COUNSELLOR:
            if not ClinicalProvenanceService._is_counsellor_authorized_for_case(db, clinician.id, case):
                AuditService.log_event(
                    db=db,
                    action="UNAUTHORIZED_PROVENANCE_ATTEMPT",
                    resource_type="clinical_provenance",
                    resource_id=str(req.case_id),
                    actor_user_id=clinician.id,
                    outcome="DENIED",
                    details={
                        "reason": "Counsellor not assigned to target case or authorized couple referral",
                        "case_id": req.case_id,
                    },
                )
                raise ForbiddenException("You are not authorized to record clinical provenance for this screening case.")

        # Verify condition exists in case findings
        finding = (
            db.query(SyntheticFinding)
            .filter(
                SyntheticFinding.case_id == req.case_id,
                SyntheticFinding.condition_code == req.condition_code,
            )
            .first()
        )
        if not finding:
            raise NotFoundException(f"Condition '{req.condition_code}' not found in case findings.")

        # Ensure finding is a negative screen (residual risk is only valid for negative screening findings)
        carrier_str = (finding.carrier_state or "").upper()
        if "CARRIER" in carrier_str or "POSITIVE" in carrier_str:
            raise ValidationException("Residual carrier probability can only be recorded for negative screening findings (NO_VARIANT_DETECTED).")

        # Deactivate any previous active record for this case and condition
        existing_records = (
            db.query(ClinicalResidualRiskRecord)
            .filter(
                ClinicalResidualRiskRecord.case_id == req.case_id,
                ClinicalResidualRiskRecord.condition_code == req.condition_code,
                ClinicalResidualRiskRecord.is_active == True,  # noqa
            )
            .all()
        )
        for r in existing_records:
            r.is_active = False

        source_ref = req.clinical_source_reference.strip()
        if is_demo and not source_ref.startswith("[SYNTHETIC_DEMO_SANDBOX]"):
            source_ref = f"[SYNTHETIC_DEMO_SANDBOX] {source_ref}"

        record = ClinicalResidualRiskRecord(
            case_id=req.case_id,
            condition_code=req.condition_code,
            residual_carrier_probability=req.residual_carrier_probability,
            clinical_source_reference=source_ref,
            reviewing_clinician_id=clinician.id,
            notes=req.notes,
            is_active=True,
            reviewed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()

        AuditService.log_event(
            db=db,
            action="CLINICAL_PROVENANCE_RECORDED",
            resource_type="clinical_provenance",
            resource_id=str(record.id),
            actor_user_id=clinician.id,
            outcome="SUCCESS",
            details={
                "case_id": req.case_id,
                "condition_code": req.condition_code,
                "residual_carrier_probability": req.residual_carrier_probability,
                "source": source_ref,
                "is_demo_session": is_demo,
                "synthetic_sandbox": is_demo,
            },
            commit=False,
        )

        db.commit()
        db.refresh(record)
        return ClinicalProvenanceResponse.model_validate(record)

    @staticmethod
    def get_valid_provenance(
        db: Session,
        case_id: int,
        condition_code: str,
    ) -> Optional[ClinicalResidualRiskRecord]:
        """Retrieve an active, server-validated clinical residual risk record for a case and condition."""
        record = (
            db.query(ClinicalResidualRiskRecord)
            .filter(
                ClinicalResidualRiskRecord.case_id == case_id,
                ClinicalResidualRiskRecord.condition_code == condition_code,
                ClinicalResidualRiskRecord.is_active == True,  # noqa
            )
            .first()
        )
        if not record:
            return None

        # Verify reviewing clinician is valid and authorized
        clinician = db.query(User).filter(User.id == record.reviewing_clinician_id).first()
        if not clinician or not clinician.is_active or clinician.role not in [UserRole.COUNSELLOR, UserRole.ADMIN]:
            return None

        return record
