import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool
    phone_whatsapp: str | None = None
    household_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class WhatsAppVerifyRequest(BaseModel):
    phone: str
    pin: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone_whatsapp: str | None = None


class StoreProviderTokensRequest(BaseModel):
    provider_token: str
    provider_refresh_token: str | None = None
