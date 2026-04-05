# Design Spec: Generic Update-Project-Docs Skill

**Date:** 2026-04-05
**Status:** Draft

---

## Problem

Project documentation drifts from reality over time. Features get implemented but not documented, old integrations get removed but references linger, and next-steps lists accumulate completed items. New Claude terminals start with stale context, leading to incorrect assumptions and wasted effort.

## Goals

1. **Easy to understand the project** — anyone (human or AI) can read the docs and know what the project is, how it works, and what's built
2. **Easy to use as context for new Claude terminals** — the docs serve as accurate, current project context
3. **Generic** — works for any project, not hardcoded to a specific codebase

## Non-Goals

- Auto-editing CLAUDE.md (only flags staleness)
- Replacing detailed API docs or inline code docs
- Tracking session-by-session changelog (git log does that)

---

## Output Files

Three living documents at the **project root**:

| File | Purpose | Target Length |
|------|---------|---------------|
| `README.md` | What the project is, tech stack, quick start, module descriptions, project structure | 150-300 lines |
| `ARCHITECTURE.md` | Detailed system design: data flow, models, endpoints, workers, integrations | 300-600 lines |
| `NEXT-STEPS.md` | Verified pending work, known bugs, infra TODOs, future ideas | 100-200 lines |

### README.md Structure

```
# {Project Name}
{One-paragraph description — discovered from codebase}

## Tech Stack
{Table: Layer | Technology — derived from package.json, pyproject.toml, etc.}

## Quick Start
{Backend + frontend setup commands — derived from existing scripts/configs}

## What {Project Name} Does
{Module-by-module descriptions — one paragraph each, grouped logically}
  - Each module: what it does, why it exists
  - No individual endpoint listing (that's in ARCHITECTURE.md)

## Project Structure
{Directory tree — derived from actual filesystem}

## Documentation
{Links to ARCHITECTURE.md, NEXT-STEPS.md, and any other relevant docs}
```

### ARCHITECTURE.md Structure

```
# Architecture

## System Overview
{High-level data flow diagram (text/ASCII)}

## Auth Flow
{How authentication works end-to-end}

## Data Model
{Tables/models and their relationships}

## API Endpoints
{Grouped by module: method, path, brief description}

## Background Jobs
{Worker tasks, queues, cron jobs}

## External Integrations
{Third-party services: what they do, how they connect}

## Frontend Architecture
{Framework, routing, state management, key components}
```

### NEXT-STEPS.md Structure

```
# Next Steps

## Pending Work
{Only items verified as NOT yet implemented — grouped by priority/area}

## Known Bugs / Tech Debt
{Issues discovered but not yet fixed}

## Infrastructure TODOs
{Env vars to set, services to deploy, configs to update}

## Future Ideas
{Not committed — ideas for later}
```

---

## Skill Specification

### Name & Location

- **Skill name:** `update-project-docs`
- **Location:** `~/.claude/skills/update-project-docs/SKILL.md`
- **Replaces:** `~/.claude/skills/luka-update-state-docs/SKILL.md` (old skill stays but is no longer referenced)

### Triggers

1. **Session end** — same signals as before: "bye", "let's wrap up", "we're done", etc.
2. **Manual invocation** — user explicitly asks to update docs, or says "update readme", "refresh project docs", etc.

### Scan Levels

#### Medium Scan (Default)

Reads the following to build an accurate picture:

- **Project root:** `package.json`, `pyproject.toml`, `Cargo.toml`, or equivalent (tech stack)
- **Directory structure:** `ls` of key directories (2 levels deep)
- **Entry points:** main app file (`main.py`, `app.ts`, `index.ts`, etc.)
- **Router/route files:** all files named `router.py`, `routes.ts`, or in `app/` directory structure
- **Model/schema files:** all files named `models.py`, `schema.prisma`, etc.
- **Worker/job files:** task definitions, queue configs
- **Migration listing:** `ls` of migrations directory (names only, for table inventory)
- **Config files:** `.env.example`, settings files (for integration inventory)
- **Frontend app structure:** page/route directory listing
- **Git log:** last 20 commits for recent context

**Approximate read volume:** ~15-25K tokens (not a hard cap — this is the typical amount of source content read)

#### Deep Scan (On Request)

Everything in medium scan, plus:

- **Service files:** business logic in each module
- **Frontend components:** key component files
- **Test files:** test inventory and coverage areas
- **CI/CD configs:** deployment pipelines
- **Full migration file reading:** actual schema changes
- **Existing documentation:** cross-reference all docs for accuracy

**Approximate read volume:** ~40-60K tokens

**Trigger:** User says "deep scan", "thorough update", "full scan", or explicitly requests it.

### Intelligence: Staleness Detection

The skill doesn't just append — it **verifies and corrects**:

1. **Removed features:** If a module/integration is referenced in docs but doesn't exist in code, remove it
2. **New features:** If a module/endpoint exists in code but isn't in docs, add it
3. **Renamed items:** If something was renamed/moved, update references
4. **Completed items:** If a next-step item is implemented in code, remove from NEXT-STEPS.md
5. **Stale references:** Flag any doc references to things that no longer exist

### CLAUDE.md Staleness Check

After updating the three docs, the skill:

1. Reads `CLAUDE.md` (project-level and user-level if accessible)
2. Checks for references to files, modules, or integrations that no longer exist
3. Reports findings to the user: "CLAUDE.md references X but it no longer exists in the codebase"
4. Does NOT auto-edit CLAUDE.md — the user decides what to do

### Content Merge Strategy

Generated sections are identified by their heading names (matching the templates above). The skill:

- **Overwrites** sections whose headings match the template (these are skill-managed)
- **Preserves** any custom sections the user added that don't match template headings
- On first run (no existing file), generates the full document from scratch

This avoids the need for HTML comment markers while preventing loss of user-authored content.

### NEXT-STEPS.md Sources

Pending items come from these sources, in priority order:

1. **Carry forward** from existing NEXT-STEPS.md (verified against code — remove completed items)
2. **TODO/FIXME comments** in source code (`grep -r "TODO\|FIXME"`)
3. **Incomplete integrations** detected during scan (e.g., env var referenced in config but not in `.env.example`)
4. **Empty/stub files** that indicate planned but unimplemented features

If no sources exist (fresh project), NEXT-STEPS.md is created with empty sections and a note: "No pending items detected."

### Process Flow

```
1. Determine scan level (medium unless user requested deep)
2. Scan codebase per scan level
3. Read existing README.md, ARCHITECTURE.md, NEXT-STEPS.md (if they exist)
4. Generate/update all three files:
   a. Cross-reference code reality vs current doc content
   b. Remove stale items
   c. Add undocumented items
   d. Preserve user-written custom sections
5. Run CLAUDE.md staleness check
6. Report findings to user (summary of what changed + any CLAUDE.md warnings)
7. On session-end trigger: ask user "Update project docs? (y/n)" before proceeding
   On manual invocation: proceed directly
8. git add README.md ARCHITECTURE.md NEXT-STEPS.md
9. git commit -m "docs: update project docs — {brief summary of changes}"
10. git push (if remote is configured and branch tracks upstream; skip + warn otherwise)
```

### Error Handling

- **No config files detected:** Generate minimal docs from directory structure + git remote name. Warn user: "Could not detect tech stack — docs may be incomplete."
- **Git push fails:** Commit succeeds locally. Warn user: "Committed locally but push failed — run `git push` manually."
- **No git repo:** Skip commit/push steps entirely. Write files and inform user.
- **Accidental session-end trigger:** The confirmation prompt ("Update project docs? y/n") prevents accidental overwrites during active conversation.

### Generic Discovery

The skill works for any project by detecting:

- **Language/framework:** from config files (`package.json` → Node/React, `pyproject.toml` → Python, `Cargo.toml` → Rust, etc.)
- **Project name:** from config files or git remote
- **Architecture pattern:** from directory structure (monorepo, backend+frontend, microservices, etc.)
- **Database:** from ORM configs, migration tools, connection strings in `.env.example`
- **Hosting:** from deployment configs (`railway.toml`, `vercel.json`, `Dockerfile`, etc.)

---

## Migration from Old Skill

1. Write new skill to `~/.claude/skills/update-project-docs/SKILL.md`
2. Update CLAUDE.md memory to reference new skill instead of `luka-update-state-docs`
3. Old skill files remain but are no longer triggered
4. Old state docs (`docs/superpowers/luka-project-state.md`, `docs/superpowers/luka-next-steps.md`) kept as historical archive

---

## Success Criteria

- A new Claude terminal reading just README.md can understand what the project is and what modules exist
- A new Claude terminal reading README.md + ARCHITECTURE.md has enough context to start working on any module
- NEXT-STEPS.md contains zero items that are already implemented
- No references to removed integrations/features in any of the three docs
- The skill works without modification on a different project
