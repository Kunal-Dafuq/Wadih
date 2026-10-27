from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SyntheticFindingResponse(BaseModel):
    id: int
    condition_code: str
    condition_name: str
    carrier_state: str
    inheritance_mode: str
    classification_state: str
    reviewed_flag: bool
    summary_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningCaseListItem(BaseModel):
    id: int
    synthetic_case_code: str
    status: str
    screening_scope_label: str
    source_reviewed: bool
    findings_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScreeningCaseDetailResponse(BaseModel):
    id: int
    synthetic_case_code: str
    status: str
    screening_scope_label: str
    source_reviewed: bool
    created_at: datetime
    findings: List[SyntheticFindingResponse]
    educational_disclaimer: str = (
        "Educational demonstration record only. "
        "Contains synthetic genetic carrier screening findings; does not constitute medical diagnosis."
    )

    model_config = ConfigDict(from_attributes=True)
