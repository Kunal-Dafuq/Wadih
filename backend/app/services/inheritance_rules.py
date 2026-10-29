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
    partner_1_residual_carrier_probability: Optional[float] = None,
    partner_2_residual_carrier_probability: Optional[float] = None,
    findings_sufficient: bool = True,
    is_clinician_reviewed: bool = True,
    clinician_confirmed_provenance: bool = True,
    residual_risk_source: Optional[str] = None,
    allow_simulation: bool = False,
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
        # Clinical safety rule: A negative carrier screen reduces but does NOT eliminate risk.
        # Numerical probability is NOT reported as 0.0 because residual risk is unquantified without panel-specific detection rates.
        explanation = (
            f"Within the scope of the reviewed synthetic carrier screening data, no disease-causing variants were identified in either partner for {condition_name}{gene_display}. "
            "This significantly reduces the reproductive probability of having a child with this condition. "
            "However, a negative screening test does not guarantee zero risk, and this system does not assign a zero-risk numerical probability. "
            "Standard screening panels test for common pathogenic variants and do not detect all possible rare alterations, deep intronic mutations, or new mutations. "
            "Couple-level reproductive risk is residual only and depends on laboratory-specific detection rates."
        )
        return (
            AssessmentStatus.EDUCATIONAL_RESULT,
            None,
            explanation,
            STANDARD_LIMITATIONS
            + [
                "Negative screening does not guarantee the absence of all genetic risks or ensure a healthy child.",
                "No numerical zero-risk probability is assigned; residual risk remains unquantified without panel detection rates.",
            ],
            assumptions,
            False,
            None,
        )

    # Case B.1: Single carrier with unlinked / missing partner
    if (
        partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED
        and (partner_2_finding is None or partner_2_finding == ScreeningInterpretation.NOT_PERFORMED)
    ) or (
        partner_2_finding == ScreeningInterpretation.CARRIER_DETECTED
        and (partner_1_finding is None or partner_1_finding == ScreeningInterpretation.NOT_PERFORMED)
    ):
        carrier_label = "Partner 1" if partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED else "Partner 2"
        other_label = "Partner 2" if carrier_label == "Partner 1" else "Partner 1"
        explanation = (
            f"{carrier_label} was identified as a carrier for {condition_name}{gene_display}. "
            "Being a carrier typically means having one altered copy of the gene and one working copy; carriers are generally healthy and do not experience symptoms. "
            f"A couple-level risk calculation cannot be performed because {other_label} has not completed screening or their results are not linked. "
            f"Screening {other_label} is recommended to determine joint reproductive risk."
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
        # Identify the residual carrier risk of the negative-screening partner
        neg_partner_r = (
            partner_2_residual_carrier_probability
            if partner_1_finding == ScreeningInterpretation.CARRIER_DETECTED
            else partner_1_residual_carrier_probability
        )

        # Safety rule: If residual carrier probability is unavailable, do NOT invent or default a number!
        if neg_partner_r is None:
            explanation = (
                f"One partner was confirmed as a carrier for {condition_name}{gene_display}, while the other partner tested negative on the reviewed carrier panel. "
                "Being a carrier means having one altered copy of the gene and one working copy; carriers are generally healthy and unaffected. "
                "In autosomal recessive inheritance, an affected child can occur only if the negative-screening partner is an undetected carrier. "
                "Under the standard Mendelian model, the couple's per-pregnancy affected probability is calculated as P(affected child) = r × 1/4, "
                "where validated residual carrier probability (r) represents the chance that the negative-screening partner is an undetected carrier. "
                "Because a validated condition-specific residual carrier probability (r) was not provided, a couple-level numerical risk cannot be calculated. "
                "Consultation with a genetic counsellor or the testing laboratory is recommended to obtain the laboratory detection rate and residual risk estimate."
            )
            return (
                AssessmentStatus.INSUFFICIENT_DATA,
                None,
                explanation,
                STANDARD_LIMITATIONS
                + [
                    "Residual risk information was not provided; no numerical probability can be calculated without validated laboratory residual carrier risk.",
                    "Carrier status in a single partner does not cause medical symptoms for that person in classical autosomal recessive conditions.",
                ],
                assumptions,
                False,
                None,
            )

        # Safety rule: Syntactic validation alone is NOT proof of clinician-reviewed laboratory provenance!
        # In authoritative mode, clinician_confirmed_provenance is required.
        # In educational simulation mode, calculations proceed for instructional demonstration,
        # but clinician_confirmed_provenance remains False.
        if not clinician_confirmed_provenance and not allow_simulation:
            explanation = (
                f"One partner was confirmed as a carrier for {condition_name}{gene_display}, while the other partner tested negative on the carrier panel. "
                f"A numerical residual carrier probability ({neg_partner_r}) was submitted, but lacks confirmed laboratory or clinician provenance. "
                "Syntactic numerical validation alone does not constitute proof that a residual-risk value originates from an accredited, clinician-reviewed laboratory report. "
                "Under clinical safety guidelines, numerical recurrence probabilities cannot be computed without verified laboratory detection rates and clinician confirmation. "
                "Consultation with a certified genetic counsellor or laboratory verification is required."
            )
            return (
                AssessmentStatus.REVIEW_REQUIRED,
                None,
                explanation,
                STANDARD_LIMITATIONS
                + [
                    "Residual carrier probability lacks confirmed clinician-reviewed laboratory provenance; numerical calculation suppressed.",
                ],
                assumptions,
                True,
                "UNVERIFIED_RESIDUAL_RISK_PROVENANCE",
            )

        # When validated residual risk r is provided (0.0 < r < 1.0) with confirmed provenance:
        # P(affected child per pregnancy) = r × 1/4
        # P(carrier child per pregnancy) = 0.50
        # P(unaffected non-carrier child per pregnancy) = 0.50 - 0.25 * r
        r = neg_partner_r
        if residual_risk_source:
            assumptions = assumptions + [
                f"Residual carrier probability (r = {r}) is derived from documented laboratory source: {residual_risk_source}."
            ]
        affected_prob = round(r * 0.25, 6)
        carrier_prob = 0.50
        unaffected_non_carrier_prob = round(0.50 - 0.25 * r, 6)

        summary_label = (
            f"Affected Child: {affected_prob:.4%} (P = r × 1/4 with r = {r:.4%}); Carrier Child: 50.00%"
        )
        recurrence_note = (
            f"Each pregnancy has an independent probability calculated from the negative partner's validated residual carrier probability "
            f"(P = r × 1/4, where r = {r}). Prior pregnancy outcomes do not influence future pregnancies."
        )

        risk_est = RiskProbabilityEstimate(
            affected_probability=affected_prob,
            carrier_probability=carrier_prob,
            unaffected_non_carrier_probability=unaffected_non_carrier_prob,
            residual_carrier_probability_used=r,
            summary_label=summary_label,
            recurrence_note=recurrence_note,
        )

        explanation = (
            f"One partner is a confirmed carrier for {condition_name}{gene_display}, and the other partner tested negative on the carrier panel "
            f"with a validated laboratory residual carrier probability of {r:.4%} (approx. 1 in {int(round(1.0 / r)) if r > 0 else 'N/A'}).\n\n"
            f"Under the validated autosomal recessive Mendelian teaching model, an affected child requires inheriting altered copies from both parents. "
            f"The per-pregnancy probability of an affected child is:\n"
            f"• P(affected child) = r × 1/4 = {affected_prob:.4%} (approx. 1 in {int(round(1.0 / affected_prob)) if affected_prob > 0 else 'N/A'}).\n"
            f"• P(carrier child) = 50.00% (1 in 2 chance of inheriting the altered copy from the carrier parent and a working copy from the partner).\n"
            f"• P(unaffected non-carrier child) = {unaffected_non_carrier_prob:.4%}.\n\n"
            "These probabilities apply separately and independently to each pregnancy and are not predictions for a particular child."
        )

        return (
            AssessmentStatus.EDUCATIONAL_RESULT,
            risk_est,
            explanation,
            STANDARD_LIMITATIONS
            + ["Calculations reflect the specific residual carrier risk (r) provided by the laboratory."],
            assumptions
            + [
                f"Negative-screening partner's validated post-test residual carrier probability is r = {r}.",
                "Simplified Mendelian teaching model: P(affected child per pregnancy) = r × 1/4.",
            ],
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
            residual_carrier_probability_used=None,
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
