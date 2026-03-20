---
name: clean-code
description: Use when asked to clean, audit, or refactor code for efficiency without changing functionality. Covers both frontend (Next.js/React/TypeScript) and backend (FastAPI/Python). Produces a full audit report first, then applies fixes.
---

# Clean Code — Audit & Refactor Without Changing Functionality

## Overview

Read first, report second, fix third. Never change what the code does — only how it does it. Every fix must be provably safe: same inputs, same outputs, same behavior.

## When to Use

- "Clean this up", "make it more efficient", "audit the code", "refactor without breaking anything"
- Performance complaints (slow load, slow API, jank)
- Code review prep — make the code defensible before a reviewer sees it

## The Process

```
1. READ all relevant files completely (no guessing)
2. REPORT every issue with: file + line + what + why it matters
3. GET confirmation before touching anything
4. FIX one category at a time — smallest blast radius first
5. VERIFY: run type check / linter after each batch
6. COMMIT with clear message per category of fix
```

## What to Look For

### Frontend (Next.js / React / TypeScript)
- **Auth waterfalls** — multiple sequential auth calls before data can load
- **Duplicate API calls** — same endpoint called in layout + component + page
- **Stale cache config** — staleTime too low causes unnecessary refetches
- **localStorage thrashing** — sync writes inside high-frequency event handlers (mousemove, scroll)
- **Dead local state** — useState that duplicates global store (Zustand/Redux)
- **Missing query guards** — `enabled: !!id` but id comes from an async source creating a waterfall
- **Unused imports** — TypeScript won't always catch these at runtime
- **SSR vs client mismatch** — `dynamic({ ssr: false })` hiding real issues

### Backend (FastAPI / Python / SQLAlchemy)
- **Missing DB indexes** — WHERE clauses on un-indexed columns (check every filter)
- **N+1 queries** — loop calling DB inside a for loop; use joinedload or batch fetch
- **Sync I/O in async functions** — `requests.get()` inside `async def` blocks the event loop
- **SELECT * queries** — fetch only columns you actually use
- **Missing LIMIT** — unbounded queries on large tables
- **Bare except** — `except:` swallows all errors including KeyboardInterrupt
- **Repeated DB session patterns** — duplicated `async with session:` boilerplate
- **Hardcoded values** — timeouts, URLs, limits that should be in config/settings
- **Missing HTTP timeouts** — `httpx.get(url)` without `timeout=` can hang forever
- **Unindexed foreign keys** — FK columns used in JOINs without indexes

## What NOT to Touch

- Business logic (what the code does)
- API contracts (endpoint paths, request/response shapes)
- Database schema (migrations are a separate task)
- Test files (unless they have obvious dead code)
- Anything with a TODO that explains intentional incompleteness

## Common Mistakes

**Changing behavior while "cleaning"** — if a function returns different values after your change, that's a bug, not a cleanup.

**Fixing style without fixing substance** — renaming variables is noise. Focus on performance, correctness, and maintainability.

**Cleaning without reading** — never suggest a fix for code you haven't read. Read the full file first.

**One giant commit** — commit by category (indexes, dead code, imports, etc.) so fixes are reviewable and reversible.

## Quick Reference: Severity Tiers

| Tier | Examples | Fix order |
|------|---------|-----------|
| Critical | Auth waterfalls, N+1 in hot paths, missing timeouts on external calls | First |
| High | Missing indexes on filtered columns, localStorage thrashing, duplicate API calls | Second |
| Medium | staleTime too low, dead local state, SELECT *, bare except | Third |
| Low | Unused imports, minor duplication, style inconsistency | Last |
