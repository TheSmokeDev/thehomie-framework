---
name: vault-sync
description: "Sync completed work into the active coding vault and project memory. Reads a PRD, plan, or completion summary, then updates vault CLAUDE.md with feature documentation and MEMORY.md with implementation status. Use PROACTIVELY after completing any PRD phase, major feature, or project milestone — even if the user just says 'document this', 'update the vault', 'capture what we built', or 'record this completion'. Also triggers on: sync vault, update memory, log this work, mark as complete."
---

# /vault-sync — Document Completed Work

Reads a source document (PRD, plan, session summary) and updates the coding vault's CLAUDE.md and project MEMORY.md with what was built, when, and key stats.

## Usage

```
/vault-sync PRDs/PRD-obsidian-vault-wow.md          # From a PRD file
/vault-sync "Completed ISR build hardening"           # From a description
/vault-sync --dry-run PRDs/PRD-some-feature.md       # Preview changes without writing
```

## Target Resolution

Resolve the documentation targets in this order:

1. Explicit user-provided target paths or repo-specific instructions
2. Environment overrides, if present:
   - `THEHOMIE_VAULT_CLAUDE_PATH`
   - `THEHOMIE_PROJECT_MEMORY_PATH`
   - `THEHOMIE_VAULT_VALIDATOR`
3. Detect from current working directory:
   - **Vault CLAUDE.md**: Look for `CLAUDE.md` in the repo root or parent coding vault
   - **Project MEMORY.md**: `~/.claude/projects/{encoded-cwd}/memory/MEMORY.md`
   - **Vault validator**: `vault.py validate` if present in the vault's skill scripts

If the work belongs to a specific deployment repo, use that repo's project memory path.

## Workflow

### Step 1: Read the Source

If the argument is a file path, read it. If it's a quoted description, use the conversation context.

Extract from the source:
- **Project name** and one-line description
- **Phases/steps completed** with dates
- **Key deliverables** (files created, features built, counts/stats)
- **Completion status** (complete, partial, in-progress)
- **Commit hash** if available (from git log or conversation)

### Step 2: Read Current State

Read both target files in parallel:
- Vault CLAUDE.md — understand existing sections, tables, lists
- Project MEMORY.md — find "Implementation Status" section, note current line count

### Step 3: Plan Updates

Before editing, determine exactly what changes are needed. Present the plan to the user if `--dry-run` was specified.

**For vault CLAUDE.md** — add or update documentation:

| Source Content | Vault Update |
|---------------|-------------|
| New Obsidian/vault features | Add subsection under "Obsidian Features" |
| PRD completed | Update PRDs table — change `status` column |
| PRD created | Add row to PRDs table |
| New decision made | Add bullet to "Key Decisions" list |
| New hub/MOC notes | Add to "Hub Notes" or "Maps of Content" |
| Infrastructure change | Add to "Quick Reference" if broadly useful |

Keep the CLAUDE.md structure consistent — insert into existing sections rather than creating one-off sections. Match the format of surrounding entries.

**For MEMORY.md** — update implementation tracking:

| Source Content | Memory Update |
|---------------|-------------|
| Work completed | Add/update "Implementation Status" line |
| Build gotcha discovered | Add to "Build Gotchas" section |
| Architectural decision | Add to "Architectural Decisions" section |
| New tool/credential | Add to relevant section |
| Status change | Update existing status line |

Format for Implementation Status entries:
```
- {Project Name}: {STATUS} [{commit}] -- {brief description}
```

Valid statuses: `COMPLETE`, `IN-PROGRESS`, `PLANNED`, `EVAL'D`, `PENDING`, `NOT STARTED`

### Step 4: Make Edits

Use the **Edit** tool (not Write) for surgical updates:
- Match existing formatting, indentation, and style
- Add new items at the logical position within the relevant section
- Don't rewrite surrounding content
- Don't add duplicate entries — if already documented, update the existing line

### Step 5: Validate

Run both checks:

```bash
<resolved vault validator>
```
Expected: same or higher note count, 0 issues. If the active vault does not use this validator, skip it and state why.

```bash
wc -l "<resolved project MEMORY.md>"
```
Must be under 200 lines. If approaching the limit, consolidate rather than truncate.

### Step 6: Report

Summarize concisely:
- Files modified (with line numbers of changes)
- Sections added or updated
- Vault validation result (X/X clean)
- MEMORY.md line count (X/200)

## Rules

1. **Never duplicate** — check if the work is already documented before adding
2. **Surgical edits** — use Edit tool, never rewrite entire files
3. **Match style** — follow existing formatting patterns in both files
4. **Under 200 lines** — MEMORY.md has a hard truncation limit; be concise
5. **Validate after** — always run vault.py validate + wc -l check
6. **Don't touch note content** — only update CLAUDE.md and MEMORY.md, not individual vault notes
7. **Preserve wiki-links** — vault CLAUDE.md uses `[[wiki-links]]`; maintain that format
8. **Read before edit** — always Read both files before making any edits
9. **One status line per project** — don't scatter the same project across multiple status entries
10. **Commit hash when available** — include `(hash)` in status line for traceability
