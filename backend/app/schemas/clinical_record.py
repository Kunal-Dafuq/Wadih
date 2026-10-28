from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ClinicalProvenanceCreateRequest(BaseModel):
    case_id: int = Field(..., description="Screening case ID to which this validated residual risk applies")
    condition_code: str = Field(..., description="Target condition code (e.g. HBB_BETA_THAL)")
    residual_carrier_probability: float = Field(
        ...,
        gt=0.0,
        lt=1.0,
        description="Clinician-confirmed residual carrier probability (strictly 0.0 < r < 1.0)",
    )
    clinical_source_reference: str = Field(
        ...,
        min_length=3,
        description="Accredited laboratory panel or clinical reference (e.g. 'LabCorp ECS v3 - 99% detection rate')",
    )
    notes: Optional[str] = Field(None, description="Clinical notes from reviewing geneticist or counsellor")

    model_config = ConfigDict(from_attributes=True)


class ClinicalProvenanceResponse(BaseModel):
    id: int
    case_id: int
    condition_code: str
    residual_carrier_probability: float
    clinical_source_reference: str
    reviewing_clinician_id: int
    notes: Optional[str] = None
    is_active: bool
    reviewed_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
