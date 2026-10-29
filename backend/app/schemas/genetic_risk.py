import enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InheritancePattern(str, enum.Enum):
    AUTOSOMAL_RECESSIVE = "AUTOSOMAL_RECESSIVE"
    AUTOSOMAL_DOMINANT = "AUTOSOMAL_DOMINANT"
    X_LINKED_RECESSIVE = "X_LINKED_RECESSIVE"
    X_LINKED_DOMINANT = "X_LINKED_DOMINANT"
    MITOCHONDRIAL = "MITOCHONDRIAL"
    MULTIFACTORIAL = "MULTIFACTORIAL"
    UNKNOWN = "UNKNOWN"


class ScreeningInterpretation(str, enum.Enum):
    CARRIER_DETECTED = "CARRIER_DETECTED"
    NO_VARIANT_DETECTED = "NO_VARIANT_DETECTED"
    UNCERTAIN_SIGNIFICANCE = "UNCERTAIN_SIGNIFICANCE"
    POSITIVE_AFFECTED = "POSITIVE_AFFECTED"
    NOT_PERFORMED = "NOT_PERFORMED"
    INCONCLUSIVE = "INCONCLUSIVE"


class AssessmentStatus(str, enum.Enum):
    EDUCATIONAL_RESULT = "EDUCATIONAL_RESULT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED_INHERITANCE_PATTERN = "UNSUPPORTED_INHERITANCE_PATTERN"


class RiskProbabilityEstimate(BaseModel):
    affected_probability: Optional[float] = Field(
        None, description="Per-pregnancy probability of a child inheriting both altered copies and being affected"
    )
    carrier_probability: Optional[float] = Field(
        None, description="Per-pregnancy probability of a child inheriting one altered copy and being an unaffected carrier"
    )
    unaffected_non_carrier_probability: Optional[float] = Field(
        None, description="Per-pregnancy probability of a child inheriting neither altered copy"
    )
    residual_carrier_probability_used: Optional[float] = Field(
        None, description="Validated post-test residual carrier probability (r) utilized for calculation"
    )
    summary_label: str = Field(..., description="Short clinical/educational summary label")
    recurrence_note: str = Field(
        ...,
        description="Explicit note stating probabilities apply independently to each pregnancy",
    )

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentRequest(BaseModel):
    case_id: Optional[str] = Field(None, description="Synthetic case identifier if applicable")
    condition_code: str = Field(..., description="Machine-readable condition identifier (e.g. HBB_BETA_THAL)")
    condition_name: str = Field(..., description="Human-readable condition name (e.g. Beta Thalassemia)")
    gene_symbol: Optional[str] = Field(None, description="Relevant gene symbol if known (e.g. HBB, CFTR)")
    inheritance_pattern: InheritancePattern = Field(..., description="Inheritance mode")
    partner_1_finding: ScreeningInterpretation = Field(
        ..., description="Clinician-confirmed finding for primary partner"
    )
    partner_2_finding: Optional[ScreeningInterpretation] = Field(
        None, description="Clinician-confirmed finding for secondary partner (None if untested/unlinked)"
    )
    partner_1_residual_carrier_probability: Optional[float] = Field(
        None,
        description="Validated condition-specific residual carrier probability (0.0 < r < 1.0) for partner 1 if negative",
    )
    partner_2_residual_carrier_probability: Optional[float] = Field(
        None,
        description="Validated condition-specific residual carrier probability (0.0 < r < 1.0) for partner 2 if negative",
    )
    residual_risk_source: Optional[str] = Field(
        None,
        description="Documentation of laboratory panel and detection rate source for residual risk (e.g. 'LabCorp ECS v3 - 99% detection rate')",
    )
    clinician_confirmed_provenance: bool = Field(
        True,
        description="Whether supplied residual carrier risk is confirmed to originate from a clinician-reviewed laboratory report",
    )
    findings_sufficient: bool = Field(
        True, description="Whether laboratory findings are sufficient for supported model"
    )
    is_clinician_reviewed: bool = Field(
        True, description="Whether input findings have undergone certified clinician review"
    )

    model_config = ConfigDict(from_attributes=True)


class CaseRiskAssessmentRequest(BaseModel):
    condition_code: str = Field(..., description="Machine-readable condition identifier (e.g. HBB_BETA_THAL)")
    partner_case_id: Optional[int] = Field(
        None, description="Optional partner case ID (requires active partner consent grant)"
    )
    partner_residual_carrier_probability: Optional[float] = Field(
        None,
        description="Validated condition-specific residual carrier probability for negative-screening partner (0.0 < r < 1.0)",
    )
    residual_risk_source: Optional[str] = Field(
        None,
        description="Documentation of laboratory panel and detection rate source for residual risk (e.g. 'ACMG Tier 3 carrier screen panel')",
    )
    clinician_confirmed_provenance: bool = Field(
        False,
        description="Explicit attestation that this residual risk value is derived from a clinician-reviewed laboratory test report",
    )
    simulation_mode: bool = Field(
        False,
        description="Run as educational demonstration rather than authoritative clinical assessment",
    )

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentResponse(BaseModel):
    case_id: Optional[str] = Field(None, description="Synthetic case identifier")
    condition: str = Field(..., description="Condition display name")
    condition_code: str = Field(..., description="Condition code")
    gene: Optional[str] = Field(None, description="Gene symbol")
    inheritance_pattern: InheritancePattern = Field(..., description="Inheritance pattern evaluated")
    assessment_status: AssessmentStatus = Field(..., description="Outcome category")
    risk_estimate: Optional[RiskProbabilityEstimate] = Field(
        None, description="Deterministic risk probabilities if simplified model applies"
    )
    residual_risk_source: Optional[str] = Field(
        None, description="Documented laboratory panel source for residual risk if applicable"
    )
    explanation: str = Field(..., description="Deterministic educational explanation")
    limitations: List[str] = Field(default_factory=list, description="Clinical assumptions and test scope boundaries")
    assumptions: List[str] = Field(default_factory=list, description="Explicit clinical conditions required for calculation")
    requires_genetic_counselor: bool = Field(
        False, description="Whether case requires escalation to professional genetics review"
    )
    referral_reason: Optional[str] = Field(None, description="Structured referral or escalation trigger code")
    rule_version: str = Field(..., description="Version identifier of deterministic calculation rule set")
    is_educational_simulation: bool = Field(
        True,
        description="Whether this assessment is a hypothetical educational scenario calculation rather than an authoritative patient record assessment",
    )
    is_authoritative_clinical_record: bool = Field(
        False,
        description="Whether this assessment evaluates an authoritative, verified clinical screening record in the database",
    )
    is_synthetic_sandbox: bool = Field(
        False,
        description="Whether this assessment utilizes a synthetic demonstration sandbox record",
    )
    disclaimer: str = Field(
        default=(
            "Educational and demonstration assessment only. This calculation uses synthetic genetic screening scenarios "
            "and standard Mendelian probability models. It does not constitute medical diagnosis, diagnostic confirmation, "
            "or a guarantee of any child's health outcome. Consult a certified genetic counsellor for personalized pre-conception guidance."
        ),
        description="Standard clinical safety disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)
