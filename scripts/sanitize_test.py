"""Sanitizer tests for PRP-7e Phase 5 (and forward).

R3 NM1 fix: tests use the sanitizer's ``is_denied()`` API directly instead
of the ``--dry-run | grep`` pattern. The dry-run print is
``sorted(allowed)[:50]`` (truncated) so a stdout grep can pass falsely.
Direct API calls test the rule, not the run.

This is the FIRST test file in this suite. PRP-7f (Phase 6) extends with
the broader ``test_prp7_paths_classify_correctly`` covering all PRP-7
paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow ``import sanitize`` from the scripts/ directory regardless of where
# pytest is invoked from. ``Path(__file__).parent`` is ``scripts/``.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sanitize  # noqa: E402  (import after sys.path manipulation)


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_REL = ".claude/templates/profile-isolation-smoke.yaml"


def test_phase5_archon_template_included() -> None:
    """The PRP-7e smoke workflow template must NOT be denied by the
    sanitizer - it has to ship in the public export so consumers of
    ``thehomie-framework`` can run profile-isolation-smoke against their
    own Archon installs.

    Direct ``is_denied()`` call (R3 NM1 fix):
      - ``.claude/templates/`` is NOT in DENY_DIRS
      - ``.yaml`` is NOT in DENY_EXTENSIONS
      - the path is NOT in DENY_FILES
    Therefore ``is_denied()`` MUST return False.
    """
    assert sanitize.is_denied(TEMPLATE_REL) is False, (
        f"sanitizer denied {TEMPLATE_REL!r} - public export will be missing "
        f"the smoke workflow asset. Check DENY_DIRS / DENY_FILES / "
        f"DENY_EXTENSIONS in scripts/sanitize.py."
    )


def test_phase5_archon_template_present_on_disk() -> None:
    """The asset file must exist on disk (WS2a Task 5). Without this file,
    ``personas.archon._seed_smoke_workflow`` silently no-ops and the
    profile gets no smoke workflow. This test is the canary that the asset
    actually shipped to the repo.
    """
    asset = REPO_ROOT / TEMPLATE_REL
    assert asset.is_file(), (
        f"Smoke workflow asset missing at {asset}. WS2a Task 5 must "
        f"create this file."
    )


def test_phase5_archon_template_tracked_by_git() -> None:
    """The asset must be ``git add``'d. An untracked file would not ship in
    the public export even if the sanitizer allows it (the sanitizer
    operates on ``git ls-files`` output - that's the source of truth).
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", TEMPLATE_REL],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = result.returncode == 0
    assert tracked, (
        f"Smoke workflow asset {TEMPLATE_REL!r} is not tracked by git. "
        f"WS2a Task 5 must `git add` the file before commit. "
        f"git stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# PRP-7f Phase 6 — paperclip seam doc + runtime-state defense
# ---------------------------------------------------------------------------

PAPERCLIP_SEAM_REL = "docs/paperclip-seam.md"
# PRD-8 Phase 6 — public cabinet voice setup guide. Same surgical-lift
# discipline as paperclip-seam.md: lives under docs/ (DENY_DIRS) so an
# explicit INCLUDE_FILES allowlist + on-disk + tracked checks prove the
# doc actually ships.
CABINET_VOICE_SETUP_REL = "docs/cabinet-voice-setup.md"
BROWSEROPS_MANUAL_REL = "docs/browserops-agent-browser-manual.md"


def test_cabinet_voice_setup_in_allowlist() -> None:
    """sanitize.INCLUDE_FILES contains the public cabinet voice setup doc.

    Phase 6 contract criterion ``sanitize_include_files_allowlist_extended``.
    Catches the regression where someone removes the entry but forgets to
    delete the doc — the public export would silently drop it.
    """
    assert CABINET_VOICE_SETUP_REL in sanitize.INCLUDE_FILES, (
        f"sanitize.INCLUDE_FILES must include {CABINET_VOICE_SETUP_REL!r} so "
        f"the public mirror ships the cabinet voice setup guide. Found "
        f"INCLUDE_FILES = {sanitize.INCLUDE_FILES}"
    )


def test_cabinet_voice_setup_survives_sanitize() -> None:
    """is_denied() returns False for the public cabinet voice doc.

    Phase 6 contract criterion ``sanitize_regression_test_added``. Locks
    the layered precedence so DENY_DIRS matching ``docs/`` is overridden
    by the surgical INCLUDE_FILES lift.
    """
    assert sanitize.is_denied(CABINET_VOICE_SETUP_REL) is False, (
        f"sanitizer denied {CABINET_VOICE_SETUP_REL!r} — public mirror will "
        f"be missing the cabinet voice setup guide. Check INCLUDE_FILES + "
        f"DENY_FILES + DENY_PATTERNS layering."
    )


def test_cabinet_voice_setup_doc_present_on_disk() -> None:
    """The cabinet voice setup doc must exist on disk."""
    asset = REPO_ROOT / CABINET_VOICE_SETUP_REL
    assert asset.is_file(), (
        f"Cabinet voice setup doc missing at {asset}. PRD-8 Phase 6 must "
        f"create this file."
    )


def test_cabinet_voice_setup_doc_no_personal_refs() -> None:
    """Public doc must not leak YourBusiness / owner-specific references.

    Phase 6 contract criterion ``public_docs_cabinet_voice_setup_exists``.
    The private vault note ``vault/memory/concepts/CABINET-VOICE-SETUP.md``
    carries YourBusiness context separately.
    """
    asset = REPO_ROOT / CABINET_VOICE_SETUP_REL
    if not asset.is_file():
        pytest.skip("setup doc not present")
    content = asset.read_text(encoding="utf-8")
    forbidden = ["YourBusiness", "YourBusiness", "owner", "lastname"]
    bad: list[str] = [term for term in forbidden if term in content]
    assert not bad, f"Public docs/cabinet-voice-setup.md contains personal refs: {bad}"


def test_browserops_manual_in_allowlist() -> None:
    """The BrowserOps manual is public-safe framework context.

    It lives under docs/ (DENY_DIRS), so it must be surgically lifted rather
    than allowing broader private planning docs through.
    """
    assert BROWSEROPS_MANUAL_REL in sanitize.INCLUDE_FILES, (
        f"sanitize.INCLUDE_FILES must include {BROWSEROPS_MANUAL_REL!r} so "
        f"the public mirror ships the BrowserOps manual. Found "
        f"INCLUDE_FILES = {sanitize.INCLUDE_FILES}"
    )


def test_browserops_manual_survives_sanitize() -> None:
    """is_denied() returns False for the public BrowserOps manual."""
    assert sanitize.is_denied(BROWSEROPS_MANUAL_REL) is False, (
        f"sanitizer denied {BROWSEROPS_MANUAL_REL!r} — public mirror will "
        f"be missing the BrowserOps operating manual. Check INCLUDE_FILES + "
        f"DENY_FILES + DENY_PATTERNS layering."
    )


def test_browserops_manual_doc_no_personal_refs() -> None:
    """The BrowserOps manual must stay framework-safe."""
    asset = REPO_ROOT / BROWSEROPS_MANUAL_REL
    assert asset.is_file(), f"BrowserOps manual missing at {asset}"
    content = asset.read_text(encoding="utf-8")
    forbidden = [
        "YourBusiness",
        "YourBusiness",
        "owner",
        "lastname",
        "YourAgent",
        "@YourBot",
        "C:\\Users\\YourUser",
        "C:/Users/YourUser",
        "thehomie",
    ]
    bad: list[str] = [term for term in forbidden if term in content]
    assert not bad, f"Public docs/browserops-agent-browser-manual.md contains private refs: {bad}"


def test_prp7_paperclip_seam_doc_included() -> None:
    """The paperclip seam doc must NOT be denied by the sanitizer. It lives
    under ``docs/`` (which is in DENY_DIRS) but is surgically lifted via
    ``INCLUDE_FILES`` because it is the public Paperclip integration
    contract.

    Direct ``is_denied()`` call — proves the layered precedence in
    ``is_denied()`` (Section: Layer 4 INCLUDE_FILES override of Layer 5
    DENY_DIRS) is wired correctly.
    """
    assert sanitize.is_denied(PAPERCLIP_SEAM_REL) is False, (
        f"sanitizer denied {PAPERCLIP_SEAM_REL!r} — public mirror will "
        f"be missing the Paperclip integration seam contract. Check that "
        f"INCLUDE_FILES in scripts/sanitize.py contains this path AND "
        f"that DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS do not match it."
    )


def test_prp7_paperclip_seam_doc_present_on_disk() -> None:
    """The doc file must exist on disk. Without this file, the
    INCLUDE_FILES allowlist points at vapor and the sanitizer silently
    ships nothing (the export step only includes paths that exist).
    """
    asset = REPO_ROOT / PAPERCLIP_SEAM_REL
    assert asset.is_file(), (
        f"Paperclip seam doc missing at {asset}. PRP-7f truncated Phase "
        f"6 must create this file."
    )


def test_prp7_paperclip_seam_doc_tracked_by_git() -> None:
    """The doc must be ``git add``'d. The sanitizer reads ``git ls-files``
    as the source of truth; an untracked file is invisible to the export
    pipeline regardless of INCLUDE_FILES.
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", PAPERCLIP_SEAM_REL],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = result.returncode == 0
    assert tracked, (
        f"Paperclip seam doc {PAPERCLIP_SEAM_REL!r} is not tracked by "
        f"git. PRP-7f Phase 6 must `git add` the file before commit. "
        f"git stderr: {result.stderr!r}"
    )


def test_prp7_runtime_state_denied() -> None:
    """Runtime state files must be denied — these contain live PIDs,
    session UUIDs, lock metadata, or feature-flag state that should
    never ship in the public mirror.

    Each path is named explicitly so a regression report points at the
    exact rule that should have caught the leak.
    """
    cases = [
        # path, rule the test expects to match
        (".claude/chat/bot.pid", "DENY_FILES + DENY_EXTENSIONS .pid"),
        (".claude/chat/bot.lock", "DENY_FILES + DENY_EXTENSIONS .lock"),
        (".claude/data/state/bot.pid", "DENY_FILES + DENY_DIRS .claude/data/ + .pid"),
        (".claude/scheduled_tasks.lock", "DENY_FILES + DENY_EXTENSIONS .lock"),
        (".claude/banner-exemption.flag", "DENY_FILES + DENY_PATTERNS \\.flag$"),
    ]
    for path, rule in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny runtime state file {path!r}. "
            f"Expected catch by: {rule}. This is a near-miss leak — "
            f"runtime state must never ship publicly."
        )


def test_prp7_homie_profiles_pattern_denied() -> None:
    """Any file under ``.homie/profiles/`` (top-level OR nested) must be
    denied — these are external operator profile-state directories that
    can show up if accidentally tracked by an operator who initialized
    a profile inside the repo by mistake.

    Tested via DENY_PATTERNS regex — handles both top-level
    ``.homie/profiles/...`` and nested ``foo/.homie/profiles/...``.
    """
    nested_cases = [
        ".homie/profiles/sales/agent.yaml",
        "home/.homie/profiles/sales/CLAUDE.md",
    ]
    for path in nested_cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny {path!r} — operator profile state "
            f"would leak. Check DENY_PATTERNS regex in scripts/sanitize.py."
        )


def test_prp7_include_files_does_not_override_deny_files() -> None:
    """Class-of-bug test for PRP-7f R1 B3.

    INCLUDE_FILES must NEVER bypass DENY_FILES. If a future operator
    accidentally puts ``.claude/chat/bot.pid`` in INCLUDE_FILES (e.g.
    cargo-cult copy of the paperclip-seam allowlist entry), the file
    must STILL be denied because DENY_FILES is layer 1 (absolute).

    Try/finally save+restore (no monkeypatch fixture) to match the
    existing test style in this file.
    """
    target = ".claude/chat/bot.pid"
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_FILES for {target!r}. DENY_FILES (layer 1) MUST "
            f"win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prp7_include_files_does_not_override_deny_extensions() -> None:
    """Class-of-bug test for PRP-7f R1 B3 — extension layer.

    INCLUDE_FILES must NEVER bypass DENY_EXTENSIONS. Same shape as
    the DENY_FILES test, but exercises layer 2 (.lock extension).
    """
    target = "docs/example.lock"  # would otherwise pass DENY_DIRS via INCLUDE_FILES
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_EXTENSIONS for {target!r}. DENY_EXTENSIONS "
            f"(layer 2) MUST win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prp7_include_files_does_not_override_deny_patterns() -> None:
    """Class-of-bug test for PRP-7f R1 B3 — pattern layer.

    INCLUDE_FILES must NEVER bypass DENY_PATTERNS. Exercises layer 3
    via the ``\\.flag$`` regex.
    """
    target = "docs/example.flag"
    saved = sanitize.INCLUDE_FILES[:]
    try:
        sanitize.INCLUDE_FILES = saved + [target]
        assert sanitize.is_denied(target) is True, (
            f"layered precedence broken: INCLUDE_FILES override leaked "
            f"past DENY_PATTERNS for {target!r}. DENY_PATTERNS (layer 3) "
            f"MUST win over INCLUDE_FILES (layer 4)."
        )
    finally:
        sanitize.INCLUDE_FILES = saved


def test_prd8_claude_agents_dir_denied() -> None:
    """Domain-owner charters at .claude/agents/ must be denied from public
    export. Charters reference shipped class-of-bug history (PRs #16, #19,
    R1 B2 wrong-gate, NB1 R3 data-loss class) and competitive intel about
    framework architecture. This is not PII per se but is competitive
    leakage owner doesn't want public until CLUTCH ships intentionally.

    Existing piv-* agents at .claude/agents/piv-*.md were already private;
    the new domain-owner charters (memory-cognition-owner, runtime-chat-owner,
    personas-owner, orchestration-owner, public-export-owner) + CODEOWNERS.toml
    + _drafts/ all live under the same dir and inherit the deny rule.

    Flip to ALLOW only with explicit user approval when CLUTCH adoption goes
    public.
    """
    cases = [
        ".claude/agents/memory-cognition-owner.md",
        ".claude/agents/runtime-chat-owner.md",
        ".claude/agents/personas-owner.md",
        ".claude/agents/orchestration-owner.md",
        ".claude/agents/public-export-owner.md",
        ".claude/agents/CODEOWNERS.toml",
        ".claude/agents/_drafts/memory-cognition-analysis.md",
        ".claude/agents/piv-validator.md",  # pre-existing — still denied
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny .claude/agents/ file {path!r}. "
            f"Expected catch by: DENY_DIRS '.claude/agents/'. Domain owner "
            f"charters and CODEOWNERS.toml must stay private."
        )


# ---------------------------------------------------------------------------
# PRD-8 Phase 3 — dashboard slice sanitizer rules (WS5)
# ---------------------------------------------------------------------------

MC_PROFILE_CONTRACT_REL = "docs/mc-profile-contract.md"
DASHBOARD_README_REL = "dashboard/README.md"
DASHBOARD_OWNER_CHARTER_REL = ".claude/agents/dashboard-owner.md"


def test_dist_dirs_denied_segment_aware() -> None:
    """Dashboard build-artifact directories must be denied at any path depth.

    The segment-aware match in ``is_denied()`` (the 6daef06 hardening)
    means ``foo/dashboard/server/dist/...`` is also denied even though
    only the canonical top-level path is configured. This regression-
    gates that the segment matcher reaches into nested cases — Phase 3
    introduces a new directory tree and we want to catch any near-miss
    where a build copy ended up under another root.
    """
    cases = [
        # canonical top-level
        "dashboard/server/dist/index.js",
        "dashboard/server/dist/middleware/auth.js",
        "dashboard/web/dist/assets/index-abc123.js",
        "dashboard/web/dist/index.html",
        # nested (e.g. accidentally produced under another root)
        "release/dashboard/server/dist/index.js",
        "vendor/dashboard/web/dist/main.js",
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny dashboard build artifact {path!r}. "
            f"Expected catch by: DENY_DIRS 'dashboard/server/dist/' or "
            f"'dashboard/web/dist/' (segment-aware). Build artifacts "
            f"must never ship — bloat + possible bundled secrets."
        )


def test_node_modules_denied_segment_aware() -> None:
    """Dashboard node_modules trees must be denied at any path depth.

    Same segment-aware rationale as the dist test. ``node_modules/``
    inside the dashboard slice should never ship — license violations
    + bloat + the trees can hide secrets if a postinstall script wrote
    one.
    """
    cases = [
        "dashboard/server/node_modules/hono/package.json",
        "dashboard/web/node_modules/preact/dist/preact.mjs",
        # nested forms
        "release/dashboard/server/node_modules/hono/index.js",
        "vendor/dashboard/web/node_modules/preact/dist/preact.js",
    ]
    for path in cases:
        assert sanitize.is_denied(path) is True, (
            f"sanitizer FAILED to deny dashboard node_modules path {path!r}. "
            f"Expected catch by: DENY_DIRS 'dashboard/server/node_modules/' "
            f"or 'dashboard/web/node_modules/' (segment-aware)."
        )


def test_mc_profile_contract_doc_explicitly_included() -> None:
    """The mc-profile-contract doc must NOT be denied. It lives under
    ``docs/`` (in DENY_DIRS) but is surgically lifted via INCLUDE_FILES
    because it is the public dashboard HTTP API contract.

    Direct ``is_denied()`` call — proves the layered precedence (Layer
    4 INCLUDE_FILES override of Layer 5 DENY_DIRS) is wired correctly
    for the new entry.
    """
    assert sanitize.is_denied(MC_PROFILE_CONTRACT_REL) is False, (
        f"sanitizer denied {MC_PROFILE_CONTRACT_REL!r} — public mirror "
        f"will be missing the dashboard HTTP API contract. Check that "
        f"INCLUDE_FILES in scripts/sanitize.py contains this path AND "
        f"that DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS do not match it."
    )


def test_dashboard_readme_explicitly_included() -> None:
    """The dashboard/README.md is NOT under DENY_DIRS today, so this
    test is informational/defensive — it proves ``is_denied()`` returns
    False even if a future operator accidentally adds ``dashboard/`` to
    DENY_DIRS without simultaneously updating INCLUDE_FILES coverage.
    """
    assert sanitize.is_denied(DASHBOARD_README_REL) is False, (
        f"sanitizer denied {DASHBOARD_README_REL!r} — public mirror "
        f"will be missing the dashboard dev/build/route documentation. "
        f"Check INCLUDE_FILES contains this path AND that nothing in "
        f"DENY_FILES / DENY_EXTENSIONS / DENY_PATTERNS matches it."
    )


def test_dashboard_owner_charter_explicitly_included() -> None:
    """The dashboard-owner charter currently STAYS DENIED.

    .claude/agents/ is in DENY_DIRS — ``test_prd8_claude_agents_dir_denied``
    locks this until CLUTCH ships publicly with explicit owner approval.
    This test asserts the current locked state: dashboard-owner.md is
    denied alongside the other domain-owner charters.

    When CLUTCH adoption goes public and owner flips ``.claude/agents/``
    out of DENY_DIRS, this test should be replaced (the file should
    then be unconditionally allowed by the absence of a deny rule, not
    by an INCLUDE_FILES surgical lift). For now: locked.
    """
    assert sanitize.is_denied(DASHBOARD_OWNER_CHARTER_REL) is True, (
        f"sanitizer FAILED to deny {DASHBOARD_OWNER_CHARTER_REL!r}. "
        f"Until CLUTCH ships publicly, .claude/agents/ stays in "
        f"DENY_DIRS — see test_prd8_claude_agents_dir_denied for the "
        f"locked-private rationale."
    )


def test_no_secrets_leak_through_dashboard_tree() -> None:
    """Scan the dashboard/ source tree for hard-coded secret-shaped
    strings. The dashboard source files DO ship publicly, so any
    accidental hard-coded token, BotFather mention, or Anthropic key
    pattern is a class-of-bug we catch at sanitizer-test time rather
    than waiting for the post-export validate_output scan.

    The scan is over the source tree on disk, not the post-export copy
    — the goal is to fail fast in CI rather than only at full-export
    time.
    """
    dashboard_root = REPO_ROOT / "dashboard"
    if not dashboard_root.exists():
        # Test runs in a checkout that pre-dates dashboard/ — skip silently.
        # Once dashboard/ lands, this branch never trips.
        return

    # Patterns whose presence in dashboard/ source is a near-miss leak.
    # Each pattern is something we have already seen attempted (real bot
    # tokens), or something that has no business being hard-coded
    # (Anthropic SDK keys, "BotFather" prose suggesting a how-to-leak).
    suspicious_patterns: list[tuple[str, "re.Pattern[str]"]] = [
        ("real telegram bot token", __import__("re").compile(
            r"\b\d{9,12}:[A-Za-z0-9_-]{30,}\b"
        )),
        ("anthropic api key", __import__("re").compile(
            r"sk-ant-[A-Za-z0-9_-]{20,}"
        )),
        ("openai api key", __import__("re").compile(
            r"sk-proj-[A-Za-z0-9_-]{20,}"
        )),
        # Hard-coded user-token literal — anything assigning a long string
        # to a name like ``bot_token`` / ``BOT_TOKEN`` is a smell.
        ("hardcoded bot_token assignment", __import__("re").compile(
            r"""(?im)\bbot_token\s*[:=]\s*["'][A-Za-z0-9_:-]{20,}["']"""
        )),
    ]

    failures: list[str] = []
    skip_dirs = {"node_modules", "dist", "__tests__"}
    skip_suffixes = {".lock", ".log"}

    for path in dashboard_root.rglob("*"):
        if not path.is_file():
            continue
        # Skip build artifacts + dep trees + test fixtures (tests may
        # legitimately use throwaway tokens for validation).
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in skip_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pat in suspicious_patterns:
            for m in pat.finditer(content):
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} — {label!r} matched: "
                    f"{m.group(0)[:80]!r}"
                )

    assert not failures, (
        "sanitizer dashboard-tree scan found near-miss leak shapes — each "
        "is a hard-coded value that should be an env-var lookup or test "
        "fixture under __tests__/:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_dashboard_server_src_files_pass_through_to_public() -> None:
    """Positive control: legitimate dashboard source code MUST pass
    ``is_denied()`` (False = allowed). This test catches the
    false-deny class-of-bug where a future restructure of DENY_DIRS
    accidentally swallows dashboard/server/src/ or dashboard/web/src/.
    """
    legitimate_paths = [
        "dashboard/server/src/index.ts",
        "dashboard/server/src/translate.ts",
        "dashboard/server/src/auth-policy.ts",
        "dashboard/server/src/framework-client.ts",
        "dashboard/server/src/middleware/auth.ts",
        "dashboard/server/src/middleware/csrf.ts",
        "dashboard/server/src/routes/agents.ts",
        "dashboard/server/src/routes/conversation.ts",
        "dashboard/server/package.json",
        "dashboard/web/src/App.tsx",
        "dashboard/web/src/main.tsx",
        "dashboard/web/src/pages/Agents.tsx",
        "dashboard/web/src/components/Sidebar.tsx",
        "dashboard/web/package.json",
        "dashboard/web/vite.config.ts",
        "dashboard/web/tsconfig.json",
    ]
    failures: list[str] = []
    for path in legitimate_paths:
        if sanitize.is_denied(path) is True:
            failures.append(path)
    assert not failures, (
        f"sanitizer falsely denied legitimate dashboard source files: "
        f"{failures!r}. Source under dashboard/server/src/ and "
        f"dashboard/web/src/ MUST ship publicly — only dist/ and "
        f"node_modules/ are denied."
    )


def test_prp7_dynamic_lock_pid_scan() -> None:
    """Dynamic regression: every currently-tracked .lock or .pid file
    must be denied. Catches future operator mistakes where a new
    runtime-state file is accidentally ``git add``'d.

    This test reads ``git ls-files`` at runtime — the test set is NOT
    hardcoded. If a new ``foo.lock`` shows up tracked, the test fails
    immediately and points at the file, the rule that should catch it,
    and what the sanitizer actually returned.
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith((".lock", ".pid"))
    ]
    failures: list[str] = []
    for path in tracked:
        if sanitize.is_denied(path) is not True:
            failures.append(path)
    assert not failures, (
        f"sanitizer FAILED to deny tracked runtime-state files: "
        f"{failures!r}. Each one is a public-mirror leak risk. Add to "
        f"DENY_FILES (layer 1) or fix DENY_EXTENSIONS / DENY_PATTERNS."
    )


# === PRD-8 Phase 7a (WS1) — SECRET_PREFIXES regression tests ===
#
# R1 B1 + M2 fix — uses the canonical `contains_leak_pattern` helper from
# security.patterns (NOT a private `_contains_leak_pattern`). One test per
# SECRET_PREFIXES entry verifies LEAK_PATTERN_REGEX catches the synthetic
# key. Synthetic — NEVER a real key (24-char `x` tail).
#
# R1 M3 negative tests — UUIDs, git SHAs, short labels, JSON field names
# must NOT match LEAK_PATTERN_REGEX (defense against false-positive
# redaction in vault notes / commit messages / config).


def test_phase7a_security_patterns_module_imports() -> None:
    from security.patterns import (
        LEAK_PATTERN_REGEX,
        PREFIX_VENDOR_MAP,
        SECRET_PREFIXES,
        contains_leak_pattern,
    )
    assert isinstance(SECRET_PREFIXES, tuple)
    assert len(SECRET_PREFIXES) >= 27
    assert callable(contains_leak_pattern)


def test_phase7a_sk_proj_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk-proj-" + "x" * 24)


def test_phase7a_sk_ant_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk-ant-" + "x" * 24)


def test_phase7a_sk_lf_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk-lf-" + "x" * 24)


def test_phase7a_pk_lf_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("pk-lf-" + "x" * 24)


def test_phase7a_sk_legacy_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk-" + "x" * 24)


def test_phase7a_sk_live_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk_live_" + "x" * 24)


def test_phase7a_sk_test_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk_test_" + "x" * 24)


def test_phase7a_rk_live_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("rk_live_" + "x" * 24)


def test_phase7a_pk_live_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("pk_live_" + "x" * 24)


def test_phase7a_sk_elevenlabs_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("sk_" + "x" * 24)


def test_phase7a_gsk_groq_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("gsk_" + "x" * 24)


def test_phase7a_gr_gradium_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("gr_" + "x" * 24)


def test_phase7a_xoxb_slack_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("xoxb-" + "x" * 24)


def test_phase7a_xoxp_slack_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("xoxp-" + "x" * 24)


def test_phase7a_xapp_slack_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("xapp-" + "x" * 24)


def test_phase7a_ghp_github_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("ghp_" + "x" * 24)


def test_phase7a_gho_github_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("gho_" + "x" * 24)


def test_phase7a_ghu_github_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("ghu_" + "x" * 24)


def test_phase7a_ghs_github_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("ghs_" + "x" * 24)


def test_phase7a_ghr_github_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("ghr_" + "x" * 24)


def test_phase7a_akia_aws_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("AKIA" + "X" * 24)


def test_phase7a_arn_aws_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("arn:aws:" + "x" * 24)


def test_phase7a_aiza_google_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("AIza" + "x" * 24)


def test_phase7a_ya29_google_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("ya29." + "x" * 24)


def test_phase7a_eyj_jwt_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("eyJ" + "x" * 24)


def test_phase7a_npm_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("npm_" + "x" * 24)


def test_phase7a_dckr_docker_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("dckr_" + "x" * 24)


def test_phase7a_glpat_gitlab_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("glpat-" + "x" * 24)


def test_phase7a_sg_sendgrid_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("SG." + "x" * 24)


def test_phase7a_key_mailgun_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("key-" + "x" * 24)


def test_phase7a_hrku_heroku_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("HRKU-" + "x" * 24)


def test_phase7a_pcp_postmark_caught() -> None:
    from security.patterns import contains_leak_pattern
    assert contains_leak_pattern("pcp_" + "x" * 24)


# === Replacement-ordering regressions (R1 B3 — most-specific wins) ===


def test_phase7a_replacement_sk_ant_labels_anthropic_not_openai() -> None:
    """sk-ant-xxxx scrubs to <REDACTED-anthropic>, NOT <REDACTED-openai>."""
    out = sanitize.scrub_content("token=sk-ant-" + "x" * 30, "x.md")
    assert "<REDACTED-anthropic>" in out
    assert "<REDACTED-openai>" not in out


def test_phase7a_replacement_sk_proj_labels_openai_not_generic() -> None:
    out = sanitize.scrub_content("token=sk-proj-" + "x" * 30, "x.md")
    assert "<REDACTED-openai>" in out


def test_phase7a_replacement_sk_live_labels_stripe_not_elevenlabs() -> None:
    """sk_live_xxxx labeled stripe (sk_live_ prefix wins over sk_ via length-desc)."""
    out = sanitize.scrub_content("k=sk_live_" + "x" * 30, "x.md")
    assert "<REDACTED-stripe>" in out
    assert "<REDACTED-elevenlabs>" not in out


def test_phase7a_replacement_gsk_labels_groq() -> None:
    out = sanitize.scrub_content("k=gsk_" + "x" * 30, "x.md")
    assert "<REDACTED-groq>" in out


def test_phase7a_replacement_gr_labels_gradium() -> None:
    out = sanitize.scrub_content("k=gr_" + "x" * 30, "x.md")
    assert "<REDACTED-gradium>" in out


def test_phase7a_replacement_ghp_labels_github() -> None:
    out = sanitize.scrub_content("k=ghp_" + "x" * 30, "x.md")
    assert "<REDACTED-github>" in out


def test_phase7a_replacement_akia_labels_aws() -> None:
    out = sanitize.scrub_content("k=AKIA" + "X" * 30, "x.md")
    assert "<REDACTED-aws>" in out


def test_phase7a_replacement_aiza_labels_google() -> None:
    out = sanitize.scrub_content("k=AIza" + "x" * 30, "x.md")
    assert "<REDACTED-google>" in out


def test_phase7a_replacement_eyj_labels_jwt() -> None:
    out = sanitize.scrub_content("token=eyJ" + "x" * 30, "x.md")
    assert "<REDACTED-jwt>" in out


def test_phase7a_replacement_does_not_scrub_identifier_with_sk_prefix() -> None:
    sample = "def test_task_name_and_prompt_always_present() -> None:\n    pass\n"
    out = sanitize.scrub_content(sample, "test_prompt_builder.py")
    assert "test_task_name_and_prompt_always_present" in out
    assert "<REDACTED-elevenlabs>" not in out


def test_phase7a_leak_patterns_ignore_identifier_with_sk_prefix() -> None:
    from security.patterns import contains_leak_pattern

    assert contains_leak_pattern("test_task_name_and_prompt_always_present") is False


# === DENY layer regressions ===


def test_phase7a_bak_in_deny_extensions() -> None:
    assert ".bak" in sanitize.DENY_EXTENSIONS
    assert ".backup" in sanitize.DENY_EXTENSIONS


def test_phase7a_bak_file_is_denied() -> None:
    assert sanitize.is_denied(".claude/data/dashboard.db.pre-v2.bak")


def test_phase7a_dashboard_db_in_deny_files() -> None:
    """R1 B7 fix — dashboard.db in DENY_FILES (audit_log lives inside)."""
    assert ".claude/data/dashboard.db" in sanitize.DENY_FILES


# === R1 M3 negative tests ===


def test_phase7a_uuid_not_redacted() -> None:
    """8-4-4-4-12 hex UUID does NOT match LEAK_PATTERN_REGEX."""
    from security.patterns import contains_leak_pattern
    sample = "550e8400-e29b-41d4-a716-446655440000"
    assert not contains_leak_pattern(sample)


def test_phase7a_git_sha_not_redacted() -> None:
    """40-char hex SHA does NOT match."""
    from security.patterns import contains_leak_pattern
    sample = "a" * 40
    assert not contains_leak_pattern(sample)


def test_phase7a_short_key_label_not_redacted() -> None:
    """Bare 'key-x' (under 16 tail chars) does NOT match."""
    from security.patterns import contains_leak_pattern
    assert not contains_leak_pattern("key-x")
    assert not contains_leak_pattern("sk_x")


def test_phase7a_field_name_key_not_redacted() -> None:
    """JSON field name 'key-name' does NOT match (16+ char tail required)."""
    from security.patterns import contains_leak_pattern
    sample = '{"key-name": "value"}'
    assert not contains_leak_pattern(sample)


# === PRD-8 Phase 6 v2 fix-pass 2026-05-10 — B-LEAK regression tests ===
#
# B-LEAK-2 incident (2026-05-10): the legacy `\bowner\b` REPLACEMENTS
# pattern did NOT fire across `_` because `_` is `\w`, so identifier
# fixtures like `v_owner_unused` and `_owner_VOICE` slipped through both
# the REPLACEMENTS pass AND the LEAK_PATTERNS validator. Verifier returned
# "zero leaks" while the literal shipped publicly.
#
# B-LEAK-1 incident (same review): a real Nestor ElevenLabs voice clone id
# (`VOICE_ID_EXAMPLE`) was hard-coded into the public docs page and
# the test fixtures. The sanitizer had no prefix-shape coverage for raw
# 20-char ElevenLabs voice ids.
#
# Both classes are now defended at REPLACEMENTS + LEAK_PATTERNS layers.
# Rule: feedback_sanitizer_regex_shape_blind_spot.md.


def test_sanitizer_owner_substring_through_underscore() -> None:
    """B-LEAK-2 — bare-substring `owner` REPLACEMENTS scrubs identifier
    fixtures where `_` blocks word-boundary matching.

    Class-of-bug: ``re.compile(r"\\bowner\\b", re.IGNORECASE)`` does NOT
    match `owner` inside `v_owner_unused` or `_owner_VOICE` because `_`
    is `\\w`. The fix relaxes REPLACEMENTS to bare substring; this test
    locks the fix.
    """
    sample = (
        "voice_overrides={\"elevenlabs\": \"v_owner_unused\"}\n"
        "OVERRIDE_KEY = \"_owner_VOICE\"\n"
        "if user == \"owner\":  # explicit lower-case still hits\n"
    )
    out = sanitize.scrub_content(sample, "test_voice_overrides.py")
    assert "owner" not in out.lower(), (
        f"REPLACEMENTS failed to scrub `owner` substring across `_` boundaries. "
        f"Output still contains owner:\n{out!r}"
    )


def test_sanitizer_owner_substring_in_leak_patterns() -> None:
    """B-LEAK-2 — LEAK_PATTERNS double-pass also catches bare-substring
    `owner` so a future regression where a new file slips past
    REPLACEMENTS still fails the post-export validator."""
    pat_strs = [p.pattern for p in sanitize.LEAK_PATTERNS]
    assert any(p == "owner" for p in pat_strs), (
        f"LEAK_PATTERNS missing bare-substring `owner` validator. "
        f"Found: {pat_strs!r}"
    )


def test_sanitizer_lastname_substring_through_email_compound() -> None:
    """B-LEAK-3 — bare-substring `lastname` REPLACEMENTS scrubs the surname
    when embedded inside an email local-part compound that survived the
    `owner` scrub.

    Class-of-bug: prior LEAK_PATTERNS only checked the two-word phrases
    ``lastname owner`` / ``owner lastname``. After the B-LEAK-2 `owner` fix,
    `owner6392lastname@gmail.com` scrubs to `owner6392lastname@gmail.com` —
    the surname survived because no rule fired on the bare token. This
    test locks the bare-substring fix.
    """
    sample = (
        '# Personal Gmail (owner6392lastname@gmail.com — read-only)\n'
        'PERSONAL_GMAIL_ACCOUNT = "owner6392lastname@gmail.com"\n'
    )
    out = sanitize.scrub_content(sample, "config.py")
    assert "lastname" not in out.lower(), (
        f"REPLACEMENTS failed to scrub bare-substring `lastname` from email "
        f"compound. Output still contains lastname:\n{out!r}"
    )


def test_sanitizer_lastname_substring_in_leak_patterns() -> None:
    """B-LEAK-3 — LEAK_PATTERNS double-pass catches bare-substring
    `lastname` so a future regression fails validate_output instead of
    shipping silently."""
    pat_strs = [p.pattern for p in sanitize.LEAK_PATTERNS]
    assert any(p == "lastname" for p in pat_strs), (
        f"LEAK_PATTERNS missing bare-substring `lastname` validator. "
        f"Found: {pat_strs!r}"
    )


def test_sanitizer_nestor_voice_id_replacements() -> None:
    """B-LEAK-1 — Nestor ElevenLabs voice clone id literal scrubs to
    placeholder via REPLACEMENTS. Defense-in-depth on top of the
    source-level placeholder."""
    sample = 'voice_id: "VOICE_ID_EXAMPLE"\n'
    out = sanitize.scrub_content(sample, "docs/cabinet-voice-setup.md")
    assert "VOICE_ID_EXAMPLE" not in out, (
        f"REPLACEMENTS failed to scrub the Nestor voice id literal. "
        f"Output:\n{out!r}"
    )


def test_sanitizer_nestor_voice_id_in_leak_patterns() -> None:
    """B-LEAK-1 — LEAK_PATTERNS double-pass catches a future regression
    where the Nestor voice id literal slips back into source."""
    matched = False
    for p in sanitize.LEAK_PATTERNS:
        if "VOICE_ID_EXAMPLE" in p.pattern:
            matched = True
            break
    assert matched, (
        f"LEAK_PATTERNS missing Nestor voice id validator. "
        f"Patterns: {[p.pattern for p in sanitize.LEAK_PATTERNS]!r}"
    )


def test_sanitizer_nestor_voice_id_case_insensitive_replacements() -> None:
    """B-LEAK-1 — REPLACEMENTS scrubs lowercase typo variant
    `VOICE_ID_EXAMPLE` (legacy test_persona_config_loader.py fixture).
    Same-class leak — first letter typo doesn't change the identifier
    semantics."""
    sample = 'voice_id: "VOICE_ID_EXAMPLE"\n'
    out = sanitize.scrub_content(sample, "test_persona_config_loader.py")
    assert "l0R3QvM8Xa45lGiK8sL" not in out, (
        f"REPLACEMENTS failed to scrub lowercase typo of Nestor voice id. "
        f"Output:\n{out!r}"
    )

