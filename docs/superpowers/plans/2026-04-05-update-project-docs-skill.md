# Update-Project-Docs Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a generic Claude Code skill that scans any codebase and generates/updates README.md, ARCHITECTURE.md, and NEXT-STEPS.md at the project root. Replace the Luka-specific `luka-update-state-docs` skill.

**Architecture:** Single SKILL.md file with comprehensive instructions for Claude to follow. No code to write — this is a prompt-engineering task. The skill tells Claude what to scan, how to structure each doc, and how to handle edge cases.

**Tech Stack:** Claude Code skills (SKILL.md format), git

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `~/.claude/skills/update-project-docs/SKILL.md` | The new generic skill |
| Modify | `~/.claude/projects/-Users-rlabrao-Documents-Proyectos-AI-Finanzas-Personales/memory/MEMORY.md` | Update references to new skill |

---

### Task 1: Write the new SKILL.md

**Files:**
- Create: `~/.claude/skills/update-project-docs/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/skills/update-project-docs
```

- [ ] **Step 2: Write the SKILL.md file**

Write `~/.claude/skills/update-project-docs/SKILL.md` with the following content:

The file must include these sections in order:

1. **Frontmatter** — name: `update-project-docs`, description covering both triggers (session end + manual invocation)
2. **Overview** — what the skill does, the three output files, generic (not project-specific)
3. **Triggers** — session-end signals + manual invocation keywords
4. **Scan Levels** — medium (default) vs deep (on request), with exact file patterns to read for each
5. **README.md Template** — section headings and what goes in each
6. **ARCHITECTURE.md Template** — section headings and what goes in each
7. **NEXT-STEPS.md Template** — section headings, sources for pending items (carry forward, TODO/FIXME grep, incomplete integrations, stubs)
8. **Content Merge Strategy** — overwrite template-matching sections, preserve custom sections
9. **Generic Discovery** — how to detect language, framework, project name, DB, hosting from config files
10. **Staleness Detection** — removed features, new features, renamed items, completed items
11. **CLAUDE.md Staleness Check** — read CLAUDE.md, flag stale references, do NOT auto-edit
12. **Process Flow** — numbered steps including confirmation on session-end, commit, push
13. **Error Handling** — no config files, push failure, no git repo, accidental trigger
14. **Common Mistakes** — same spirit as old skill but updated

Key requirements for the SKILL.md content:
- MUST be fully generic — zero references to "Luka", specific modules, or specific tech
- MUST include the medium scan file patterns: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.csproj`, main entry points, `**/router.py`, `**/routes.ts`, `**/models.py`, `schema.prisma`, worker/job files, migration directory listing, `.env.example`, frontend `app/` structure, `git log --oneline -20`
- MUST include the deep scan additions: service files, frontend components, test files, CI/CD configs, full migration reading, existing doc cross-reference
- MUST include session-end confirmation prompt: "Update project docs? (y/n)"
- MUST include commit message format: `docs: update project docs — {brief summary}`
- MUST include push-on-failure handling: commit locally, warn user

- [ ] **Step 3: Verify the skill file exists and has correct frontmatter**

```bash
head -5 ~/.claude/skills/update-project-docs/SKILL.md
```

Expected: frontmatter with `name: update-project-docs`

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add skills/update-project-docs/SKILL.md && git commit -m "feat: add generic update-project-docs skill"
```

Note: If `~/.claude` is not a git repo, skip this step.

---

### Task 2: Update memory references

**Files:**
- Modify: `~/.claude/projects/-Users-rlabrao-Documents-Proyectos-AI-Finanzas-Personales/memory/MEMORY.md`

- [ ] **Step 1: Update MEMORY.md**

Make these edits:

1. Under "## Project State Docs" — change references from `luka-project-state.md` / `luka-next-steps.md` to the new root-level files:
   - `README.md` — project overview, modules, quick start
   - `ARCHITECTURE.md` — detailed system design, endpoints, data model
   - `NEXT-STEPS.md` — verified pending work and TODOs
   - Note: old docs in `docs/superpowers/` kept as historical archive

2. Under "## Personal Skill" — change from `luka-update-state-docs` to `update-project-docs`

3. Under "## Reference Files" — remove the Fintoc API reference (Fintoc was removed from the project)

4. Under "## Key Architectural Decisions" — remove the Fintoc reference in the ARQ worker line

- [ ] **Step 2: Verify the changes**

Read the updated MEMORY.md and confirm no stale Fintoc or old-skill references remain.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude/projects/-Users-rlabrao-Documents-Proyectos-AI-Finanzas-Personales/memory && git add MEMORY.md && git commit -m "docs: update memory — new update-project-docs skill, remove stale Fintoc refs"
```

Note: If this directory is not a git repo, skip.

---

### Task 3: First run — generate the three docs for this project

**Files:**
- Create/Overwrite: `README.md` (project root)
- Create: `ARCHITECTURE.md` (project root)
- Create: `NEXT-STEPS.md` (project root)

- [ ] **Step 1: Invoke the new skill manually**

Tell Claude: "Update project docs" — this triggers the new skill for the first time on the Luka project.

The skill should:
1. Do a medium scan of the codebase
2. Generate all three files at the project root
3. Cross-reference against reality (no Fintoc, correct module list, etc.)
4. Run CLAUDE.md staleness check
5. Report findings

- [ ] **Step 2: Review the generated docs**

Verify:
- README.md mentions no Fintoc, includes Luka Connect + Plaid
- ARCHITECTURE.md has accurate endpoint list, correct worker queue setup (fast/slow)
- NEXT-STEPS.md has zero already-completed items
- All three are at project root (not in docs/)

- [ ] **Step 3: Commit and push**

```bash
git add README.md ARCHITECTURE.md NEXT-STEPS.md
git commit -m "docs: initial generation from update-project-docs skill"
git push
```

---

### Task 4: Verify skill triggers correctly

- [ ] **Step 1: Test session-end trigger**

In a new conversation, say "let's wrap up" and verify the skill:
1. Asks "Update project docs? (y/n)"
2. On "y", scans and updates the three files
3. Commits and pushes

- [ ] **Step 2: Test manual invocation**

In a new conversation, say "update project docs" and verify:
1. Proceeds directly (no y/n confirmation)
2. Scans and updates
3. Commits and pushes

- [ ] **Step 3: Test deep scan**

Say "do a deep scan and update project docs" and verify it reads additional files (services, components, tests).
