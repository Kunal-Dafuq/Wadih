"""Deterministic genetic-risk calculation engine.

Validates structured inputs, enforces clinical-safety guardrails, and evaluates
inheritance probabilities using versioned deterministic rule sets.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.schemas.genetic_risk import (
    InheritancePattern,
    ScreeningInterpretation,
    AssessmentStatus,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from app.services.inheritance_rules import (
    RULE_VERSION,
    STANDARD_LIMITATIONS,
    evaluate_autosomal_recessive_case,
)
from app.models.user import User, UserRole
from app.models.screening_case import ScreeningCase, SyntheticFinding
from app.models.consent import ConsentGrant, ConsentStatus, ConsentScope
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    ConsentRequiredException,
    ForbiddenException,
)


class RiskEngineService:
    @staticmethod
    def assess_risk(
        request: RiskAssessmentRequest,
        is_educational_simulation: Optional[bool] = None,
        allow_simulation: bool = False,
    ) -> RiskAssessmentResponse:
        """Evaluate deterministic genetic risk from a validated structured request."""
        # 1. Input Validation Guardrails
        if not request.condition_code or not request.condition_code.strip():
            raise ValidationException("Condition code must not be empty.")

        if not request.condition_name or not request.condition_name.strip():
            raise ValidationException("Condition name must not be empty.")

        if is_educational_simulation is None:
            is_educational_simulation = (request.case_id is None)

        bound_case_id = request.case_id

        if is_educational_simulation:
            disclaimer_text = (
                "Hypothetical educational simulation only. This calculation uses demonstration scenario parameters "
                "and standard Mendelian arithmetic. It does NOT evaluate, verify, or represent any patient's actual "
                "clinical screening record. For verified clinical results, view the authoritative case assessment."
            )
        else:
            disclaimer_text = (
                "Educational and demonstration assessment for clinical screening case. This calculation uses verified "
                "synthetic findings and standard Mendelian probability models. It does not constitute medical diagnosis "
                "or a guarantee of any child's health outcome. Consult a certified genetic counsellor for personalized pre-conception guidance."
            )

        # Residual carrier probability validations
        if request.partner_1_residual_carrier_probability is not None:
            r1 = request.partner_1_residual_carrier_probability
            if r1 <= 0.0 or r1 >= 1.0:
                raise ValidationException("Partner 1 residual carrier probability must be strictly between 0.0 and 1.0 (exclusive).")
            if request.partner_1_finding != ScreeningInterpretation.NO_VARIANT_DETECTED:
                raise ValidationException("Residual carrier probability is only applicable for partners with NO_VARIANT_DETECTED screening interpretation.")

        if request.partner_2_residual_carrier_probability is not None:
            r2 = request.partner_2_residual_carrier_probability
            if r2 <= 0.0 or r2 >= 1.0:
                raise ValidationException("Partner 2 residual carrier probability must be strictly between 0.0 and 1.0 (exclusive).")
            if request.partner_2_finding != ScreeningInterpretation.NO_VARIANT_DETECTED:
                raise ValidationException("Residual carrier probability is only applicable for partners with NO_VARIANT_DETECTED screening interpretation.")

        # 2. Inheritance pattern guardrail
        if request.inheritance_pattern != InheritancePattern.AUTOSOMAL_RECESSIVE:
            return RiskAssessmentResponse(
                case_id=bound_case_id,
                condition=request.condition_name,
                condition_code=request.condition_code,
                gene=request.gene_symbol,
                inheritance_pattern=request.inheritance_pattern,
                assessment_status=AssessmentStatus.UNSUPPORTED_INHERITANCE_PATTERN,
                risk_estimate=None,
                explanation=(
                    f"The inheritance mode '{request.inheritance_pattern.value}' for {request.condition_name} "
                    "is not supported by this deterministic educational model. Non-recessive inheritance patterns "
                    "(e.g., dominant, X-linked, mitochondrial, or multifactorial) involve complex clinical considerations "
                    "such as variable expressivity, incomplete penetrance, or sex-linked segregation, which require "
                    "individualized evaluation by a certified genetics specialist."
                ),
                limitations=STANDARD_LIMITATIONS
                + [f"Inheritance pattern {request.inheritance_pattern.value} requires specialized clinical counselling."],
                assumptions=["Model currently supports biallelic autosomal recessive carrier screening calculations."],
                requires_genetic_counselor=True,
                referral_reason="UNSUPPORTED_INHERITANCE_PATTERN",
                rule_version=RULE_VERSION,
                is_educational_simulation=is_educational_simulation,
                is_case_linked_assessment=bool(bound_case_id),
                is_authoritative_clinical_record=False,
                is_synthetic_sandbox=False,
                clinician_confirmed_provenance=request.clinician_confirmed_provenance,
                disclaimer=disclaimer_text,
            )

        # 3. Autosomal recessive evaluation
        (
            status,
            risk_est,
            explanation,
            limitations,
            assumptions,
            requires_counselor,
            referral_reason,
        ) = evaluate_autosomal_recessive_case(
            partner_1_finding=request.partner_1_finding,
            partner_2_finding=request.partner_2_finding,
            condition_name=request.condition_name,
            gene_symbol=request.gene_symbol,
            partner_1_residual_carrier_probability=request.partner_1_residual_carrier_probability,
            partner_2_residual_carrier_probability=request.partner_2_residual_carrier_probability,
            findings_sufficient=request.findings_sufficient,
            is_clinician_reviewed=request.is_clinician_reviewed,
            clinician_confirmed_provenance=request.clinician_confirmed_provenance,
            residual_risk_source=request.residual_risk_source,
            allow_simulation=allow_simulation,
        )

        return RiskAssessmentResponse(
            case_id=bound_case_id,
            condition=request.condition_name,
            condition_code=request.condition_code,
            gene=request.gene_symbol,
            inheritance_pattern=request.inheritance_pattern,
            assessment_status=status,
            risk_estimate=risk_est,
            residual_risk_source=request.residual_risk_source,
            explanation=explanation,
            limitations=limitations,
            assumptions=assumptions,
            requires_genetic_counselor=requires_counselor,
            referral_reason=referral_reason,
            rule_version=RULE_VERSION,
            is_educational_simulation=is_educational_simulation,
            is_case_linked_assessment=bool(bound_case_id),
            is_authoritative_clinical_record=False,
            is_synthetic_sandbox=False,
            clinician_confirmed_provenance=request.clinician_confirmed_provenance,
            disclaimer=disclaimer_text,
        )

    @staticmethod
    def assess_from_cases(
        db: Session,
        case_1_id: int,
        condition_code: str,
        user: User,
        partner_case_id: Optional[int] = None,
        partner_residual_carrier_probability: Optional[float] = None,
        residual_risk_source: Optional[str] = None,
        clinician_confirmed_provenance: bool = False,
        simulation_mode: bool = False,
    ) -> RiskAssessmentResponse:
        """Assess risk directly from stored synthetic cases in the database, verifying ownership and consent."""
        is_demo = getattr(user, "is_demo_session", False)

        # 1. Fetch Primary Case (Case 1)
        case_1 = db.query(ScreeningCase).filter(ScreeningCase.id == case_1_id).first()
        if not case_1:
            raise NotFoundException("Screening case not found.")

        # Demo session isolation: barred from non-synthetic cases
        if is_demo and not (case_1.synthetic_case_code and case_1.synthetic_case_code.startswith("SYN-")):
            raise NotFoundException("Screening case not found.")

        # Object-level authorization for Case 1
        is_owner = case_1.owner_user_id == user.id
        is_counsellor = False
        if user.role == UserRole.COUNSELLOR:
            from app.models.referral import ReferralTask
            is_counsellor = (
                db.query(ReferralTask)
                .filter(
                    ReferralTask.case_id == case_1_id,
                    ReferralTask.assigned_counsellor_id == user.id,
                )
                .first()
                is not None
            )

        if not is_owner and not is_counsellor:
            raise NotFoundException("Screening case not found.")

        # Finding for Case 1
        finding_1 = (
            db.query(SyntheticFinding)
            .filter(
                SyntheticFinding.case_id == case_1_id,
                SyntheticFinding.condition_code == condition_code,
            )
            .first()
        )
        if not finding_1:
            raise NotFoundException(f"Condition '{condition_code}' not found in primary case findings.")

        # Map Case 1 finding
        p1_interpretation = RiskEngineService._map_finding_to_interpretation(finding_1)
        inheritance_mode = RiskEngineService._map_inheritance_mode(finding_1.inheritance_mode)

        # 2. Handle Partner Case (Case 2) if provided
        p2_interpretation: Optional[ScreeningInterpretation] = None
        case_2: Optional[ScreeningCase] = None
        if partner_case_id:
            case_2 = db.query(ScreeningCase).filter(ScreeningCase.id == partner_case_id).first()
            if not case_2:
                raise NotFoundException("Partner screening case not found.")

            if is_demo and not (case_2.synthetic_case_code and case_2.synthetic_case_code.startswith("SYN-")):
                raise NotFoundException("Partner screening case not found.")

            # Strict Consent Check: Partner must have granted ACTIVE consent to user
            if case_2.owner_user_id != user.id and not is_counsellor:
                active_grant = (
                    db.query(ConsentGrant)
                    .filter(
                        ConsentGrant.granter_user_id == case_2.owner_user_id,
                        ConsentGrant.grantee_user_id == user.id,
                        ConsentGrant.status == ConsentStatus.GRANTED.value,
                    )
                    .first()
                )
                if not active_grant:
                    raise ConsentRequiredException(
                        "Access to partner screening data requires an approved consent grant from the partner."
                    )

            finding_2 = (
                db.query(SyntheticFinding)
                .filter(
                    SyntheticFinding.case_id == partner_case_id,
                    SyntheticFinding.condition_code == condition_code,
                )
                .first()
            )
            if finding_2:
                p2_interpretation = RiskEngineService._map_finding_to_interpretation(finding_2)
            else:
                p2_interpretation = ScreeningInterpretation.NO_VARIANT_DETECTED

        # Ensure findings reviewed by clinician for both available partners
        both_reviewed = bool(finding_1.reviewed_flag)
        if partner_case_id and finding_2:
            both_reviewed = both_reviewed and bool(finding_2.reviewed_flag)

        # Server-controlled clinical provenance lookup:
        # A client cannot self-certify provenance. Residual risk must be backed by a persisted ClinicalResidualRiskRecord.
        from app.services.clinical_provenance_service import ClinicalProvenanceService

        final_residual_carrier_prob: Optional[float] = None
        final_provenance_confirmed: bool = False
        final_residual_source: Optional[str] = None

        is_single_carrier_and_neg = (
            (
                p1_interpretation == ScreeningInterpretation.CARRIER_DETECTED
                and p2_interpretation == ScreeningInterpretation.NO_VARIANT_DETECTED
            )
            or (
                p1_interpretation == ScreeningInterpretation.NO_VARIANT_DETECTED
                and p2_interpretation == ScreeningInterpretation.CARRIER_DETECTED
            )
        )

        is_sandbox_used: bool = False
        if is_single_carrier_and_neg:
            neg_case_id = (
                partner_case_id
                if p1_interpretation == ScreeningInterpretation.CARRIER_DETECTED
                else case_1_id
            )
            trusted_record = None
            if neg_case_id:
                # If simulation_mode is explicitly requested, allow synthetic sandbox records for demo simulations
                # In standard authoritative evaluation (simulation_mode=False), synthetic sandbox records are EXCLUDED
                trusted_record = ClinicalProvenanceService.get_valid_provenance(
                    db=db,
                    case_id=neg_case_id,
                    condition_code=condition_code,
                    allow_synthetic_sandbox=simulation_mode,
                )

            if trusted_record:
                if trusted_record.is_synthetic_sandbox:
                    # Sandbox demonstration record:
                    # CANNOT satisfy authoritative clinical provenance (only usable in simulation_mode)
                    is_sandbox_used = True
                    final_residual_carrier_prob = trusted_record.residual_carrier_probability
                    final_provenance_confirmed = False  # NEVER True for synthetic sandbox
                    final_residual_source = trusted_record.clinical_source_reference
                else:
                    # If client passed an explicit probability, verify it matches the authoritative clinician record
                    if (
                        partner_residual_carrier_probability is not None
                        and abs(partner_residual_carrier_probability - trusted_record.residual_carrier_probability) > 1e-5
                    ):
                        # Inconsistent with authoritative clinician record -> fail safely
                        final_residual_carrier_prob = partner_residual_carrier_probability
                        final_provenance_confirmed = False
                        final_residual_source = None
                    else:
                        final_residual_carrier_prob = trusted_record.residual_carrier_probability
                        final_provenance_confirmed = True
                        final_residual_source = trusted_record.clinical_source_reference
            else:
                # No trusted clinical record found in the database.
                # Client-supplied numbers cannot self-certify clinical provenance.
                if partner_residual_carrier_probability is not None:
                    final_residual_carrier_prob = partner_residual_carrier_probability
                    final_provenance_confirmed = False
                    final_residual_source = None
                else:
                    final_residual_carrier_prob = None
                    final_provenance_confirmed = False
                    final_residual_source = None

        # Check if cases are explicitly identified synthetic demo cases ('SYN-')
        is_case_1_synthetic = bool(case_1.synthetic_case_code and case_1.synthetic_case_code.startswith("SYN-"))
        is_case_2_synthetic = (
            bool(case_2 and case_2.synthetic_case_code and case_2.synthetic_case_code.startswith("SYN-"))
            if partner_case_id
            else False
        )
        has_synthetic_case = is_case_1_synthetic or is_case_2_synthetic

        req = RiskAssessmentRequest(
            case_id=case_1.synthetic_case_code,
            condition_code=finding_1.condition_code,
            condition_name=finding_1.condition_name,
            gene_symbol=finding_1.condition_code.split("_")[0] if "_" in finding_1.condition_code else None,
            inheritance_pattern=inheritance_mode,
            partner_1_finding=p1_interpretation,
            partner_2_finding=p2_interpretation,
            partner_2_residual_carrier_probability=final_residual_carrier_prob,
            residual_risk_source=final_residual_source,
            clinician_confirmed_provenance=final_provenance_confirmed,
            findings_sufficient=True,
            is_clinician_reviewed=both_reviewed,
        )

        is_simulation = simulation_mode or is_sandbox_used
        resp = RiskEngineService.assess_risk(
            req,
            is_educational_simulation=is_simulation,
            allow_simulation=simulation_mode,
        )
        resp.is_case_linked_assessment = True
        resp.is_synthetic_sandbox = is_sandbox_used
        resp.clinician_confirmed_provenance = final_provenance_confirmed

        if is_simulation or is_sandbox_used:
            resp.is_authoritative_clinical_record = False
            resp.is_educational_simulation = True
            if is_sandbox_used:
                resp.disclaimer = (
                    "Hypothetical educational demonstration using synthetic sandbox residual risk parameters. "
                    "This calculation does not satisfy authoritative clinical provenance. "
                    "Consult a certified genetic counsellor for personalized pre-conception guidance."
                )
            else:
                resp.disclaimer = (
                    "Educational scenario simulation. Calculations reflect hypothetical teaching models. "
                    "Consult a certified genetic counsellor for clinical guidance."
                )
        else:
            resp.is_educational_simulation = False
            resp.is_synthetic_sandbox = False

            # Genuinely authoritative clinical record evaluation:
            # 1. Non-synthetic screening cases (neither starts with 'SYN-')
            # 2. Both findings reviewed by clinician (both_reviewed == True)
            # 3. Not running in simulation mode
            # 4. Valid non-synthetic clinician provenance verified if residual risk was required
            # 5. Status is not INSUFFICIENT_DATA and risk_estimate is not None
            if has_synthetic_case:
                # Screening findings from explicitly identified synthetic demo cases cannot be labelled authoritative
                resp.is_authoritative_clinical_record = False
                resp.disclaimer = (
                    "Educational demonstration using synthetic screening cases. "
                    "Calculations reflect hypothetical simulation models and do not constitute an authoritative clinical patient record. "
                    "Consult a certified genetic counsellor for clinical decision-making."
                )
            elif (
                not both_reviewed
                or resp.assessment_status == AssessmentStatus.INSUFFICIENT_DATA
                or resp.risk_estimate is None
            ):
                resp.is_authoritative_clinical_record = False
            elif is_single_carrier_and_neg and not final_provenance_confirmed:
                resp.is_authoritative_clinical_record = False
            else:
                resp.is_authoritative_clinical_record = True
                resp.disclaimer = (
                    "Authoritative clinical risk assessment evaluated against clinician-reviewed patient screening records "
                    "and verified laboratory provenance. Pre-conception genetic counselling is recommended."
                )

        return resp

    @staticmethod
    def _map_finding_to_interpretation(finding: SyntheticFinding) -> ScreeningInterpretation:
        """Map database SyntheticFinding fields to ScreeningInterpretation enum."""
        carrier_str = (finding.carrier_state or "").upper()
        classification_str = (finding.classification_state or "").upper()

        if "UNCERTAIN" in carrier_str or "VUS" in classification_str:
            return ScreeningInterpretation.UNCERTAIN_SIGNIFICANCE
        if "INCONCLUSIVE" in carrier_str:
            return ScreeningInterpretation.INCONCLUSIVE
        if "CARRIER" in carrier_str or "PATHOGENIC" in classification_str:
            return ScreeningInterpretation.CARRIER_DETECTED
        if "NEGATIVE" in classification_str or "NO_VARIANT" in carrier_str:
            return ScreeningInterpretation.NO_VARIANT_DETECTED
        if "AFFECTED" in carrier_str or "POSITIVE_AFFECTED" in classification_str:
            return ScreeningInterpretation.POSITIVE_AFFECTED

        return ScreeningInterpretation.CARRIER_DETECTED

    @staticmethod
    def _map_inheritance_mode(mode_str: str) -> InheritancePattern:
        """Map database string to InheritancePattern enum."""
        s = (mode_str or "").upper().replace(" ", "_").replace("-", "_")
        for member in InheritancePattern:
            if member.value == s:
                return member
        return InheritancePattern.UNKNOWN
