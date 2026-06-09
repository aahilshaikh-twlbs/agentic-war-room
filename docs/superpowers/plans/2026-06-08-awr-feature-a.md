# Feature A — Assimilate an Existing Hermes Profile into the War Room

Date: 2026-06-08. Status: planning. Builds on shared-core (PR #2), Feature C runtime (PR #3), Feature B installer (PR #5).

---

## 1. Goal

Add war-room capability to a Hermes profile that was NOT built from this template, on owner trigger inside that profile's running Claude Code session, without clobbering its existing Discord/Slack/model wiring, persona, hooks, plugins, or skill bundles.

## 2. Scope

**In:**
- Skill `template/skills/assimilate-warroom/SKILL.md` — owner-trigger protocol the agent loads.
- CLI subcommand `warroom assimilate <profile_root>` (in existing `warroom_setup/cli.py`).
- Orchestrator `template/warroom_setup/assimilate.py` — detect → walkthrough (conditional) → patches → call `enroll.bootstrap`.
- Idempotent re-run safety (`--reconfigure` for forced rewrite, default = no-op on repeat).
- Preserve-don't-clobber semantics for existing `hooks:`, `plugins:`, model provider, persona body, channel credentials, skill bundles.
- Skill-bundle append-only merge (add `confidence-gate` reference without removing existing entries) — kept inside the sentinel block to avoid mutating operator lists.

**Out:**
- Fresh-install flow (Feature B owns it).
- Non-Hermes profiles, non-yaml configs.
- Migrating model providers, rewriting hooks, deleting plugins.
- Auto-creating Discord apps / Slack apps (manual walkthrough only).
- Mailbox daemon install (we fail-warn if absent, same as Feature C).
- Multi-board federation (one board per assimilate run).

## 3. Reuse map — function-by-function

| Capability | Reuse from | Notes |
|---|---|---|
| Detect existing profile shape | `template/scripts/installer/profile_detect.py::inspect_profile` | Same dataclass shape; assimilate consumes `ProfileInspection`. We do NOT re-implement existence/Hermes-managed/user-data checks. |
| Discord credentials | `discord_walkthrough.run_discord_walkthrough` | Reuse verbatim. Assimilate-context = "wire an existing Hermes profile into the war room" string in the welcome banner. |
| Slack credentials | `slack_walkthrough.run_slack_walkthrough` | Same shape. Skipped if Slack credentials already in target's `.env`. |
| Write `mailbox:` config block | `setup.patch_mailbox_block` | Schema-driven, sentinel-managed; we do not touch it. |
| Write `war_room:` config block | `setup.patch_war_room_block` | Idempotent + schema-checked; assimilate calls with `enabled=True, board=..., label=..., enforce=False` (gentler default on existing profiles). |
| Write MAILBOX_BOARD/LABEL to `.env` | `enroll.bootstrap` (via its `write_runtime_env` call) | Assimilate ends with `enroll.bootstrap(...)` — same as fresh install. |
| Persona rule | `setup.patch_persona_decisions(..., sentinel_id="warroom-runtime")` | Reuse `_WARROOM_PERSONA_RULE` constant from setup.py (or re-import the text). Idempotent. |
| Atomic file writes | `setup._atomic_write_text`, `setup.write_env` | Never re-implement. |
| Slug + handle validation | `validators.valid_slug`, `validators.valid_handle` | For board name + label normalization. |
| Runtime state | `runtime_state.save_state` | For `local/warroom-assimilate.json` audit trail. |
| Hooks command patch | `setup.patch_hooks_command` | If target has the war-room first_run hook (unlikely on a foreign profile, but cheap to call — no-op when the line is absent). |

**Strictly new code** (in `assimilate.py`):
- `assimilate(profile_root, *, board, label, dry_run, reconfigure, no_walkthrough, env)` — orchestrator.
- `_classify(profile_root)` — wraps `inspect_profile` but treats foreign-Hermes (no `warroom_setup/`) as a VALID assimilate target (the installer's `inspect_profile` calls this `ABORT`; assimilate flips it to `PROCEED-as-foreign`).
- `_detect_channels(profile_root)` — read `<profile>/.env` (if present), look for `DISCORD_BOT_TOKEN` / `SLACK_BOT_TOKEN`; return `{"discord": bool, "slack": bool}` to skip walkthrough steps.
- `_already_assimilated(profile_root)` — check for `local/warroom-enroll.json` AND a `# >>> warroom-managed` block in `config.yaml`; True ⇒ refuse without `--reconfigure`.
- `_report(report_dict, out_stream)` — pre-flight + post-flight printer.

That's it. ~150-200 LoC of new orchestration; the rest is composition.

## 4. New file inventory

| Path | Purpose |
|---|---|
| `template/skills/assimilate-warroom/SKILL.md` | Agent-loaded protocol triggered by owner saying "join the war room" / "assimilate". |
| `template/warroom_setup/assimilate.py` | Orchestrator (~200 LoC, stdlib only). |
| `template/warroom_setup/cli.py` | MODIFY — add `assimilate` subparser. |
| `template/tests/test_assimilate.py` | Unit tests with fixtures. |
| `template/tests/fixtures/foreign_profile/config.yaml` | Hermes profile w/o `warroom_setup/` — own hooks, own plugins, own model. |
| `template/tests/fixtures/foreign_profile_with_discord/.env` | Same + pre-populated `DISCORD_BOT_TOKEN` to exercise walkthrough-skip. |
| `template/tests/fixtures/already_assimilated/config.yaml` | Profile with existing `# >>> warroom-managed` block to exercise reconfigure path. |

No new module beyond `assimilate.py`. No new walkthrough module. No new validators.

## 5. SKILL.md sketch

```markdown
---
name: assimilate-warroom
description: Wire this Hermes profile into a cross-agent war-room board. Trigger
  when the owner says "join the war room", "assimilate", "wire me into the war
  room", or asks to coordinate with another agent on a shared board.
---

# Skill: Assimilate Into the War Room

The owner of this profile wants to add war-room coordination capability. You will:

## 1. Confirm scope
Ask the owner two questions (one message, both at once):
- Board name (default: `default` — same board their peer is on).
- Label for this agent on the board (default: this profile's handle, fetched from
  `local/agent.json` if present, else the profile directory name).

## 2. Run the CLI
```
python -m warroom_setup assimilate "$CLAUDE_PROJECT_DIR" \
  --board <board> --label <label>
```
The CLI will:
- Detect this profile's shape (existing channels, hooks, plugins).
- Walk through Discord bot setup ONLY if no DISCORD_BOT_TOKEN is already wired.
- Walk through Slack bot setup ONLY if no SLACK_BOT_TOKEN is already wired.
- Print a pre-flight diff of files it will create/modify.
- Apply patches atomically (sentinel-managed, never clobbers).
- Append a persona rule teaching you to use `mailbox claim-lane` before edits.
- Run `enroll.bootstrap` so the next session joins the board.

## 3. Re-run safety
If the owner re-asks, run with `--reconfigure` to force re-write (otherwise the
CLI no-ops with "already assimilated"). Use `--dry-run` to preview.

## 4. After it runs
Restart this Claude Code session so the new MAILBOX_BOARD/MAILBOX_LABEL env vars
take effect (Hermes loads `<profile>/.env` into the session). Then `mailbox ps`
should show your peer.

## Failure modes
- "mailbox CLI not found" — the mailbox daemon is not installed. The war_room
  config block is still written; install mailbox from the runtime README and
  re-run `warroom enroll`.
- "already assimilated" — pass `--reconfigure` to force rewrite.
- Walkthrough fails validation — the owner can re-run; nothing is written until
  the pre-flight confirm.
```

## 6. CLI surface

```
warroom assimilate <profile_root>
  --board <name>           default: "default"
  --label <name>           default: handle from local/agent.json, else basename(profile_root)
  --dry-run                resolve + report; write nothing
  --no-walkthrough         skip Discord/Slack walkthroughs even if creds missing
  --reconfigure            force rewrite if already assimilated
  --yes                    headless: no prompts (requires --no-walkthrough OR pre-set env)
```

Exit codes (mirror enroll's contract):
- 0 — assimilated (or dry-run reported cleanly).
- 1 — mailbox CLI not found (config written; runtime inactive).
- 2 — already assimilated, `--reconfigure` not passed.
- 3 — profile path invalid / not a Hermes profile.
- 4 — walkthrough validation failed or owner aborted.

## 7. Detection flow

`_classify(profile_root)` returns a `dict` (not a dataclass — keep the surface tiny):

```
{
  "exists": True,
  "is_hermes": True,             # has config.yaml
  "is_awr_template": False,      # warroom_setup/ package present?
  "already_assimilated": False,  # has _WR_BEGIN block AND local/warroom-enroll.json
  "channels": {"discord": True, "slack": False},  # creds in .env
  "has_persona_decisions": True, # local/persona/decisions.md exists
}
```

Branching:
- `not exists` or `not is_hermes` → exit 3 with message naming the missing file.
- `already_assimilated and not reconfigure` → exit 2.
- `channels.discord` → skip Discord walkthrough (preserve operator's existing creds).
- `channels.slack` → skip Slack walkthrough.
- `no_walkthrough` → skip both unconditionally; refuse if no creds present at all (warn that war-room messaging will be CLI-only).
- `is_awr_template and already_assimilated` → exit 0 "this is already a war-room template profile; use `warroom enroll --reconfigure` instead" (don't double-patch the war_room block).

## 8. Orchestration flow — `assimilate(profile_root, *, board, label, dry_run, reconfigure, no_walkthrough, env)`

1. **Classify.** `info = _classify(profile_root)`. Exit-3 / exit-2 short-circuits per §7.
2. **Resolve identity.** Read `<profile>/local/agent.json` if present; derive `label` default from `handle`, else profile basename. Slug-validate; refuse with exit 4 if invalid.
3. **Pre-flight report.** Print to stdout:
   ```
   Assimilating <profile_root>:
     hermes-managed:  yes
     awr-template:    no
     discord creds:   present (skipping walkthrough)
     slack creds:     absent (will walk through)
     persona file:    present (will append sentinel-bounded rule)
     war_room block:  absent (will create)
     mailbox block:   absent (will create)
   Proceed? [y/N]
   ```
4. **Walkthroughs (conditional).**
   - If `not info["channels"]["discord"]` and `not no_walkthrough`: `creds = discord_walkthrough.run_discord_walkthrough(prompts, context="assimilate")`. Stash `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` for the `.env` write at step 7.
   - Same for Slack.
5. **Patches (atomic, in order):**
   a. `setup.patch_war_room_block(profile_root, board, label=label, enforce=False)` — `enforce=False` because we don't want to gate an existing operator's outputs on first contact.
   b. `setup.patch_persona_decisions(profile_root, setup._WARROOM_PERSONA_RULE, sentinel_id="warroom-runtime")` — creates `local/persona/decisions.md` if absent.
   c. `enroll.bootstrap(profile_root, board, label, dry_run=dry_run, env=env)` — writes `mailbox:` block, writes MAILBOX_BOARD/LABEL to `.env`, persists `local/warroom-enroll.json`. Captures the `EnrollState`.
   d. If walkthrough creds collected at step 4: `setup.write_env(profile_root, walkthrough_creds, filename=".env")` — merge-not-replace, so existing keys survive.
   e. `runtime_state.save_state(profile_root / "local" / "warroom-assimilate.json", {...})` — audit trail (timestamp, board, label, channels_walked_through).
6. **Post-flight summary.** Print state + `next-steps`:
   ```
   Assimilated. Next:
     - Restart this Claude session so MAILBOX_BOARD/LABEL load into env.
     - Run `mailbox ps` to see your peer.
     - Re-run with --reconfigure to change the board or label.
   ```
7. **Return exit code** per §6.

Notes:
- `--dry-run` short-circuits BEFORE step 5; only steps 1-3 run, report says `[would create]` / `[would modify]` instead of applying.
- `--yes` flag suppresses the proceed-confirm but still runs walkthroughs unless `--no-walkthrough` is also given (walkthroughs are interactive; `--yes` + missing creds + no `--no-walkthrough` is a usage error, exit 4).

## 9. Inline Discord walkthrough — exact reuse

```python
from . import discord_walkthrough

def _maybe_discord(info, no_walkthrough, prompts):
    if no_walkthrough or info["channels"]["discord"]:
        return None
    creds = discord_walkthrough.run_discord_walkthrough(prompts)
    return {"DISCORD_BOT_TOKEN": creds.bot_token, "DISCORD_CHANNEL_ID": creds.channel_id}
```

No new module. No new step content. The walkthrough's existing welcome line is generic enough; if Feature B's `context` kwarg landed, pass `context="assimilate"`, otherwise omit it (assimilate doesn't need a different closing message — the post-flight summary in step 6 does that job).

If the target profile uses a different Discord intent (e.g. `MESSAGE CONTENT` already disabled because the operator scoped down), the walkthrough's `_validate_token` only checks shape, not intents; the operator's bot will work for war-room broadcasts as long as MESSAGE CONTENT is enabled (the walkthrough surfaces this as step 3 — they can confirm + skip if already correct).

## 10. Atomic commit ordering — T-numbered tasks

| T | Title | Files | Acceptance |
|---|---|---|---|
| T1 | Add `_classify` + `_detect_channels` + `_already_assimilated` helpers (NO patching yet) | `template/warroom_setup/assimilate.py` (new, helpers only) + `template/tests/test_assimilate.py` (classify tests with all 3 fixtures) | All classify tests green; module importable; no behavior reachable from CLI. |
| T2 | Add CLI subparser + dispatch (no-op handler that prints the classify report) | `template/warroom_setup/cli.py` | `warroom assimilate <path> --dry-run` returns 0 and prints the report; `--help` shows new args. |
| T3 | Wire orchestrator steps 1-3 + 5a + 5b (war_room block + persona) | `assimilate.py` (add `assimilate()` function) + tests for patch idempotency + reconfigure refusal | Two-run idempotency test passes; `--reconfigure` rewrites; non-Hermes path returns exit 3. |
| T4 | Wire walkthrough integration (step 4) + `.env` merge (step 5d) | `assimilate.py` extends, no new imports beyond `discord_walkthrough` / `slack_walkthrough` | Skip-on-existing-creds test passes; `--no-walkthrough` test passes; scripted-stdin walkthrough integration test passes. |
| T5 | Wire `enroll.bootstrap` call (step 5c) + audit-trail write (5e) | `assimilate.py` extends | Post-state has `local/warroom-enroll.json` AND `local/warroom-assimilate.json`; `.env` has `MAILBOX_BOARD`. |
| T6 | Add `template/skills/assimilate-warroom/SKILL.md` | new file | Skill loads via Claude's skill loader (manual smoke, not unit-testable here); SKILL.md byte-level snapshot test. |
| T7 | Add exit-code matrix tests + sanitization grep | extend `test_assimilate.py` + run shared-core sanitization check | All exit codes covered; sanitize_check passes on the whole diff. |
| T8 | Manual smoke against a synthesized aahil-sh-shaped fixture (not the real one) | new `template/tests/fixtures/aahil_like/...` + `test_assimilate.py::test_assimilate_aahil_like_smoke` | Smoke test runs end-to-end against the fixture in tmp; original fixture bytes unchanged for any non-warroom file. |

Estimated: T1-T2 = 1 commit each; T3-T5 = 1 commit each; T6-T8 = 1 commit each. Total ~8 atomic commits.

## 11. Tests — unit + manual smoke

**Unit (`template/tests/test_assimilate.py`):**

- `test_classify_foreign_hermes_profile` — fixture with `config.yaml` but no `warroom_setup/`; assert `is_hermes=True, is_awr_template=False, already_assimilated=False`.
- `test_classify_already_assimilated` — fixture with `_WR_BEGIN` block + `local/warroom-enroll.json`; assert `already_assimilated=True`.
- `test_classify_detects_discord_creds_in_env` — fixture with `.env` containing `DISCORD_BOT_TOKEN=fake`; assert `channels.discord=True`.
- `test_assimilate_nonexistent_path_returns_3` — pass `/tmp/does-not-exist`; assert exit 3.
- `test_assimilate_non_hermes_dir_returns_3` — empty tmp dir; assert exit 3.
- `test_assimilate_dry_run_writes_nothing` — fixture; hash all files before, run with `--dry-run`, hash after; assert byte-identical.
- `test_assimilate_idempotent` — run twice with `--yes --no-walkthrough --reconfigure`; assert second run produces zero file-content diff.
- `test_assimilate_refuses_repeat_without_reconfigure` — second run without `--reconfigure` returns exit 2.
- `test_assimilate_preserves_existing_hooks_block` — fixture with custom `hooks:` content; assert post-state retains it byte-for-byte.
- `test_assimilate_skips_discord_walkthrough_when_token_present` — `.env` pre-seeded; monkeypatch `discord_walkthrough.run_discord_walkthrough` to assert-not-called.
- `test_assimilate_calls_enroll_bootstrap_with_resolved_label` — monkeypatch `enroll.bootstrap`; assert called with `(profile_root, "default", expected_label)`.
- `test_assimilate_persists_audit_trail` — assert `local/warroom-assimilate.json` exists with `board`, `label`, `channels_walked_through`, `timestamp`.
- `test_assimilate_fail_warn_when_mailbox_cli_absent` — monkeypatch `discover_mailbox_cli` → `None`; assert exit 1 AND `_WR_BEGIN` block still written.
- `test_assimilate_no_walkthrough_no_creds_warns_but_proceeds` — assert exit 0 with stdout warning text "channels: none configured; war-room will be CLI-only".

**Manual smoke (T8):**
Build a fixture `template/tests/fixtures/aahil_like/` that mimics aahil-sh's directory shape (a Hermes profile with its own `hooks/`, its own `plugins/`, an existing `.env` with Discord creds, an existing `persona/decisions.md` with operator content, NO `warroom_setup/`). Run `warroom assimilate <fixture>` end-to-end in a tmp copy. Verify:
- All non-warroom files byte-identical to the fixture original (hash-compare).
- `config.yaml` has the new `_WR_BEGIN` + `_MB_BEGIN` blocks appended (existing content above unchanged).
- `local/persona/decisions.md` retains operator's original content above the sentinel block.
- `.env` retains `DISCORD_BOT_TOKEN` value, adds `MAILBOX_BOARD` + `MAILBOX_LABEL`.
- `local/warroom-enroll.json` exists.
- `local/warroom-assimilate.json` exists.

**DO NOT** touch the real `aahil-sh` profile under `~/.hermes/profiles/`. The smoke test is fixture-only.

## 12. Sanitization audit

- No employer names, no internal hosts, no specific channel IDs in: `assimilate.py`, `SKILL.md`, `cli.py` diff, all test fixtures.
- Fixture names: use `alpha-sh`, `beta-sh`, `shared`, `foreign-sh`, `aahil_like` (the last as directory name only — the fixture file contents must use neutral placeholders like `foreign-sh-handle`, not real handles).
- Walkthrough re-uses existing module — already sanitized.
- Audit trail JSON: ensure timestamps are ISO 8601 in UTC, no machine-specific paths beyond what `profile_root` carries.
- Run `sanitize_check` (shared-core utility) on the full diff before each commit. Add a `test_sanitize_assimilate_fixtures` that greps every fixture under `template/tests/fixtures/foreign_profile*` and `aahil_like/` for the BLOCKED_VALUE_PATTERNS (from `schema.py`) and the project's blocklist words.

## 13. Risks (top 3 + mitigations)

1. **Foreign profile's `config.yaml` uses YAML features our sentinel-based patcher doesn't tolerate (anchors, multi-doc separators, tab indentation).** `_replace_sentinel_block` is a regex over text; if the operator's file has a stray `# >>> warroom-managed` comment that isn't ours (improbable but possible), we corrupt it.
   **Mitigation:** `_classify` reads the file once; if a sentinel line exists but `local/warroom-enroll.json` is absent, refuse with exit 4 ("config.yaml contains a war-room sentinel block but this profile was never enrolled; manual review required"). Don't silently rewrite. Also: the `_WR_BEGIN` string includes `(set via `warroom setup`)` — exact-match unlikely to collide.

2. **Operator's existing `.env` has a custom `MAILBOX_BOARD` already set (e.g. they tested mailbox standalone).** `write_env` does merge-not-replace, but it OVERWRITES on key match, so our value silently clobbers theirs.
   **Mitigation:** Before step 5c, read `<profile>/.env` and if `MAILBOX_BOARD` is present AND differs from the new value, surface in pre-flight report as `[overwrite: MAILBOX_BOARD=<old> -> <new>]` and require explicit confirm. Add `test_assimilate_warns_on_existing_mailbox_board_mismatch`.

3. **Operator restarts Claude Code session before `.env` is re-loaded (Hermes gateway loads `.env` at session start, not on file change).** They run assimilate, immediately run `mailbox ps`, see empty board, get confused.
   **Mitigation:** Post-flight summary EXPLICITLY says "Restart this Claude session so MAILBOX_BOARD/LABEL load into env." SKILL.md repeats it. Also: have `enroll.bootstrap` return `state.status="ok"` only if the mailbox CLI was found AND a daemon ping at the resolved socket succeeded (`daemon_probe.ping_socket`); if ping fails, surface "daemon unreachable; restart your session OR run `mailbox` to spawn the daemon" in the summary.

---

## Open questions (resolve before T1)

- Does the existing `discord_walkthrough.run_discord_walkthrough` accept a `context=` kwarg today, or did that proposal die? If absent, T4 ignores it — the post-flight summary handles context messaging.
- Should assimilate accept a `--enforce` flag to allow the operator to opt INTO confidence-gate enforcement on first contact? Default is OFF (gentler), but power users may want ON. Adding it costs ~2 lines; recommend adding in T3.
- Should `local/warroom-assimilate.json` be merged INTO `local/warroom-enroll.json` (single state file) or kept separate (audit trail vs runtime state)? Separate is clearer for `enroll --status` (only reads enroll state, not assimilate history); keep separate.

---

**Estimated effort:** S-M (~1 day). The orchestration is composition; the smoke fixture + sanitization audit is the bulk of the work. No new modules beyond `assimilate.py`; no new walkthroughs; no new validators.
