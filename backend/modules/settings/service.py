import uuid
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modules.settings.models import NotificationPreference, UserCategoryPreference

_DEFAULT_CATEGORIES = [
    ("Alimentación", "expense", 0),
    ("Arriendo/Hipoteca", "expense", 1),
    ("Cuentas", "expense", 2),
    ("Combustible", "expense", 3),
    ("Deporte", "expense", 4),
    ("Educación", "expense", 5),
    ("Entretenimiento", "expense", 6),
    ("Farmacia", "expense", 7),
    ("Hogar", "expense", 8),
    ("Inversiones", "expense", 9),
    ("Ropa", "expense", 10),
    ("Salud", "expense", 11),
    ("Servicios", "expense", 12),
    ("Supermercado", "expense", 13),
    ("Tecnología", "expense", 14),
    ("Transporte", "expense", 15),
    ("Viajes", "expense", 16),
    ("Otros", "expense", 17),
    ("Sueldo", "income", 0),
    ("Freelance", "income", 1),
    ("Inversiones", "income", 2),
    ("Bono", "income", 3),
    ("Transferencia de terceros", "income", 4),
    ("Deuda pendiente", "income", 5),
    ("Otros ingresos", "income", 6),
]


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


def _pref_to_dict(p: UserCategoryPreference) -> dict:
    return {
        "category": p.category,
        "sort_order": p.sort_order,
        "category_type": p.category_type,
        "is_custom": p.is_custom,
    }


async def get_category_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(UserCategoryPreference)
        .where(UserCategoryPreference.user_id == user_id)
        .order_by(UserCategoryPreference.category_type, UserCategoryPreference.sort_order)
    )
    prefs = result.scalars().all()
    if not prefs:
        for category, category_type, sort_order in _DEFAULT_CATEGORIES:
            db.add(
                UserCategoryPreference(
                    user_id=user_id,
                    category=category,
                    category_type=category_type,
                    is_custom=False,
                    sort_order=sort_order,
                )
            )
        await db.commit()
        result = await db.execute(
            select(UserCategoryPreference)
            .where(UserCategoryPreference.user_id == user_id)
            .order_by(UserCategoryPreference.category_type, UserCategoryPreference.sort_order)
        )
        prefs = result.scalars().all()

    expense = [p for p in prefs if p.category_type == "expense"]
    income = [p for p in prefs if p.category_type == "income"]
    return [_pref_to_dict(p) for p in expense + income]


async def add_category(
    db: AsyncSession, user_id: uuid.UUID, category: str, category_type: str
) -> dict:
    category = category.strip()
    if not category:
        raise ValueError("Category name cannot be empty")
    if len(category) > 40:
        raise ValueError("Category name too long (max 40 chars)")

    count_result = await db.execute(
        select(func.count()).where(
            UserCategoryPreference.user_id == user_id,
            UserCategoryPreference.category_type == category_type,
        )
    )
    if (count_result.scalar() or 0) >= 20:
        raise ValueError(f"Limit of 20 {category_type} categories reached")

    dup_result = await db.execute(
        select(UserCategoryPreference).where(
            UserCategoryPreference.user_id == user_id,
            UserCategoryPreference.category == category,
            UserCategoryPreference.category_type == category_type,
        )
    )
    if dup_result.scalar_one_or_none() is not None:
        raise ValueError("Duplicate category name")

    max_result = await db.execute(
        select(func.max(UserCategoryPreference.sort_order)).where(
            UserCategoryPreference.user_id == user_id,
            UserCategoryPreference.category_type == category_type,
        )
    )
    max_order = max_result.scalar()
    next_order = (max_order + 1) if max_order is not None else 0

    pref = UserCategoryPreference(
        user_id=user_id,
        category=category,
        category_type=category_type,
        is_custom=True,
        sort_order=next_order,
    )
    db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return _pref_to_dict(pref)


async def reorder_categories(db: AsyncSession, user_id: uuid.UUID, items: list[dict]) -> list[dict]:
    result = await db.execute(
        select(UserCategoryPreference).where(UserCategoryPreference.user_id == user_id)
    )
    existing = {p.category: p for p in result.scalars().all()}

    submitted = {item["category"] for item in items}
    if submitted != set(existing.keys()):
        raise ValueError(
            "Submitted categories do not match existing set (no additions or deletions allowed)"
        )

    for item in items:
        existing[item["category"]].sort_order = item["sort_order"]

    await db.commit()
    return await get_category_preferences(db, user_id)


async def get_category_usage(db: AsyncSession, user_id: uuid.UUID, category: str) -> int:
    from modules.transactions.models import Transaction, TransactionSplit

    txn_ids = select(Transaction.id).where(Transaction.user_id == user_id)
    result = await db.execute(
        select(func.count()).where(
            TransactionSplit.transaction_id.in_(txn_ids),
            TransactionSplit.category == category,
        )
    )
    return result.scalar() or 0


async def delete_category(
    db: AsyncSession, user_id: uuid.UUID, category: str, reclassify_to: str | None
) -> None:
    from modules.transactions.models import Transaction, TransactionSplit
    from modules.merchants.models import MerchantCategorySelection

    if reclassify_to is not None:
        check = await db.execute(
            select(UserCategoryPreference).where(
                UserCategoryPreference.user_id == user_id,
                UserCategoryPreference.category == reclassify_to,
            )
        )
        if check.scalar_one_or_none() is None:
            raise ValueError(f"Reclassify target '{reclassify_to}' not found in your categories")

        txn_ids = select(Transaction.id).where(Transaction.user_id == user_id)
        await db.execute(
            update(TransactionSplit)
            .where(
                TransactionSplit.transaction_id.in_(txn_ids),
                TransactionSplit.category == category,
            )
            .values(category=reclassify_to)
        )
        await db.execute(
            update(Transaction)
            .where(Transaction.user_id == user_id, Transaction.category == category)
            .values(category=reclassify_to)
        )

    await db.execute(
        delete(MerchantCategorySelection).where(
            MerchantCategorySelection.user_id == user_id,
            MerchantCategorySelection.category == category,
        )
    )
    await db.execute(
        delete(UserCategoryPreference).where(
            UserCategoryPreference.user_id == user_id,
            UserCategoryPreference.category == category,
        )
    )
    await db.commit()


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
