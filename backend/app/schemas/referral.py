from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class CounsellorNoteCreateRequest(BaseModel):
    note_text: str = Field(..., min_length=2, max_length=2000)


class CounsellorNoteResponse(BaseModel):
    id: int
    referral_id: int
    author_user_id: int
    author_name: str
    note_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralTaskCreateRequest(BaseModel):
    case_id: int = Field(..., ge=1)
    reason_code: str = Field(
        ...,
        min_length=3,
        max_length=64,
        json_schema_extra={"example": "CARRIER_RESULT_CONSULT"},
    )
    urgency_level: Optional[str] = Field("ROUTINE", max_length=32)


class ReferralStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(PENDING|SCHEDULED|COMPLETED|CANCELLED)$")


class ReferralTaskResponse(BaseModel):
    id: int
    participant_user_id: int
    case_id: int
    case_code: str
    assigned_counsellor_id: Optional[int] = None
    assigned_counsellor_name: Optional[str] = None
    reason_code: str
    status: str
    urgency_level: str
    created_at: datetime
    updated_at: datetime
    notes: List[CounsellorNoteResponse] = []
    service_disclaimer: str = (
        "Educational & Demonstration Service: This is a simulated referral navigation record. "
        "No real-world appointments or clinical interventions are triggered."
    )

    model_config = ConfigDict(from_attributes=True)
