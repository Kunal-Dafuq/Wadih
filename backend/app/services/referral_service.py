from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase
from app.models.referral import ReferralTask, ReferralStatus, CounsellorNote
from app.schemas.referral import (
    ReferralTaskCreateRequest,
    ReferralTaskResponse,
    CounsellorNoteResponse,
    ReferralStatusUpdateRequest,
    CounsellorNoteCreateRequest,
)
from app.core.exceptions import NotFoundException, ForbiddenException, ValidationException


class ReferralService:
    @staticmethod
    def create_referral_task(
        db: Session, user: User, request_data: ReferralTaskCreateRequest
    ) -> ReferralTaskResponse:
        """Create a participant-owned simulated referral task linked to their screening case."""
        # 1. Validate that the case exists and is owned by the authenticated participant
        case = db.query(ScreeningCase).filter(ScreeningCase.id == request_data.case_id).first()
        if not case or case.owner_user_id != user.id:
            raise NotFoundException("Screening case not found.")

        # 2. Assign default demo genetic counsellor if one exists
        default_counsellor = (
            db.query(User).filter(User.role == UserRole.COUNSELLOR, User.is_active == True).first()
        )
        counsellor_id = default_counsellor.id if default_counsellor else None

        referral = ReferralTask(
            participant_user_id=user.id,
            case_id=case.id,
            assigned_counsellor_id=counsellor_id,
            reason_code=request_data.reason_code.strip(),
            status=ReferralStatus.PENDING,
            urgency_level=request_data.urgency_level.strip() if request_data.urgency_level else "ROUTINE",
        )
        db.add(referral)
        db.commit()
        db.refresh(referral)

        return ReferralService._format_referral_response(referral)

    @staticmethod
    def get_referrals_for_user(
        db: Session, user: User, skip: int = 0, limit: int = 50
    ) -> List[ReferralTaskResponse]:
        """Retrieve simulated referrals owned by participant or assigned to counsellor."""
        if user.role == UserRole.COUNSELLOR:
            referrals = (
                db.query(ReferralTask)
                .filter(ReferralTask.assigned_counsellor_id == user.id)
                .order_by(ReferralTask.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
        else:
            referrals = (
                db.query(ReferralTask)
                .filter(ReferralTask.participant_user_id == user.id)
                .order_by(ReferralTask.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )

        return [ReferralService._format_referral_response(r) for r in referrals]

    @staticmethod
    def get_referral_by_id(
        db: Session, referral_id: int, user: User
    ) -> ReferralTaskResponse:
        """Retrieve a specific referral task enforcing access boundaries."""
        referral = db.query(ReferralTask).filter(ReferralTask.id == referral_id).first()
        if not referral:
            raise NotFoundException("Referral task not found.")

        is_owner = referral.participant_user_id == user.id
        is_assigned_counsellor = (
            user.role == UserRole.COUNSELLOR and referral.assigned_counsellor_id == user.id
        )

        if not is_owner and not is_assigned_counsellor:
            raise NotFoundException("Referral task not found.")

        return ReferralService._format_referral_response(referral)

    @staticmethod
    def update_referral_status(
        db: Session,
        referral_id: int,
        user: User,
        status_update: ReferralStatusUpdateRequest,
    ) -> ReferralTaskResponse:
        """Update referral status (counsellor or authorized participant workflow)."""
        referral = db.query(ReferralTask).filter(ReferralTask.id == referral_id).first()
        if not referral:
            raise NotFoundException("Referral task not found.")

        is_owner = referral.participant_user_id == user.id
        is_assigned_counsellor = (
            user.role == UserRole.COUNSELLOR and referral.assigned_counsellor_id == user.id
        )

        if not is_owner and not is_assigned_counsellor:
            raise NotFoundException("Referral task not found.")

        # Participants can only cancel their own pending referrals
        if is_owner and not is_assigned_counsellor:
            if status_update.status != "CANCELLED":
                raise ForbiddenException("Participants can only cancel pending referrals.")

        try:
            new_status = ReferralStatus(status_update.status)
        except ValueError:
            raise ValidationException(f"Invalid status '{status_update.status}'.")

        referral.status = new_status
        referral.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(referral)

        return ReferralService._format_referral_response(referral)

    @staticmethod
    def add_note_to_referral(
        db: Session,
        referral_id: int,
        user: User,
        note_data: CounsellorNoteCreateRequest,
    ) -> CounsellorNoteResponse:
        """Add a counsellor note to a referral task."""
        referral = db.query(ReferralTask).filter(ReferralTask.id == referral_id).first()
        if not referral:
            raise NotFoundException("Referral task not found.")

        if user.role != UserRole.COUNSELLOR or referral.assigned_counsellor_id != user.id:
            raise ForbiddenException("Only the assigned genetic counsellor may author clinical notes.")

        note = CounsellorNote(
            referral_id=referral.id,
            author_user_id=user.id,
            note_text=note_data.note_text.strip(),
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        author_name = (
            user.profile.display_name if user.profile else user.email.split("@")[0]
        )

        return CounsellorNoteResponse(
            id=note.id,
            referral_id=note.referral_id,
            author_user_id=note.author_user_id,
            author_name=author_name,
            note_text=note.note_text,
            created_at=note.created_at,
        )

    @staticmethod
    def _format_referral_response(referral: ReferralTask) -> ReferralTaskResponse:
        case_code = referral.case.synthetic_case_code if referral.case else "SYN-UNKNOWN"

        counsellor_name = None
        if referral.assigned_counsellor:
            counsellor_name = (
                referral.assigned_counsellor.profile.display_name
                if referral.assigned_counsellor.profile
                else referral.assigned_counsellor.email.split("@")[0]
            )

        notes_resp = []
        for n in referral.notes:
            auth_name = (
                n.author.profile.display_name
                if n.author and n.author.profile
                else (n.author.email.split("@")[0] if n.author else "Counsellor")
            )
            notes_resp.append(
                CounsellorNoteResponse(
                    id=n.id,
                    referral_id=n.referral_id,
                    author_user_id=n.author_user_id,
                    author_name=auth_name,
                    note_text=n.note_text,
                    created_at=n.created_at,
                )
            )

        status_str = (
            referral.status.value
            if hasattr(referral.status, "value")
            else str(referral.status)
        )

        return ReferralTaskResponse(
            id=referral.id,
            participant_user_id=referral.participant_user_id,
            case_id=referral.case_id,
            case_code=case_code,
            assigned_counsellor_id=referral.assigned_counsellor_id,
            assigned_counsellor_name=counsellor_name,
            reason_code=referral.reason_code,
            status=status_str,
            urgency_level=referral.urgency_level,
            created_at=referral.created_at,
            updated_at=referral.updated_at,
            notes=notes_resp,
        )
