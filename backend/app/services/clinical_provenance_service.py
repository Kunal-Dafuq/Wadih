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
    def record_provenance(
        db: Session,
        clinician: User,
        req: ClinicalProvenanceCreateRequest,
    ) -> ClinicalProvenanceResponse:
        """Create and persist a clinician-reviewed residual-risk assessment record.

        AUTHORIZATION:
        Restricted to COUNSELLOR and ADMIN roles. Ordinary participants cannot approve
        or manufacture their own clinical data.
        """
        if clinician.role not in [UserRole.COUNSELLOR, UserRole.ADMIN]:
            AuditService.log_event(
                db=db,
                action="UNAUTHORIZED_PROVENANCE_ATTEMPT",
                resource_type="clinical_provenance",
                resource_id=str(req.case_id),
                actor_user_id=clinician.id,
                outcome="DENIED",
                details={"condition_code": req.condition_code, "reason": "Non-clinical role attempt"},
            )
            raise ForbiddenException("Only authorized genetic counsellors or clinical administrators can confirm clinical residual-risk provenance.")

        # Verify target screening case exists
        case = db.query(ScreeningCase).filter(ScreeningCase.id == req.case_id).first()
        if not case:
            raise NotFoundException("Target screening case not found.")

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

        record = ClinicalResidualRiskRecord(
            case_id=req.case_id,
            condition_code=req.condition_code,
            residual_carrier_probability=req.residual_carrier_probability,
            clinical_source_reference=req.clinical_source_reference.strip(),
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
                "source": req.clinical_source_reference.strip(),
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
