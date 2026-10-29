from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    details: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditEventListResponse(BaseModel):
    total: int
    events: List[AuditEventResponse]

    model_config = ConfigDict(from_attributes=True)
