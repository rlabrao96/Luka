from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
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
