import uuid
from pydantic import BaseModel, EmailStr


class CreateHouseholdRequest(BaseModel):
    name: str
    type: str  # 'individual' | 'couple'


class InviteRequest(BaseModel):
    email: EmailStr


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str

    model_config = {"from_attributes": True}
