from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawEmail:
    message_id: str
    subject: str
    sender: str
    body: str
    received_at: datetime


@dataclass
class ParsedEmail:
    amount: int  # smallest unit: CLP integer or USD cents
    raw_merchant: str  # original string from email, e.g. "COMPRA LIDER PROVI"
    transaction_date: datetime
    bank_name: str  # inferred from sender/subject
    transaction_type: str = "expense"  # "expense" or "transfer"
    currency: str = "CLP"  # ISO 4217: "CLP" or "USD"


class EmailProvider(ABC):
    @abstractmethod
    async def setup_watch(self, user_id: str) -> dict: ...

    @abstractmethod
    async def fetch_new_emails(self, user_id: str, **kwargs) -> list[RawEmail]: ...

    @abstractmethod
    async def renew_watch(self, user_id: str) -> dict: ...
