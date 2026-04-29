"""Identify (and optionally delete) orphan merchant_review notifications.

A notification is "orphan" when:
  - its linked MerchantReviewJob no longer exists, OR
  - the linked job has 0 unverified canonical merchants left.

Usage:
    python -m scripts.cleanup_orphan_notifications              # dry-run (default)
    python -m scripts.cleanup_orphan_notifications --apply      # actually delete
    python -m scripts.cleanup_orphan_notifications --email X    # restrict to one user
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from typing import Optional

from sqlalchemy import select, func

from core.database import AsyncSessionLocal
from modules.auth.models import User
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.notifications.models import Notification


async def _unverified_count(db, job: MerchantReviewJob) -> int:
    q = (
        select(func.count())
        .select_from(CanonicalMerchant)
        .where(
            CanonicalMerchant.review_job_id == job.id,
            CanonicalMerchant.is_verified.is_(False),
        )
    )
    return (await db.execute(q)).scalar_one()


async def main(email: Optional[str], apply: bool) -> int:
    async with AsyncSessionLocal() as db:
        user_filter = []
        if email:
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u:
                print(f"no user for {email}")
                return 1
            user_filter = [Notification.user_id == u.id]
            print(f"scoping to user {u.email} ({u.id})")

        notifs = (
            (
                await db.execute(
                    select(Notification)
                    .where(Notification.type == "merchant_review", *user_filter)
                    .order_by(Notification.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

        orphans: list[tuple[Notification, str]] = []
        for n in notifs:
            sync_job_id = (n.payload or {}).get("sync_job_id")
            if not sync_job_id:
                orphans.append((n, "no sync_job_id in payload"))
                continue
            try:
                job_uuid = uuid.UUID(sync_job_id)
            except (TypeError, ValueError):
                orphans.append((n, f"invalid sync_job_id: {sync_job_id!r}"))
                continue
            job = (
                await db.execute(select(MerchantReviewJob).where(MerchantReviewJob.id == job_uuid))
            ).scalar_one_or_none()
            if job is None:
                orphans.append((n, "linked job missing"))
                continue
            remaining = await _unverified_count(db, job)
            if remaining == 0:
                orphans.append((n, "0 unverified merchants left"))

        print(
            f"\nscanned {len(notifs)} merchant_review notifications, found {len(orphans)} orphans:\n"
        )
        for n, reason in orphans:
            print(f"  {n.id}  status={n.status:<10}  title={n.title!r}  -> {reason}")

        if not apply:
            print("\n(dry-run; pass --apply to delete)")
            return 0

        if not orphans:
            print("\nnothing to delete.")
            return 0

        print(f"\nDELETING {len(orphans)} notifications...")
        for n, _ in orphans:
            # Unlink any review jobs still pointing at this notification.
            await db.execute(
                MerchantReviewJob.__table__.update()
                .where(MerchantReviewJob.notification_id == n.id)
                .values(notification_id=None)
            )
            await db.delete(n)
        await db.commit()
        print("done.")
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", default="rafaellabra96@gmail.com")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    sys.exit(asyncio.run(main(args.email, args.apply)))
