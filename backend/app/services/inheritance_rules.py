"""Deterministic inheritance rules and clinical calculation engine for Wadih.

RULE VERSION: v1.0.0-ar-deterministic
Scope: Autosomal recessive pre-conception carrier screening assessment.
"""

from typing import Tuple, List, Optional
from app.schemas.genetic_risk import (
    InheritancePattern,
    ScreeningInterpretation,
    AssessmentStatus,
    RiskProbabilityEstimate,
)

RULE_VERSION = "v1.0.0-ar-deterministic"

STANDARD_LIMITATIONS = [
    "Carrier screening evaluates a defined panel of synthetic pathogenic variants; negative findings reduce but do not eliminate residual risk.",
    "Detection rate varies by laboratory method and specific gene; undetected rare variants, structural variants, and deep intronic mutations may exist.",
    "Assessment assumes classical Mendelian biallelic transmission without de novo mutations, non-paternity, or uniparental disomy.",
    "Calculations reflect statistical probabilities for each separate pregnancy; they are not deterministic predictions of a specific child's outcome.",
]


def evaluate_autosomal_recessive_case(
    partner_1_finding: ScreeningInterpretation,
    partner_2_finding: Optional[ScreeningInterpretation],
    condition_name: str,
    gene_symbol: Optional[str] = None,
    findings_sufficient: bool = True,
    is_clinician_reviewed: bool = True,
) -> Tuple[
    AssessmentStatus,
    Optional[RiskProbabilityEstimate],
    str,
    List[str],
    List[str],
    bool,
    Optional[str],
]:
    """Pure deterministic rule evaluator for autosomal recessive inheritance.

    Returns:
        (assessment_status, risk_estimate, explanation, limitations, assumptions, requires_counsellor, referral_reason)
    """
    assumptions: List[str] = [
        "Inheritance mode is confirmed Autosomal Recessive.",
        "Both reproductive partners are the biological parents of the prospective pregnancy.",
        "Variants evaluated are confirmed pathogenic or likely pathogenic according to ACMG/AMP criteria.",
    ]
    gene_display = f" ({gene_symbol})" if gene_symbol else ""

    # Guardrail 1: Laboratory findings sufficiency
    if not findings_sufficient:
        return (
            AssessmentStatus.INSUFFICIENT_DATA,
            None,
            f"The laboratory findings provided for {condition_name}{gene_display} are flagged as insufficient or incomplete. "
            "A definitive Mendelian risk calculation cannot be safely rendered without complete screening data.",
            STANDARD_LIMITATIONS,
            assumptions,
            True,
            "LAB_FINDINGS_INSUFFICIENT",
        )

    # Guardrail 2: Clinician review requirement
    if not is_clinician_reviewed:
        return (
            AssessmentStatus.REVIEW_REQUIRED,
            None,
            f"Screening findings for {condition_name}{gene_display} are pending clinician verification. "
            "To ensure patient safety, carrier status must be formally reviewed by a certified laboratory director or clinician before joint risk assessment.",
            STANDARD_LIMITATIONS,
            assumptions,
            True,
            "REPORT_REVIEW_PENDING",
        )

    # Guardrail 3: Uncertain or inconclusive findings (VUS)
    uncertain_states = {
        ScreeningInterpretation.UNCERTAIN_SIGNIFICANCE,
        ScreeningInterpretation.INCONCLUSIVE,
    }
    if partner_1_finding in uncertain_states or partner_2_finding in uncertain_states:
        return (
            AssessmentStatus.REVIEW_REQUIRED,
            None,
            f"A variant of uncertain significance (VUS) or inconclusive finding was identified for {condition_name}{gene_display}. "
            "Current clinical evidence is insufficient to determine whether this variant disrupts gene function or is benign. "
            "No definitive reproductive risk probability can be calculated. Review by a medical geneticist or certified genetic counsellor is required.",
            STANDARD_LIMITATIONS
            + ["Variants of uncertain significance cannot be used to establish definitive reproductive recurrence figures."],
            assumptions,
            True,
            "VARIANT_OF_UNCERTAIN_SIGNIFICANCE",
        )

    # Guardrail 4: Affected partner findings (beyond carrier screening)
    if (
        partner_1_finding == ScreeningInterpretation.POSITIVE_AFFECTED
        or partner_2_finding == ScreeningInterpretation.POSITIVE_AFFECTED
    ):
        return (
            AssessmentStatus.REVIEW_REQUIRED,
            None,
            f"One or both partners are identified as clinically affected with {condition_name}{gene_display} rather than an asymptomatic carrier. "
            "Reproductive risk modeling for affected individuals requires specialized clinical pedigree analysis and individualized genetic counselling.",
            STANDARD_LIMITATIONS,
            assumptions,
            True,
            "AFFECTED_PARTNER_CLINICAL_REVIEW",
        )

    # Case A: Neither partner has a relevant finding identified
    if (
        partner_1_finding == ScreeningInterpretation.NO_VARIANT_DETECTED
        and partner_2_finding == ScreeningInterpretation.NO_VARIANT_DETECTED
    ):
        risk_est = RiskProbabilityEstimate(
            affected_probability=0.0,
            carrier_probability=None,
            unaffected_non_carrier_probability=None,
            summary_label="Significantly Reduced / Residual Risk Only",
            recurrence_note="No pathogenic variants identified in either partner on the reviewed screening panel.",
        )
        explanation = (
            f"Within the scope of the reviewed synthetic carrier screening data, no disease-causing variants were identified in either partner for {condition_name}{gene_display}. "
            "This significantly reduces the reproductive probability of having a child with this condition. "
            "However, a negative screening test does not guarantee zero risk, because standard screening panels test for common pathogenic variants and do not detect all possible rare alterations or new mutations."
        )
        return (
            AssessmentStatus.EDUCATIONAL_RESULT,
            risk_est,
            explanation,
            STANDARD_LIMITATIONS
            + ["Negative screening does not guarantee the absence of all genetic risks or ensure a healthy child."],
            assumptions,
            False,
            None,
        )

    # Case B.1: Single carrier with unlinked / missing partner
    if partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED and (
        partner_2_finding is None or partner_2_finding == ScreeningInterpretation.NOT_PERFORMED
    ):
        explanation = (
            f"Partner 1 was identified as a carrier for {condition_name}{gene_display}. "
            "Being a carrier typically means having one altered copy of the gene and one working copy; carriers are generally healthy and do not experience symptoms. "
            "A couple-level risk calculation cannot be performed because Partner 2 has not completed screening or their results are not linked. "
            "Screening Partner 2 is recommended to determine joint reproductive risk."
        )
        return (
            AssessmentStatus.INSUFFICIENT_DATA,
            None,
            explanation,
            STANDARD_LIMITATIONS
            + ["Couple-level probability cannot be determined without the reproductive partner's screening status."],
            assumptions,
            False,
            None,
        )

    # Case B.2: Single carrier with confirmed negative partner
    if (
        partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED
        and partner_2_finding == ScreeningInterpretation.NO_VARIANT_DETECTED
    ) or (
        partner_1_finding == ScreeningInterpretation.NO_VARIANT_DETECTED
        and partner_2_finding == ScreeningInterpretation.CARRIER_DETECTED
    ):
        risk_est = RiskProbabilityEstimate(
            affected_probability=0.0,
            carrier_probability=0.50,
            unaffected_non_carrier_probability=0.50,
            summary_label="Affected Risk: Residual Only; Carrier Chance: ~50%",
            recurrence_note="Each pregnancy has an estimated 50% chance of being an unaffected carrier like the carrier parent, assuming the other parent has two working gene copies.",
        )
        explanation = (
            f"One partner was confirmed as a carrier for {condition_name}{gene_display}, while the other partner tested negative on the reviewed carrier panel. "
            "Because an autosomal recessive condition requires inheriting two altered gene copies (one from each biological parent) to cause disease, the probability of an affected child is reduced to the background residual risk of the negative partner. "
            "With each pregnancy, there is an estimated 50% chance the child will inherit the carrier copy and be an unaffected carrier, and a 50% chance the child will inherit working copies from both parents."
        )
        return (
            AssessmentStatus.EDUCATIONAL_RESULT,
            risk_est,
            explanation,
            STANDARD_LIMITATIONS
            + ["Carrier status in a child carries no direct personal health symptoms in classical autosomal recessive conditions."],
            assumptions,
            False,
            None,
        )

    # Case C: Both partners are confirmed carriers for the same condition
    if (
        partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED
        and partner_2_finding == ScreeningInterpretation.CARRIER_DETECTED
    ):
        risk_est = RiskProbabilityEstimate(
            affected_probability=0.25,
            carrier_probability=0.50,
            unaffected_non_carrier_probability=0.25,
            summary_label="25% Affected, 50% Carrier, 25% Unaffected Non-Carrier per pregnancy",
            recurrence_note="Each pregnancy is an independent event with a 25% (1 in 4) chance of having the condition. Prior pregnancy outcomes do not influence future pregnancies.",
        )
        explanation = (
            f"Both biological parents are confirmed carriers of pathogenic variants for {condition_name}{gene_display}. "
            "In classical autosomal recessive inheritance, when both reproductive partners are carriers of the same genetic condition, each pregnancy carries:\n"
            "• 25% (1 in 4) chance that the child inherits both altered gene copies and is affected by the condition.\n"
            "• 50% (1 in 2) chance that the child inherits one altered copy and one working copy, becoming an unaffected carrier like the parents.\n"
            "• 25% (1 in 4) chance that the child inherits working copies from both parents and is neither affected nor a carrier.\n\n"
            "These probabilities are separate and independent for each pregnancy. They are not a forecast of an individual child's health outcome. "
            "Consultation with a certified genetic counsellor is recommended to discuss pre-conception options, reproductive technologies, and prenatal screening pathways."
        )
        return (
            AssessmentStatus.EDUCATIONAL_RESULT,
            risk_est,
            explanation,
            STANDARD_LIMITATIONS,
            assumptions
            + [
                "Both partners carry pathogenic variants in trans affecting the same functional gene locus.",
                "Classical 1:2:1 Mendelian segregation applies.",
            ],
            True,
            "DUAL_CARRIER_AUTOSOMAL_RECESSIVE",
        )

    # Fallback for any unhandled state
    return (
        AssessmentStatus.INSUFFICIENT_DATA,
        None,
        f"Input combination for {condition_name}{gene_display} could not be resolved by standard deterministic rules.",
        STANDARD_LIMITATIONS,
        assumptions,
        True,
        "UNRESOLVED_FINDING_COMBINATION",
    )
