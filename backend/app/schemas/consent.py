from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.models.consent import ConsentStatus, ConsentScope


class ConsentGrantCreateRequest(BaseModel):
    grantee_email: Optional[EmailStr] = Field(
        None, description="Email of the user being granted access"
    )
    grantee_user_id: Optional[int] = Field(
        None, description="User ID of the user being granted access"
    )
    scope: ConsentScope = Field(
        ConsentScope.SUMMARY_ONLY,
        description="Allowed disclosure scope: carrier_status_only, summary_only, full_report",
    )
    purpose: str = Field(
        "preconception_carrier_screening",
        description="Specific intended purpose of the shared access",
    )
    case_id: Optional[int] = Field(
        None, description="Optional screening case ID to which access is granted"
    )
    terms_version: str = Field(
        "v1.0", description="Version of the consent agreement terms"
    )
    expires_in_days: Optional[int] = Field(
        None, description="Optional validity duration in days"
    )


class SharingInvitationRequest(BaseModel):
    partner_email: EmailStr = Field(
        ..., description="Email address of partner being invited"
    )
    scope: ConsentScope = Field(
        ConsentScope.SUMMARY_ONLY,
        description="Proposed disclosure scope once partner registers/accepts",
    )
    purpose: str = Field(
        "preconception_carrier_screening",
        description="Stated purpose of the partner sharing link",
    )
    case_id: Optional[int] = Field(
        None, description="Primary screening case ID reference"
    )


class ConsentGrantResponse(BaseModel):
    id: int
    granter_user_id: int
    granter_name: str
    grantee_user_id: int
    grantee_name: str
    scope: str
    status: str
    purpose: Optional[str] = None
    terms_version: Optional[str] = None
    case_id: Optional[int] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SharedFindingSummary(BaseModel):
    condition_code: str
    condition_name: str
    carrier_state: str
    inheritance_mode: str
    classification_state: Optional[str] = None
    reviewed_flag: Optional[bool] = None
    summary_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SharedCaseSummaryResponse(BaseModel):
    case_id: int
    synthetic_case_code: str
    granted_scope: str
    owner_display_name: str
    status: str
    findings: List[SharedFindingSummary]
    privacy_notice: str = (
        "Shared view authorized under recipient consent grant. "
        "Access is restricted to authorized scope and can be revoked by granter at any time."
    )

    model_config = ConfigDict(from_attributes=True)
