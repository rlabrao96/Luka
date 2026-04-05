from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    status: str
    payload: dict | None = None
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationUpdate(BaseModel):
    status: str  # "read", "dismissed", "actioned"


class UnreadCountResponse(BaseModel):
    count: int
