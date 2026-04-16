from pydantic import BaseModel


class UserCurrencyOut(BaseModel):
    currency_code: str
    is_primary: bool
    sort_order: int
    model_config = {"from_attributes": True}


class AddCurrencyBody(BaseModel):
    currency_code: str
