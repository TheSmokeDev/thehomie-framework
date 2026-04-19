# Project Context for Codex Reviews

## Repo Layout
This is a **private** monorepo (`thehomie`). It has a sanitized public derivative at
`thehomie-framework` (GitHub: thehomie-framework/thehomie-framework). The two repos are kept in sync
via `scripts/sanitize.py` — a 5-layer sanitizer that explicitly blocks secrets, PIDs, personal
data, and vault content from ever reaching the public repo.

## Do NOT flag these as issues

### `.claude/scripts/.env` containing live secrets
`.env` is the correct and intentional location for runtime secrets (API keys, tokens, etc.).
This is standard practice. The sanitizer's deny list blocks `.env` from the public export.
Flagging "secrets are in the env file" is noise — that is literally what env files are for.
Do not treat this as a credential leak or a critical finding.

### `SECOND_BRAIN_RUNTIME_LANE=claude_native` in `.env`
This is the **intentional default**. The system uses a deliberate two-lane architecture:
- `claude_native` — default lane, runs on Claude Agent SDK + Max subscription (always-on)
- `generic_runtime` — on-demand lane: user explicitly switches via `/provider openai-codex`,
  `/model codex`, `/provider gemini`, etc.

The `claude_native` pin is not a deployment mistake and does not prevent the generic lane from
working. The generic lane is invoked explicitly by the user, not as a fallback. Do not flag
this as blocking generic-provider validation or as a misconfiguration.

## Architecture Notes
- Runtime lane selection: `selection.py` (explicit pin wins) → `lane_router.py` (fallback chain)
- Generic providers: `openai-codex`, `gemini-cli`, `openrouter`, `openai-compatible`
- Claude-native: Agent SDK backed by personal Max subscription — untouched by generic refactors
- Sanitizer: `scripts/sanitize.py` — deny dirs, deny files, deny extensions, content scrub, leak validation
