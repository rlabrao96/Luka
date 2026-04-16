import uuid
from sqlalchemy import Boolean, CHAR, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class UserCurrency(Base):
    __tablename__ = "user_currencies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    currency_code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
