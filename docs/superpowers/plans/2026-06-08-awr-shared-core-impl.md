# AWR Shared-Core Implementation Plan

Date: 2026-06-08. Branch: `awr-shared-core`. Status: ready to build.

## Goal

Land every shared dependency for features A (assimilate), B (interactive installer), and C (cross-agent runtime) on one branch, one PR. After this lands, A/B/C can be built in any order with zero merge collisions.

## Locked decisions (from investigation, no further debate)

1. **Mailbox routing → `<profile>/config.yaml` top-level `mailbox:` block.** NOT env, NOT `local/*.env`. Env is tokens-only.
2. **Lane CLI strategy: patch upstream.** Add `claim-lane`/`release-lane`/`list-lanes` to `coordination/src/mailbox/cli.py`. `_abspath` skipped on `lane://`-prefixed args.
3. **Installer command (for later feature B):** `hermes profile install <SRC> --name <N> --alias --force -y`. Capture stdout+stderr; treat any nonzero exit as failure.
4. **Default `warroom.label` → handle**, not agent_name.
5. **`skills/twelvelabs/**` (or any org-namespaced skill) hard-excluded** from anywhere this repo ships.
6. **Template SOUL.md human-edited directly**; no external vault-sync.
7. **Discord walkthrough = single Python module** (`WALKTHROUGH_STEPS: list[Step]` + `run_discord_walkthrough(prompts, context)`). NOT a templated text file.
8. **MCP servers** are registered as a `mcp_servers:` block inside `config.yaml` (not a separate `mcp.json`). Template docs must reflect this.

## Sanitization rule (applies to every file we create)

- No employer names, no colleague names, no internal hostnames, no specific channel IDs, no project codenames, no Bitwarden references with concrete IDs.
- All persona content ships as `<<FILL-IN: ...>>` markers.
- All channel references ship as `<CHANNEL_ID>` placeholders.
- All MCP servers ship as `<<NAME>>`/`<<URL>>` placeholders or are absent.
- Personalities (if shipped) trimmed to generic flavors: helpful, concise, technical, teacher, noir.

## Phases (commit per task, in order)

### Phase 1 — Mailbox lane CLI (upstream patch)

**T1.** Add `claim-lane`, `release-lane`, `list-lanes` subcommands to `coordination/src/mailbox/cli.py`. Skip `_abspath` on `lane://`-prefixed paths. Tests in `coordination/tests/test_cli_lanes.py`: subcommand parses, `lane://x` is preserved verbatim, idempotent re-claim, list-lanes shows held lanes.

### Phase 2 — Shared utility modules (template/warroom_setup/)

**T2.** Extract `patch_persona_decisions(profile_root, rule_text, *, sentinel_id="warroom") -> bool` from inline persona-writing code in `setup.py::run_setup`. Sentinel-bounded append (`<!-- _WR_PERSONA_BEGIN -->` ... `<!-- _WR_PERSONA_END -->`), idempotent. Tests cover: first write, no-op re-write, owner edits between sentinels survive.

**T3.** Parameterize `write_env(profile_root, values, *, filename=".env")` — add `filename=` kwarg. All existing callsites stay default `.env`. Tests cover the new path with `filename="local/sentinel.env"`.

**T4.** Add `prompt_secret(label, current=None)` to `prompts.py` — masked input via `getpass.getpass`. Tests with monkeypatched `getpass.getpass`.

**T5.** Create `validators.py` with: `valid_slug(s) -> bool` (already in setup.py — extract + share), `valid_channel_id(s) -> bool` (17-20 digit snowflake), `valid_bot_token(s) -> bool` (regex shape), `valid_board_name(s) -> bool`, `valid_handle(s) -> bool`. Tests per-validator.

**T6.** Create `schema.py` — canonical key sets and defaults:
  - `WAR_ROOM_KEYS = ("enabled", "board", "label", "role", "min_confidence", "gate_action", "enforce", "show_confidence_badge")`
  - `MAILBOX_KEYS = ("board", "label", "mailbox_home", "socket_path")`
  - `DEFAULTS = {...}` with safe values
  - `clamp_pct(v) -> int` (moved from setup.py)
  - `BLOCKED_VALUES_REGEX` — regex for sanitization CI check
  Tests cover schema completeness, clamp behavior, regex hit/miss.

**T7.** Extend `patch_war_room_block` signature to read from `schema.DEFAULTS` and accept any kwargs from `WAR_ROOM_KEYS`. Strict backward-compatibility (existing callers unchanged). Tests: existing T17/T8 idempotency holds; new keys can be added without breaking old.

### Phase 3 — Walkthroughs

**T8.** Create `discord_walkthrough.py`:
  - `@dataclass Step(n, title, body_lines, prompt_label, validator, optional)`
  - `WALKTHROUGH_STEPS: list[Step]` — 7 steps (create app → bot token → MESSAGE CONTENT intent → install URL with permission integer 277025770560 → channel ID → optional second channel → finish)
  - `run_discord_walkthrough(prompts, *, context: str) -> DiscordCreds`
  - `_validate_token` / `_validate_channel_id` (re-export from validators)
  Tests assert step count, required strings in each step, validator wiring.

**T9.** Create `slack_walkthrough.py`:
  - Same `Step` shape (import from `discord_walkthrough` to keep one dataclass)
  - `SLACK_WALKTHROUGH_STEPS: list[Step]` — Socket Mode flow
  - `run_slack_walkthrough(prompts, *, context: str) -> SlackCreds`
  Tests parallel to T8.

### Phase 4 — Template content additions (sanitization-driven)

**T10.** `template/SOUL.md` — H1 + 6-8 H2 sections (Voice / How you talk / How you work / What you value / Communication / Writing rules / Boundaries), all `<<FILL-IN>>` markers, no real content. (Today SOUL.md is generated by persona_sync; this T10 keeps that flow but adds a starter `local/persona/voice.md` placeholder.)

**T11.** `template/memories/USER.md` + `template/memories/MEMORY.md` — empty files; each has 3-line header documenting the `§`-separator memory convention (a single source of truth in the template README).

**T12.** `template/channel_directory.json` — `{"updated_at": null, "platforms": {}}`.

**T13.** `template/slack-manifest.json` — generic manifest with `<<APP_NAME>>`, `<<BOT_HANDLE>>` placeholders and ONE example slash command.

**T14.** `template/cron/jobs.json` — `{"jobs": []}`. README in `template/cron/` documents the schema.

**T15.** `template/skills/.bundled_manifest` — JSON with 3 generic bundled skills (writing-plans / test-driven-development / dogfood). `template/skills/.hub/taps.json` → `{"taps": []}` + comment pointing to the official hub URL placeholder.

**T16.** `template/.env.example` — verify full key list matches `.env.template`; add stub `MAILBOX_BOARD_OVERRIDE=` for power users (commented out by default).

**T17.** `template/hooks/README.md` — documents the on_session_start / pre_tool_use / post_tool_use contracts and where they hook in. `template/scripts/README.md` — documents `setup.sh`, `publish.sh`, future `install.sh` (feature B), `assimilate.sh` (feature A).

**T18.** Add `personalities:` block to `template/config.yaml` — 5 generic flavors: helpful, concise, technical, teacher, noir. Each flavor has a 1-line description and a `system_prompt_suffix` example.

**T19.** Add `platform_toolsets:` block to `template/config.yaml` — discord / slack / cli with the exact key shape aahil-sh uses. Mark as managed inside an additional sentinel block (`# >>> warroom-toolsets >>>` ... `# <<< warroom-toolsets <<<`) so future templating can rewrite cleanly.

**T20.** Add safe-default top-level keys to `template/config.yaml`:
  - `approvals: { mode: manual }`
  - `cron_mode: deny`
  - `security: { tirith_enabled: true }`
  - `redact_secrets: true`
  Each with a one-line comment above explaining the default.

### Phase 5 — Sanitization guard + docs

**T21.** Create `template/SANITIZATION.md` — the regex blocklist + key list from the investigation's §4. Top-level: "How we keep TwelveLabs (and any other employer) out of this public template." Includes:
  - List of patterns CI should fail on (employer names, internal hostnames, specific channel IDs, colleague-name patterns).
  - The list of skills folders hard-excluded.
  - Instructions for contributors who copy from a personal profile.

**T22.** Update `template/README.md`:
  - Documents the `mailbox:` config block as the canonical routing config.
  - Documents `mcp_servers:` belongs in `config.yaml` (not a separate file).
  - Adds a "Known limitations" link to the cross-agent feature (still pending — feature C).
  - Adds a "Sanitization" section pointing to SANITIZATION.md.

### Phase 6 — Migration sanity

**T23.** Update `template/warroom_setup/setup.py::run_setup` to use:
  - `validators.valid_slug` (replace inline regex)
  - `validators.valid_handle` (replace inline)
  - `schema.WAR_ROOM_KEYS` / `schema.DEFAULTS` (replace literals)
  - `patch_persona_decisions` (replace inline persona append)
  - `write_env(..., filename=".env")` (no behavior change, just explicit kwarg)
  Tests: full template suite must pass green (52 → still 52+, all green).

**T24.** Full regression. `pytest -v` template/ + coordination/. All green. README updated to bump "as of YYYY-MM-DD" date.

## Verification

After all 24 tasks land:
- `template/.venv/bin/python -m pytest template -v` → all template tests green (52 baseline + ~30 added).
- `coordination/.venv/bin/python -m pytest coordination -v` (if venv exists) → mailbox tests green + new lane-CLI tests passing.
- Manual: `grep -rIn "twelvelabs\|TwelveLabs\|tl-" template/` → ZERO hits.
- Manual: `grep -rIn "twelvelabs\|TwelveLabs" template/` → ZERO hits.
- Sanitization CI check: `python3 template/scripts/sanitize_check.py template/` exits 0 (this script's spec goes into SANITIZATION.md and is shippable as T21).

## Out of scope (will land in later PRs)

- Feature A (assimilate) — needs all the above
- Feature B (interactive installer) — needs all the above
- Feature C (cross-agent runtime + mailbox enroll) — depends on lane CLI patch from this PR
- Bitwarden security warning ban — doc-only, add in README later
- gateway_state.json semantics — runtime artifact, not template concern
