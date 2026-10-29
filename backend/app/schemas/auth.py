from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., json_schema_extra={"example": "patient.a@wadih.demo"})
    password: str = Field(..., min_length=6, json_schema_extra={"example": "DemoPassword123!"})


class DemoSessionRequest(BaseModel):
    persona: str = Field(..., description="Synthetic demo persona ('patient_a', 'patient_b', 'counsellor')")


class CurrentUserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    display_name: Optional[str] = None
    preferred_language: str = "en"
    literacy_mode: str = "standard"
    is_demo_session: bool = False
    token_scope: str = "standard"

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_demo: bool = False
    scope: str = "standard"
    user: CurrentUserResponse


class LogoutResponse(BaseModel):
    message: str = "Successfully logged out."
