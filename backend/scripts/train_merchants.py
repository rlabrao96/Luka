"""CLI tool for curating the global canonical merchant database.

Usage:
    python scripts/train_merchants.py seed --from-db [--verify] [--dry-run]
    python scripts/train_merchants.py seed --from-file merchants.json [--verify]
    python scripts/train_merchants.py review
    python scripts/train_merchants.py merge "Source Name" "Target Name"
    python scripts/train_merchants.py stats
    python scripts/train_merchants.py regroup
"""

import asyncio
import json
import sys
from pathlib import Path

import click

# Add parent dir to path so we can import backend modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402


async def _get_db_and_redis():
    import redis.asyncio as aioredis

    db = AsyncSessionLocal()
    redis = aioredis.from_url(settings.redis_url)
    return db, redis


@click.group()
def cli():
    """Luka merchant training CLI."""
    pass


@cli.command()
@click.option("--from-db", "source_db", is_flag=True, help="Pull uncategorized from database")
@click.option(
    "--from-file", "source_file", type=click.Path(exists=True), help="Load from JSON file"
)
@click.option("--verify", is_flag=True, help="Mark created merchants as verified")
@click.option("--dry-run", is_flag=True, help="Preview without writing")
def seed(source_db, source_file, verify, dry_run):
    """Seed canonical merchants from DB or file."""
    if source_db:
        asyncio.run(_seed_from_db(verify, dry_run))
    elif source_file:
        asyncio.run(_seed_from_file(source_file, verify, dry_run))
    else:
        click.echo("Specify --from-db or --from-file")


async def _seed_from_db(verify: bool, dry_run: bool):
    from sqlalchemy import select

    from modules.merchant_review.llm_grouping import group_raw_merchants
    from modules.merchant_review.service import create_canonicals_from_groups
    from modules.merchants.models import Merchant
    from modules.merchants.service import lookup_merchant
    from modules.transactions.models import Transaction

    db, redis = await _get_db_and_redis()
    try:
        # Get unique raw names without canonical
        result = await db.execute(
            select(Transaction.raw_merchant_name)
            .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
            .where(Merchant.canonical_merchant_id.is_(None) | Merchant.id.is_(None))
            .distinct()
        )
        raw_names = [r[0] for r in result.all() if r[0]]

        click.echo(f"Found {len(raw_names)} uncategorized raw merchant names")

        if not raw_names:
            click.echo("Nothing to process.")
            return

        # Phase 1: Group
        click.echo("Running LLM grouping...")
        groups = await group_raw_merchants(raw_names)
        click.echo(f"LLM grouped into {len(groups)} canonical merchants")

        for g in groups:
            click.echo(f"  {g['display_name']}: {', '.join(g['raw_names'])}")

        if dry_run:
            click.echo("\n[DRY RUN] No changes written.")
            return

        # Create canonicals
        canonicals = await create_canonicals_from_groups(db, groups)
        await db.commit()

        # Phase 2: Categorize
        click.echo("Categorizing...")
        for i, group in enumerate(groups):
            info = canonicals[i]
            if not info.get("is_new"):
                continue
            first_raw = group["raw_names"][0]
            categories = await lookup_merchant(first_raw, db, redis)
            if categories:
                from modules.merchant_review.models import CanonicalMerchant

                cm = await db.execute(
                    select(CanonicalMerchant).where(
                        CanonicalMerchant.display_name == group["display_name"]
                    )
                )
                canonical = cm.scalar_one_or_none()
                if canonical:
                    canonical.default_category = categories[0]
                    if verify:
                        canonical.is_verified = True
                    click.echo(f"  {group['display_name']} -> {categories[0]}")

        await db.commit()
        click.echo(
            f"\nDone! Created {len([c for c in canonicals if c.get('is_new')])} canonical merchants."
        )
    finally:
        await db.close()
        await redis.aclose()


async def _seed_from_file(path: str, verify: bool, dry_run: bool):
    from sqlalchemy import select

    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    with open(path) as f:
        data = json.load(f)

    click.echo(f"Loaded {len(data)} merchant entries from {path}")

    if dry_run:
        for entry in data:
            click.echo(
                f"  {entry['display_name']}: {', '.join(entry['raw_names'])} -> {entry.get('category', 'N/A')}"
            )
        click.echo("\n[DRY RUN] No changes written.")
        return

    db, _ = await _get_db_and_redis()
    try:
        for entry in data:
            # Get or create canonical
            result = await db.execute(
                select(CanonicalMerchant).where(
                    CanonicalMerchant.display_name == entry["display_name"]
                )
            )
            canonical = result.scalar_one_or_none()
            if not canonical:
                canonical = CanonicalMerchant(
                    display_name=entry["display_name"],
                    default_category=entry.get("category"),
                    is_verified=verify,
                )
                db.add(canonical)
                await db.flush()

            # Link raw names
            for raw_name in entry.get("raw_names", []):
                mr = await db.execute(select(Merchant).where(Merchant.raw_name == raw_name))
                merchant = mr.scalar_one_or_none()
                if merchant:
                    merchant.canonical_merchant_id = canonical.id
                else:
                    db.add(
                        Merchant(
                            raw_name=raw_name,
                            normalized_name=raw_name,
                            canonical_merchant_id=canonical.id,
                        )
                    )

            click.echo(f"  {entry['display_name']} -> {entry.get('category', 'N/A')}")

        await db.commit()
        click.echo(f"\nDone! Processed {len(data)} merchants.")
    finally:
        await db.close()


@cli.command()
def review():
    """Interactive review of unverified canonical merchants."""
    asyncio.run(_interactive_review())


async def _interactive_review():
    from sqlalchemy import select, func

    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant
    from modules.transactions.models import Transaction

    db, _ = await _get_db_and_redis()
    try:
        result = await db.execute(
            select(CanonicalMerchant)
            .where(CanonicalMerchant.is_verified == False)  # noqa: E712
            .order_by(CanonicalMerchant.created_at)
        )
        canonicals = list(result.scalars().all())
        click.echo(f"\n{len(canonicals)} unverified merchants to review\n")

        for cm in canonicals:
            # Get linked raw names
            mr = await db.execute(
                select(Merchant.raw_name).where(Merchant.canonical_merchant_id == cm.id)
            )
            raw_names = [r[0] for r in mr.all()]

            # Get transaction stats
            stats = await db.execute(
                select(func.count(), func.sum(Transaction.amount)).where(
                    Transaction.raw_merchant_name.in_(raw_names)
                )
            )
            count, total = stats.one()

            click.echo(f"Display name: {cm.display_name}")
            click.echo(f"Category: {cm.default_category or 'None'}")
            click.echo(f"Grouped from: {', '.join(raw_names)}")
            click.echo(f"Transactions: {count} (total: ${abs(total or 0):,.0f})")

            action = click.prompt(
                "-> (a)pprove  (e)dit  (s)kip  (m)erge into another  (q)uit",
                type=click.Choice(["a", "e", "s", "m", "q"]),
            )

            if action == "q":
                break
            elif action == "a":
                cm.is_verified = True
                await db.commit()
                click.echo("Approved\n")
            elif action == "e":
                new_name = click.prompt("New display name", default=cm.display_name)
                new_cat = click.prompt("New category", default=cm.default_category or "")
                cm.display_name = new_name
                if new_cat:
                    cm.default_category = new_cat
                cm.is_verified = True
                await db.commit()
                click.echo("Updated & approved\n")
            elif action == "m":
                target_name = click.prompt("Merge into (display name)")
                tr = await db.execute(
                    select(CanonicalMerchant).where(CanonicalMerchant.display_name == target_name)
                )
                target = tr.scalar_one_or_none()
                if not target:
                    click.echo(f"Not found: {target_name}\n")
                    continue
                # Move all merchant links
                await db.execute(
                    Merchant.__table__.update()
                    .where(Merchant.canonical_merchant_id == cm.id)
                    .values(canonical_merchant_id=target.id)
                )
                await db.delete(cm)
                await db.commit()
                click.echo(f"Merged into {target_name}\n")
            else:
                click.echo("Skipped\n")
    finally:
        await db.close()


@cli.command()
@click.argument("source")
@click.argument("target")
def merge(source, target):
    """Merge source canonical merchant into target."""
    asyncio.run(_merge(source, target))


async def _merge(source_name: str, target_name: str):
    from sqlalchemy import select

    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    db, _ = await _get_db_and_redis()
    try:
        sr = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.display_name == source_name)
        )
        source = sr.scalar_one_or_none()
        tr = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.display_name == target_name)
        )
        target = tr.scalar_one_or_none()

        if not source:
            click.echo(f"Source not found: {source_name}")
            return
        if not target:
            click.echo(f"Target not found: {target_name}")
            return

        await db.execute(
            Merchant.__table__.update()
            .where(Merchant.canonical_merchant_id == source.id)
            .values(canonical_merchant_id=target.id)
        )
        await db.delete(source)
        await db.commit()
        click.echo(f"Merged '{source_name}' into '{target_name}'")
    finally:
        await db.close()


@cli.command()
def stats():
    """Show global merchant database statistics."""
    asyncio.run(_stats())


async def _stats():
    from sqlalchemy import select, func

    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    db, _ = await _get_db_and_redis()
    try:
        total = await db.execute(select(func.count()).select_from(CanonicalMerchant))
        verified = await db.execute(
            select(func.count())
            .select_from(CanonicalMerchant)
            .where(CanonicalMerchant.is_verified == True)  # noqa: E712
        )
        unverified = await db.execute(
            select(func.count())
            .select_from(CanonicalMerchant)
            .where(CanonicalMerchant.is_verified == False)  # noqa: E712
        )
        linked = await db.execute(
            select(func.count())
            .select_from(Merchant)
            .where(Merchant.canonical_merchant_id.isnot(None))
        )
        unlinked = await db.execute(
            select(func.count())
            .select_from(Merchant)
            .where(Merchant.canonical_merchant_id.is_(None))
        )

        click.echo(f"Canonical merchants: {total.scalar_one()}")
        click.echo(f"  Verified: {verified.scalar_one()}")
        click.echo(f"  Unverified: {unverified.scalar_one()}")
        click.echo(
            f"Merchant raw names: {linked.scalar_one()} linked, {unlinked.scalar_one()} unlinked"
        )
    finally:
        await db.close()


@cli.command()
def regroup():
    """Re-run LLM grouping on all unverified merchants."""
    asyncio.run(_regroup())


async def _regroup():
    from sqlalchemy import select

    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchant_review.llm_grouping import group_raw_merchants
    from modules.merchant_review.service import create_canonicals_from_groups
    from modules.merchants.models import Merchant

    db, _ = await _get_db_and_redis()
    try:
        # Get all unverified canonical merchants
        result = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.is_verified == False)  # noqa: E712
        )
        old_canonicals = list(result.scalars().all())

        # Collect all their raw names
        raw_names = []
        for cm in old_canonicals:
            mr = await db.execute(
                select(Merchant.raw_name).where(Merchant.canonical_merchant_id == cm.id)
            )
            raw_names.extend([r[0] for r in mr.all()])

        if not raw_names:
            click.echo("No unverified merchants to regroup.")
            return

        click.echo(
            f"Regrouping {len(raw_names)} raw names from {len(old_canonicals)} unverified merchants..."
        )

        # Unlink all
        for cm in old_canonicals:
            await db.execute(
                Merchant.__table__.update()
                .where(Merchant.canonical_merchant_id == cm.id)
                .values(canonical_merchant_id=None)
            )
            await db.delete(cm)
        await db.commit()

        # Re-run grouping
        groups = await group_raw_merchants(raw_names)
        await create_canonicals_from_groups(db, groups)
        await db.commit()

        click.echo(f"Regrouped into {len(groups)} canonical merchants:")
        for g in groups:
            click.echo(f"  {g['display_name']}: {', '.join(g['raw_names'])}")
    finally:
        await db.close()


if __name__ == "__main__":
    cli()
