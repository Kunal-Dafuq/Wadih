from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.schemas.consent import (
    ConsentGrantCreateRequest,
    SharingInvitationRequest,
    ConsentGrantResponse,
    SharedCaseSummaryResponse,
    SharedFindingSummary,
)
from app.services.audit_service import AuditService
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    ConsentRequiredException,
)


class ConsentService:
    @staticmethod
    def create_consent_grant(
        db: Session, granter: User, request_data: ConsentGrantCreateRequest
    ) -> ConsentGrantResponse:
        """Create an explicit consent grant from the authenticated participant."""
        # Resolve grantee
        grantee = None
        if request_data.grantee_user_id:
            grantee = db.query(User).filter(User.id == request_data.grantee_user_id).first()
        elif request_data.grantee_email:
            grantee = db.query(User).filter(User.email == request_data.grantee_email.strip().lower()).first()

        if not grantee:
            raise NotFoundException("Grantee user not found.")

        if grantee.id == granter.id:
            raise ValidationException("A user cannot issue a consent grant to themselves.")

        # Demo session isolation: Demo sessions can only grant consent to synthetic demo accounts
        if getattr(granter, "is_demo_session", False):
            if not grantee.email.endswith("@wadih.demo"):
                raise ForbiddenException("Demo sessions are strictly restricted to synthetic demonstration accounts.")

        # Validate case if specified
        if request_data.case_id:
            case = db.query(ScreeningCase).filter(ScreeningCase.id == request_data.case_id).first()
            if not case or case.owner_user_id != granter.id:
                raise NotFoundException("Specified screening case does not exist or is not owned by caller.")

        expires_at = None
        if request_data.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=request_data.expires_in_days)

        grant = ConsentGrant(
            granter_user_id=granter.id,
            grantee_user_id=grantee.id,
            scope=request_data.scope.value,
            status=ConsentStatus.GRANTED.value,  # Granter directly granting
            purpose=request_data.purpose.strip(),
            terms_version=request_data.terms_version.strip(),
            case_id=request_data.case_id,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
        db.add(grant)
        db.flush()

        # Audit Event in same atomic transaction
        AuditService.log_event(
            db=db,
            action="CONSENT_GRANTED",
            resource_type="consent_grant",
            resource_id=str(grant.id),
            actor_user_id=granter.id,
            outcome="SUCCESS",
            details={
                "grantee_id": grantee.id,
                "scope": grant.scope,
                "purpose": grant.purpose,
                "case_id": grant.case_id,
            },
            commit=False,
        )
        db.commit()
        db.refresh(grant)

        return ConsentService._format_consent_response(grant)

    @staticmethod
    def create_sharing_request(
        db: Session, requester: User, request_data: SharingInvitationRequest
    ) -> ConsentGrantResponse:
        """Create a partner-sharing invitation request.

        Crucial security guarantee:
        A partner invitation does NOT grant immediate access to findings.
        Status is initialized as PENDING and must be explicitly approved by the granter.
        """
        partner = (
            db.query(User)
            .filter(User.email == request_data.partner_email.strip().lower())
            .first()
        )
        if not partner:
            raise NotFoundException("Invited partner account not found. Partner must create an account first.")

        if partner.id == requester.id:
            raise ValidationException("Cannot create a sharing request targeting yourself.")

        # Demo session isolation: Demo sessions can only issue partner invitations to synthetic demo accounts
        if getattr(requester, "is_demo_session", False):
            if not request_data.partner_email.strip().lower().endswith("@wadih.demo"):
                raise ForbiddenException("Demo sessions are strictly restricted to synthetic demonstration accounts.")

        # Case reference check
        if request_data.case_id:
            case = db.query(ScreeningCase).filter(ScreeningCase.id == request_data.case_id).first()
            if not case or case.owner_user_id != requester.id:
                raise NotFoundException("Screening case not found.")

        # Request where requester invites partner to share, meaning requester authorizes partner to view
        grant = ConsentGrant(
            granter_user_id=requester.id,
            grantee_user_id=partner.id,
            scope=request_data.scope.value,
            status=ConsentStatus.PENDING.value,
            purpose=request_data.purpose.strip(),
            terms_version="v1.0",
            case_id=request_data.case_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(grant)
        db.flush()

        AuditService.log_event(
            db=db,
            action="SHARING_REQUEST_CREATED",
            resource_type="consent_grant",
            resource_id=str(grant.id),
            actor_user_id=requester.id,
            outcome="SUCCESS",
            details={
                "grantee_user_id": partner.id,
                "scope": grant.scope,
                "status": "PENDING",
            },
            commit=False,
        )
        db.commit()
        db.refresh(grant)

        return ConsentService._format_consent_response(grant)

    @staticmethod
    def approve_consent(db: Session, consent_id: int, user: User) -> ConsentGrantResponse:
        """Explicitly approve a pending consent grant. Only the granter may approve."""
        grant = db.query(ConsentGrant).filter(ConsentGrant.id == consent_id).first()
        if not grant:
            raise NotFoundException("Consent grant not found.")

        # Object-level access control: only the granter can authorize disclosure
        if grant.granter_user_id != user.id:
            AuditService.log_event(
                db=db,
                action="CONSENT_APPROVAL_UNAUTHORIZED",
                resource_type="consent_grant",
                resource_id=str(consent_id),
                actor_user_id=user.id,
                outcome="DENIED",
                details={"reason": "User is not the granting participant for this consent record."},
            )
            raise ForbiddenException("Only the granting participant can approve consent.")

        grant.status = ConsentStatus.GRANTED.value
        AuditService.log_event(
            db=db,
            action="CONSENT_GRANTED",
            resource_type="consent_grant",
            resource_id=str(grant.id),
            actor_user_id=user.id,
            outcome="SUCCESS",
            details={"grantee_id": grant.grantee_user_id, "scope": grant.scope},
            commit=False,
        )
        db.commit()
        db.refresh(grant)

        return ConsentService._format_consent_response(grant)

    @staticmethod
    def revoke_consent(db: Session, consent_id: int, user: User) -> ConsentGrantResponse:
        """Revoke a previously granted consent. Subsequent access is immediately blocked."""
        grant = db.query(ConsentGrant).filter(ConsentGrant.id == consent_id).first()
        if not grant:
            raise NotFoundException("Consent grant not found.")

        # Object-level access control: only the granter can revoke their own consent
        if grant.granter_user_id != user.id:
            AuditService.log_event(
                db=db,
                action="CONSENT_REVOKE_UNAUTHORIZED",
                resource_type="consent_grant",
                resource_id=str(consent_id),
                actor_user_id=user.id,
                outcome="DENIED",
                details={"reason": "Caller attempted to revoke consent granted by another user."},
            )
            raise ForbiddenException("Only the granting participant can revoke consent.")

        grant.status = ConsentStatus.REVOKED.value
        grant.revoked_at = datetime.now(timezone.utc)
        AuditService.log_event(
            db=db,
            action="CONSENT_REVOKED",
            resource_type="consent_grant",
            resource_id=str(grant.id),
            actor_user_id=user.id,
            outcome="SUCCESS",
            details={"grantee_id": grant.grantee_user_id, "scope": grant.scope},
            commit=False,
        )
        db.commit()
        db.refresh(grant)

        return ConsentService._format_consent_response(grant)

    @staticmethod
    def get_consents_for_user(
        db: Session, user: User, as_granter: bool = True, as_grantee: bool = True
    ) -> List[ConsentGrantResponse]:
        """List consent records involving the authenticated participant."""
        query = db.query(ConsentGrant)
        if as_granter and as_grantee:
            query = query.filter(
                (ConsentGrant.granter_user_id == user.id) | (ConsentGrant.grantee_user_id == user.id)
            )
        elif as_granter:
            query = query.filter(ConsentGrant.granter_user_id == user.id)
        elif as_grantee:
            query = query.filter(ConsentGrant.grantee_user_id == user.id)

        # Demo session isolation: Demo sessions strictly see consent grants between demo accounts
        if getattr(user, "is_demo_session", False):
            demo_user_ids = [u.id for u in db.query(User.id).filter(User.email.like("%@wadih.demo")).all()]
            query = query.filter(
                ConsentGrant.granter_user_id.in_(demo_user_ids),
                ConsentGrant.grantee_user_id.in_(demo_user_ids),
            )

        grants = query.order_by(ConsentGrant.created_at.desc()).all()
        return [ConsentService._format_consent_response(g) for g in grants]

    @staticmethod
    def get_consent_detail(db: Session, consent_id: int, user: User) -> ConsentGrantResponse:
        """Fetch consent detail with object-level isolation (caller must be granter or grantee)."""
        grant = db.query(ConsentGrant).filter(ConsentGrant.id == consent_id).first()
        if not grant:
            raise NotFoundException("Consent grant not found.")

        if grant.granter_user_id != user.id and grant.grantee_user_id != user.id and user.role != UserRole.ADMIN:
            raise NotFoundException("Consent grant not found.")

        # Demo session isolation: Demo sessions cannot view consent records involving real accounts
        if getattr(user, "is_demo_session", False):
            demo_user_ids = {u.id for u in db.query(User.id).filter(User.email.like("%@wadih.demo")).all()}
            if grant.granter_user_id not in demo_user_ids or grant.grantee_user_id not in demo_user_ids:
                raise NotFoundException("Consent grant not found.")

        return ConsentService._format_consent_response(grant)

    @staticmethod
    def get_shared_case(
        db: Session, case_id: int, caller: User
    ) -> SharedCaseSummaryResponse:
        """Retrieve shared screening findings enforcing scoped consent and revocation status.

        Scenarios:
        - Active GRANTED consent: returns findings filtered strictly by consented scope.
        - PENDING, REVOKED, or EXPIRED consent: denied access.
        - No consent: 404 privacy-preserving response (avoids exposing case existence).
        """
        case = db.query(ScreeningCase).filter(ScreeningCase.id == case_id).first()
        if not case:
            AuditService.log_event(
                db=db,
                action="ACCESS_DENIED",
                resource_type="screening_case",
                resource_id=str(case_id),
                actor_user_id=caller.id,
                outcome="DENIED",
                details={"reason": "Case does not exist."},
            )
            raise NotFoundException("Screening case not found.")

        # If caller is the case owner, they can view their own summary
        if case.owner_user_id == caller.id:
            findings_summary = [
                SharedFindingSummary(
                    condition_code=f.condition_code,
                    condition_name=f.condition_name,
                    carrier_state=f.carrier_state,
                    inheritance_mode=f.inheritance_mode,
                    summary_text=f.summary_text,
                )
                for f in case.findings
            ]
            owner_name = caller.profile.display_name if caller.profile else caller.email.split("@")[0]
            return SharedCaseSummaryResponse(
                case_id=case.id,
                synthetic_case_code=case.synthetic_case_code,
                granted_scope="owner_full",
                owner_display_name=owner_name,
                status=case.status,
                findings=findings_summary,
            )

        # Check Active Consent Grant from Owner to Caller
        grant = (
            db.query(ConsentGrant)
            .filter(
                ConsentGrant.granter_user_id == case.owner_user_id,
                ConsentGrant.grantee_user_id == caller.id,
            )
            .order_by(ConsentGrant.created_at.desc())
            .first()
        )

        if not grant:
            AuditService.log_event(
                db=db,
                action="ACCESS_DENIED",
                resource_type="screening_case",
                resource_id=str(case_id),
                actor_user_id=caller.id,
                outcome="DENIED",
                details={"reason": "No consent grant exists from case owner."},
            )
            # Privacy-preserving response: do not confirm case exists to unauthorized caller
            raise NotFoundException("Screening case not found.")

        # Check Grant Status
        now = datetime.now(timezone.utc)
        if grant.status != ConsentStatus.GRANTED.value:
            AuditService.log_event(
                db=db,
                action="ACCESS_DENIED",
                resource_type="screening_case",
                resource_id=str(case_id),
                actor_user_id=caller.id,
                outcome="DENIED",
                details={"reason": f"Consent grant status is {grant.status} (not GRANTED)."},
            )
            raise ConsentRequiredException(
                f"Access denied: Consent permission is {grant.status}. Active granted consent is required."
            )

        if grant.revoked_at is not None:
            AuditService.log_event(
                db=db,
                action="ACCESS_DENIED",
                resource_type="screening_case",
                resource_id=str(case_id),
                actor_user_id=caller.id,
                outcome="DENIED",
                details={"reason": "Consent grant was revoked by the granter."},
            )
            raise ConsentRequiredException("Access denied: Consent has been revoked by the granting participant.")

        if grant.expires_at is not None:
            expires_at = grant.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                grant.status = ConsentStatus.EXPIRED.value
                db.commit()
                AuditService.log_event(
                    db=db,
                    action="ACCESS_DENIED",
                    resource_type="screening_case",
                    resource_id=str(case_id),
                    actor_user_id=caller.id,
                    outcome="DENIED",
                    details={"reason": "Consent grant has expired."},
                )
                raise ConsentRequiredException("Access denied: Consent grant has expired.")

        # Specific Case Binding Check (if grant was bound to a specific case)
        if grant.case_id is not None and grant.case_id != case.id:
            AuditService.log_event(
                db=db,
                action="ACCESS_DENIED",
                resource_type="screening_case",
                resource_id=str(case_id),
                actor_user_id=caller.id,
                outcome="DENIED",
                details={"reason": "Consent grant is bound to a different case."},
            )
            raise NotFoundException("Screening case not found.")

        # Authorized Access: Filter Findings by Scope
        AuditService.log_event(
            db=db,
            action="SENSITIVE_RESULT_ACCESSED",
            resource_type="screening_case",
            resource_id=str(case.id),
            actor_user_id=caller.id,
            outcome="SUCCESS",
            details={
                "scope": grant.scope,
                "grant_id": grant.id,
                "granter_user_id": grant.granter_user_id,
            },
        )

        findings_summary = []
        for f in case.findings:
            if grant.scope == ConsentScope.CARRIER_STATUS_ONLY.value:
                # Carrier status only: summary text and classification redacted
                findings_summary.append(
                    SharedFindingSummary(
                        condition_code=f.condition_code,
                        condition_name=f.condition_name,
                        carrier_state=f.carrier_state,
                        inheritance_mode=f.inheritance_mode,
                        classification_state=None,
                        reviewed_flag=None,
                        summary_text=None,
                    )
                )
            elif grant.scope == ConsentScope.SUMMARY_ONLY.value:
                # Summary only: educational summary included, classification redacted
                findings_summary.append(
                    SharedFindingSummary(
                        condition_code=f.condition_code,
                        condition_name=f.condition_name,
                        carrier_state=f.carrier_state,
                        inheritance_mode=f.inheritance_mode,
                        classification_state=None,
                        reviewed_flag=None,
                        summary_text=f.summary_text,
                    )
                )
            else:
                # full_report: complete finding disclosure
                findings_summary.append(
                    SharedFindingSummary(
                        condition_code=f.condition_code,
                        condition_name=f.condition_name,
                        carrier_state=f.carrier_state,
                        inheritance_mode=f.inheritance_mode,
                        classification_state=f.classification_state,
                        reviewed_flag=f.reviewed_flag,
                        summary_text=f.summary_text,
                    )
                )

        owner = case.owner
        owner_name = owner.profile.display_name if owner and owner.profile else "Partner"

        return SharedCaseSummaryResponse(
            case_id=case.id,
            synthetic_case_code=case.synthetic_case_code,
            granted_scope=grant.scope,
            owner_display_name=owner_name,
            status=case.status,
            findings=findings_summary,
        )

    @staticmethod
    def _format_consent_response(grant: ConsentGrant) -> ConsentGrantResponse:
        granter_name = (
            grant.granter.profile.display_name
            if grant.granter and grant.granter.profile
            else (grant.granter.email.split("@")[0] if grant.granter else f"User {grant.granter_user_id}")
        )
        grantee_name = (
            grant.grantee.profile.display_name
            if grant.grantee and grant.grantee.profile
            else (grant.grantee.email.split("@")[0] if grant.grantee else f"User {grant.grantee_user_id}")
        )

        return ConsentGrantResponse(
            id=grant.id,
            granter_user_id=grant.granter_user_id,
            granter_name=granter_name,
            grantee_user_id=grant.grantee_user_id,
            grantee_name=grantee_name,
            scope=grant.scope,
            status=grant.status,
            purpose=grant.purpose,
            terms_version=grant.terms_version,
            case_id=grant.case_id,
            created_at=grant.created_at,
            expires_at=grant.expires_at,
            revoked_at=grant.revoked_at,
        )
