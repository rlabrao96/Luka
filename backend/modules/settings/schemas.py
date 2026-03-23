from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    whatsapp_enabled: bool
    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    whatsapp_enabled: bool


class CategoryPreferenceItem(BaseModel):
    category: str
    sort_order: int
    hidden: bool = False
    model_config = {"from_attributes": True}


class CategoryPreferencesResponse(BaseModel):
    categories: list[CategoryPreferenceItem]


class CategoryPreferencesUpdate(BaseModel):
    categories: list[CategoryPreferenceItem]
