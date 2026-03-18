import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool
    household_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class WhatsAppVerifyRequest(BaseModel):
    phone: str  # e.g. "+56912345678"
    pin: str  # 6-digit pin
