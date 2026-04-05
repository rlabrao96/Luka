import json
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from redis.asyncio import Redis
from modules.merchants.models import Merchant, MerchantCategorySelection
from modules.merchants.normalizer import normalize_merchant
from modules.merchants.llm import categorize_with_llm

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours


async def lookup_merchant(
    raw_name: str,
    db: AsyncSession,
    redis: Redis,
) -> list[str]:
    """
    Look up merchant categories: Redis L1 → DB L2 → LLM fallback.
    Returns 1 category for known merchants, up to 3 for new merchants.
    """
    normalized = normalize_merchant(raw_name)
    cache_key = f"merchant:{normalized}"

    # L1: Redis cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # L2: Database — check if merchant + selections exist
    result = await db.execute(select(Merchant).where(Merchant.normalized_name == normalized))
    merchant = result.scalar_one_or_none()

    if merchant:
        top = await db.execute(
            select(MerchantCategorySelection)
            .where(
                MerchantCategorySelection.merchant_id == merchant.id,
                MerchantCategorySelection.user_id == None,  # noqa: E711 — legacy global rows only
            )
            .order_by(MerchantCategorySelection.count.desc())
            .limit(1)
        )
        categories = [row.category for row in top.scalars().all()]
        if not categories and merchant.llm_suggested_categories:
            categories = merchant.llm_suggested_categories[:1]
        if not categories:
            # Merchant exists but has no categories — retry LLM
            categories = await categorize_with_llm(normalized)
            if categories:
                merchant.llm_suggested_categories = categories
                await db.commit()
    else:
        # L3: LLM fallback — create merchant row
        categories = await categorize_with_llm(normalized)
        try:
            merchant = Merchant(
                raw_name=raw_name,
                normalized_name=normalized,
                llm_suggested_categories=categories,
            )
            db.add(merchant)
            await db.commit()
            await db.refresh(merchant)
        except IntegrityError:
            # Race condition: another request already created this merchant
            await db.rollback()
            result = await db.execute(
                select(Merchant).where(Merchant.normalized_name == normalized)
            )
            merchant = result.scalar_one_or_none()
            if merchant and merchant.llm_suggested_categories:
                categories = merchant.llm_suggested_categories[:1]
            logger.info("lookup_merchant: concurrent insert for %s, using existing row", raw_name)

    # Populate Redis cache
    await redis.setex(cache_key, _CACHE_TTL, json.dumps(categories))
    return categories


async def get_user_ranked_categories(
    user_id: uuid.UUID,
    raw_name: str,
    db: AsyncSession,
) -> list[str]:
    """
    Return the user's full category list ranked for this specific merchant:
      1. Categories the user has previously chosen for this merchant (count desc)
      2. Categories chosen globally for this merchant (count desc)
      3. Remaining user categories in default sort_order (expense first, then income)
    Only returns categories that exist in the user's preferences list.
    """
    from modules.settings.models import UserCategoryPreference

    normalized = normalize_merchant(raw_name)

    # Fetch all user categories in their default display order
    prefs_result = await db.execute(
        select(UserCategoryPreference)
        .where(UserCategoryPreference.user_id == user_id)
        .order_by(UserCategoryPreference.category_type, UserCategoryPreference.sort_order)
    )
    user_cats = [p.category for p in prefs_result.scalars().all()]
    if not user_cats:
        return []

    # Fetch merchant (may not exist yet)
    merchant_result = await db.execute(
        select(Merchant).where(Merchant.normalized_name == normalized)
    )
    merchant = merchant_result.scalar_one_or_none()
    if not merchant:
        return user_cats

    # User-specific selections for this merchant
    user_sel_result = await db.execute(
        select(MerchantCategorySelection).where(
            MerchantCategorySelection.merchant_id == merchant.id,
            MerchantCategorySelection.user_id == user_id,
        )
    )
    user_sel = {row.category: row.count for row in user_sel_result.scalars().all()}

    # Global (legacy) selections for this merchant as secondary signal
    global_sel_result = await db.execute(
        select(MerchantCategorySelection).where(
            MerchantCategorySelection.merchant_id == merchant.id,
            MerchantCategorySelection.user_id == None,  # noqa: E711
        )
    )
    global_sel = {row.category: row.count for row in global_sel_result.scalars().all()}

    def _rank(cat: str) -> tuple:
        u = user_sel.get(cat, 0)
        g = global_sel.get(cat, 0)
        # Lower tuple = shown first. Penalize zero counts, sort desc by count.
        return (0 if u > 0 else 1, -u, 0 if g > 0 else 1, -g)

    return sorted(user_cats, key=_rank)


async def record_category_selection(
    raw_name: str,
    category: str,
    db: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID | None = None,
) -> None:
    """Called when a user selects a final category via WhatsApp. Trains the dataset."""
    normalized = normalize_merchant(raw_name)

    result = await db.execute(select(Merchant).where(Merchant.normalized_name == normalized))
    merchant = result.scalar_one_or_none()
    if not merchant:
        return

    sel_result = await db.execute(
        select(MerchantCategorySelection).where(
            MerchantCategorySelection.merchant_id == merchant.id,
            MerchantCategorySelection.category == category,
            MerchantCategorySelection.user_id == user_id,
        )
    )
    selection = sel_result.scalar_one_or_none()
    if selection:
        selection.count += 1
    else:
        db.add(MerchantCategorySelection(
            merchant_id=merchant.id,
            category=category,
            user_id=user_id,
        ))

    merchant.total_selections += 1
    await db.commit()

    # Invalidate cache so next lookup returns fresh top category
    await redis.delete(f"merchant:{normalized}")
