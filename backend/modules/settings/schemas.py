import uuid
from typing import Literal
from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    whatsapp_enabled: bool
    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    whatsapp_enabled: bool


class CategoryPreferenceItem(BaseModel):
    category: str
    sort_order: int
    category_type: str
    is_custom: bool
    model_config = {"from_attributes": True}


class CategoryPreferencesResponse(BaseModel):
    categories: list[CategoryPreferenceItem]


class CategoryReorderItem(BaseModel):
    category: str
    sort_order: int


class CategoryReorderRequest(BaseModel):
    categories: list[CategoryReorderItem]


class CategoryAddRequest(BaseModel):
    category: str
    category_type: Literal["expense", "income"]


class CategoryDeleteRequest(BaseModel):
    reclassify_to: str | None = None


class CategoryUsageResponse(BaseModel):
    count: int


class HouseholdPartnerCategoryItem(BaseModel):
    category: str
    category_type: Literal["expense", "income"]
    member_ids: list[uuid.UUID]
    count: int


class HouseholdPartnerCategoriesResponse(BaseModel):
    categories: list[HouseholdPartnerCategoryItem]


class HouseholdCategoryAdoptRequest(BaseModel):
    category: str
    category_type: Literal["expense", "income"]


class HouseholdCategoryAdoptResponse(BaseModel):
    already_present: bool
    category: str | None = None
    sort_order: int | None = None
    category_type: Literal["expense", "income"] | None = None
    is_custom: bool | None = None
