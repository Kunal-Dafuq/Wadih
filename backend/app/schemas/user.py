from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ParticipantProfileResponse(BaseModel):
    user_id: int
    display_name: str
    preferred_language: str
    literacy_mode: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParticipantProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=120)
    preferred_language: Optional[str] = Field(None, pattern=r"^[a-zA-Z]{2}(-[a-zA-Z]{2})?$")
    literacy_mode: Optional[str] = Field(None, pattern=r"^(standard|plain_language)$")


class UserDetailResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime
    profile: Optional[ParticipantProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)
