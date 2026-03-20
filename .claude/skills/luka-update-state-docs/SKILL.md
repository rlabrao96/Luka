---
name: luka-update-state-docs
description: Use when a Luka development session is ending — user says goodbye, wraps up, or asks to disconnect. Updates the persistent state and next-steps documents so the next session starts with accurate context.
---

# Luka — Update State Docs on Session End

## Overview

At the end of every session, update the two persistent project docs so the next Claude instance (or you tomorrow) starts with accurate, current context. A verbal summary is not enough — the docs must reflect reality.

## Trigger

Any of these signal session end:
- "ok, talk tomorrow" / "we're done for today" / "bye" / "let's stop here"
- "let's wrap up" / "that's enough for today"
- User asks you to write a summary before disconnecting

## The Two Files

Both live in the **Luka project root:**

```
docs/superpowers/luka-project-state.md   ← Architecture + what's built
docs/superpowers/luka-next-steps.md      ← What needs input + gaps to close
```

---

## What to Update in Each File

### `luka-project-state.md`

Update the **"Implementation Status"** section and the **"What Is NOT Yet Implemented"** table to reflect what changed this session.

Steps:
1. Run `git log main --oneline -20` — see what was committed
2. Cross-reference with the existing status table
3. Move any newly completed items from ❌/⚠️ to ✅
4. Add new ⚠️ or ❌ items discovered during this session
5. Update the **"Date"** line at the top to today

### `luka-next-steps.md`

Update the **"Phase 3: Gaps to Close"** section and the **"Pre-First-User Checklist"**.

Steps:
1. Mark completed gaps as done or remove them
2. Add any new gaps discovered during this session
3. Update the **"Recommended Execution Order"** if the sequence changed
4. Update the **"Date"** line at the top to today

---

## Process

```
1. git log main --oneline -20           ← what changed this session
2. Read luka-project-state.md           ← find the status section
3. Edit it — move items, add items
4. Read luka-next-steps.md              ← find Phase 3 + checklist
5. Edit it — close gaps, add gaps
6. git add docs/superpowers/luka-*.md
7. git commit -m "docs: update project state after [session topic]"
8. Tell the user: "State docs updated — see you tomorrow."
```

---

## Quick Reference: Status Symbols

| Symbol | Meaning |
|--------|---------|
| ✅ | Fully implemented and tested |
| ⚠️ | Partially implemented / needs wiring |
| ❌ | Not yet started |

---

## Common Mistakes

**Just giving a verbal summary** — the docs are what persists across sessions, not your words. Always write to the files.

**Updating one doc but not the other** — state-doc reflects what IS built, next-steps reflects what still NEEDS doing. Both need to be current.

**Forgetting to commit** — an uncommitted update is lost if the worktree changes. Always commit after editing.

**Making it too long** — only update what changed. Don't rewrite sections that are still accurate.
