import uuid
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modules.settings.models import NotificationPreference, UserCategoryPreference

EXPENSE_CATEGORIES = [
    "Alimentación",
    "Supermercado",
    "Transporte",
    "Combustible",
    "Entretenimiento",
    "Salud",
    "Farmacia",
    "Hogar",
    "Ropa",
    "Tecnología",
    "Educación",
    "Viajes",
    "Servicios",
    "Otros",
]

INCOME_CATEGORIES = [
    "Sueldo",
    "Freelance",
    "Inversiones",
    "Arriendo",
    "Bono",
    "Transferencia de terceros",
    "Deuda pendiente",
    "Otros ingresos",
]

ALL_CATEGORIES = EXPENSE_CATEGORIES + INCOME_CATEGORIES


async def get_notification_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> NotificationPreference:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id, whatsapp_enabled=True)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


async def update_notification_preferences(
    db: AsyncSession, user_id: uuid.UUID, whatsapp_enabled: bool
) -> NotificationPreference:
    stmt = (
        pg_insert(NotificationPreference)
        .values(user_id=user_id, whatsapp_enabled=whatsapp_enabled)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={"whatsapp_enabled": whatsapp_enabled, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.commit()
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return result.scalar_one()


async def get_category_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(UserCategoryPreference)
        .where(UserCategoryPreference.user_id == user_id)
        .order_by(UserCategoryPreference.sort_order)
    )
    prefs = result.scalars().all()
    if prefs:
        return [
            {"category": p.category, "sort_order": p.sort_order, "hidden": p.hidden} for p in prefs
        ]
    return [
        {"category": cat, "sort_order": i, "hidden": False} for i, cat in enumerate(ALL_CATEGORIES)
    ]


async def update_category_preferences(
    db: AsyncSession, user_id: uuid.UUID, categories: list[dict]
) -> list[dict]:
    for item in categories:
        if item["category"] not in ALL_CATEGORIES:
            raise ValueError(f"Unknown category: {item['category']}")
    await db.execute(
        delete(UserCategoryPreference).where(UserCategoryPreference.user_id == user_id)
    )
    for item in categories:
        db.add(
            UserCategoryPreference(
                user_id=user_id,
                category=item["category"],
                sort_order=item["sort_order"],
                hidden=item.get("hidden", False),
            )
        )
    await db.commit()
    return categories


async def delete_user_account(db: AsyncSession, user_id: uuid.UUID) -> None:
    from modules.transactions.models import Transaction, TransactionSplit
    from modules.households.models import (
        BankAccount,
        Household,
        HouseholdBudget,
        HouseholdBudgetAllocation,
        HouseholdMember,
    )
    from modules.auth.models import User

    hm_result = await db.execute(select(HouseholdMember).where(HouseholdMember.user_id == user_id))
    membership = hm_result.scalar_one_or_none()
    household_id = membership.household_id if membership else None

    user_txn_ids = select(Transaction.id).where(Transaction.user_id == user_id)
    await db.execute(
        delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(user_txn_ids))
    )
    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await db.execute(delete(BankAccount).where(BankAccount.user_id == user_id))
    await db.execute(delete(HouseholdMember).where(HouseholdMember.user_id == user_id))
    await db.execute(
        delete(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    await db.execute(
        delete(UserCategoryPreference).where(UserCategoryPreference.user_id == user_id)
    )

    if household_id:
        remaining = await db.execute(
            select(HouseholdMember).where(HouseholdMember.household_id == household_id)
        )
        if not remaining.scalars().first():
            await db.execute(
                delete(HouseholdBudgetAllocation).where(
                    HouseholdBudgetAllocation.household_id == household_id
                )
            )
            await db.execute(
                delete(HouseholdBudget).where(HouseholdBudget.household_id == household_id)
            )
            await db.execute(delete(Household).where(Household.id == household_id))

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
