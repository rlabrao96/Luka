# RLS Testing for Trips

**Purpose:** Document how Task 2.7 (and every later task that exercises a `trip_*`
table directly via the `db` fixture) must establish a Postgres-side identity so
that the RLS policies shipped in commit `bf5c183` (`auth.uid()`-based) actually
gate rows the same way they will in production.

This file is research output for Phase 2 Task 2.0 of the Viajes plan.

---

## Finding: the test suite has no RLS-aware fixture today

We searched the entire test tree and `backend/modules/auth/` for any of the
following patterns:

- `auth.uid` / `request.jwt.claims` / `jwt.claim.sub`
- `set_config(...)` calls scoped to `auth.*` or `request.*`
- Any helper called `as_user`, `rls_session`, `user_client`, `set_jwt`,
  `set_user_context`, `asgi.jwt`, etc.

All searches returned **zero** hits in the test suite. The closest existing
auth machinery is the `override_auth` fixture
(`backend/tests/conftest.py:91-99`), which overrides FastAPI's
`get_current_user` dependency. That makes routes *think* a user is logged in,
but it does **not** propagate any identity to the underlying Postgres session —
so `auth.uid()` inside an RLS policy still evaluates to `NULL`.

Likewise, the `db` fixture (`backend/tests/conftest.py:14-37`) opens the
connection using `settings.database_url`. Locally that's a `postgres`
superuser; in CI/Supabase it's the pooler role. **Both bypass RLS** — the
`postgres` role is `BYPASSRLS`, and the pooler role is connected without a
`request.jwt.claims` GUC, so `auth.uid()` is null and policies that compare
`= auth.uid()` reject every row.

Existing tables already shipping RLS (`user_category_preferences` from
migration 015, `bank_credentials` from migration 017) are **not exercised
through their RLS policies in any test** — those tests run as superuser.

So the answer to "ranking the four options":

| Option | Verdict |
|---|---|
| (a) An existing helper / fixture | **Does not exist.** |
| (b) HTTP-route tests with JWT-injecting client | Does not exist; `override_auth` skips DB-level auth entirely. |
| (c) **Service-role connection that bypasses RLS** | **This is what we have today.** |
| (d) `SET LOCAL request.jwt.claims = '...'` | Does not exist anywhere in the repo. |

---

## What Task 2.7 must add

A new fixture-level helper that sets the per-transaction GUC Supabase's
`auth.uid()` reads from. Supabase's `auth.uid()` is implemented as
`(current_setting('request.jwt.claim.sub', true))::uuid` (or the equivalent
`request.jwt.claims` JSON path), so the helper just needs to write that GUC
inside the same transaction the test queries on.

**Where to add it:** extend `backend/tests/conftest.py` with a helper
fixture `as_user`. Keep it tiny:

```python
# backend/tests/conftest.py (Task 2.7 — do not add in Task 2.0)
import json
from sqlalchemy import text

@pytest.fixture
async def as_user(db):
    """Bind subsequent queries on `db` to a user id so auth.uid() resolves.

    Usage:
        await as_user(user.id)
        # any select/insert from now on, in this txn, runs as that user
    """
    async def _set(user_id):
        # set_config(..., is_local=true) scopes the GUC to the current txn,
        # which matches the SAVEPOINT lifecycle of the `db` fixture.
        await db.execute(
            text("SELECT set_config('request.jwt.claims', :c, true)").bindparams(
                c=json.dumps({"sub": str(user_id), "role": "authenticated"})
            )
        )
        await db.execute(
            text("SELECT set_config('request.jwt.claim.sub', :s, true)").bindparams(
                s=str(user_id)
            )
        )
        # Switch role away from the BYPASSRLS superuser:
        await db.execute(text("SET LOCAL ROLE authenticated"))
    return _set
```

Then in Task 2.7 RLS tests:

```python
async def test_non_member_cannot_select_trip(db, make_user, as_user):
    creator = await make_user()
    outsider = await make_user()
    # ... create trip as creator via service layer (still superuser here) ...
    await as_user(outsider.id)
    rows = (await db.execute(text("SELECT id FROM trips"))).all()
    assert rows == []  # RLS hides it
```

---

## Caveats

1. **Pooler / transaction mode.** The Supabase pooler at port 6543 runs
   transaction-mode pooling. `SET LOCAL` and `set_config(..., true)` are both
   txn-scoped, so they're safe — but `SET ROLE` *without* `LOCAL` would leak.
   Always use `SET LOCAL ROLE`.
2. **The `db` fixture wraps every test in a single transaction it rolls back
   at the end.** That's compatible with `SET LOCAL`, but it means the role
   switch only persists for the test. Any service-layer code that opens a
   *new* session will not inherit the GUC — for RLS tests, query through the
   same `db` session.
3. **Privilege.** The `authenticated` role must have `SELECT/INSERT/UPDATE/
   DELETE` grants on `trip_*`. Migration 047 enables RLS but does not grant
   table privileges; verify these grants exist (or add them) in Task 2.7
   before asserting RLS behavior, otherwise tests will fail with
   `permission denied` instead of "no rows".
4. **Superuser exception.** If `DATABASE_URL` points at a superuser
   (`postgres`), even `SET LOCAL ROLE authenticated` lets you back in if
   policies use `BYPASSRLS`. Mitigate by also forcing
   `ALTER TABLE … FORCE ROW LEVEL SECURITY` on each `trip_*` table — consider
   adding this in Task 2.7 if migration 047 omitted it.
5. **Helper scope.** Keep `as_user` private to tests. Production routes set
   `auth.uid()` via the Supabase JWT on the connection itself; we don't want
   app code calling `set_config` directly.
