# AWR Next-Three Planning — Assimilate / Installer / Cross-Agent Runtime

Date: 2026-06-08. Status: planning. Plans below were produced in parallel by a Workflow fan-out; this doc is the source of truth for choosing the next build.

---

## Recommendation (build order)

# Build Order Recommendation

## 1. Recommended Order

**C-investigation (1 day spike) → shared-core (validators + schema + walkthrough module) → C-implementation → B → A**

Verify C's Risk #1/#4 (gateway env propagation) empirically before anyone writes production code; without that, A and B are decorative wrappers around a non-functional runtime. Then build the shared modules once, land C to make the war room actually work, ship B to make fresh installs trivial, and finish with A to convert existing Hermes profiles.

## 2. Alternative Orders

**Alt 1: B → C → A (ship visible UX first)**
Tradeoff: Accepts shipping a beautiful installer that produces non-functional agents for 2-3 days. Good if you need a demo-able artifact this week and can live with "it installs cleanly, runtime comes next." Bad because the first user who runs B and discovers two agents can't see each other loses trust.

**Alt 2: A+B parallel after C-investigation, then C-implementation, then merge (maximize wall-clock)**
Tradeoff: Accepts merge pain on `patch_war_room_block` signature, `setup.py::write_env` refactor, and the Discord walkthrough module — all three of which A, B, and C touch. Worth it only if you have two engineers and a strict deadline; one engineer should go strictly sequential.

## 3. If I Had To Ship ONE This Week

**Feature C.** It is the only feature that delivers standalone value. A and B are both orchestration over a runtime contract that doesn't yet exist — without C, they produce installs that look successful but never actually join a board. C alone (with a manual `warroom enroll` invocation documented in README) gives you the hero scenario: two agents meeting on a board, exchanging messages, claiming lanes. That is the truthful claim "this template ships a war-room agent." A and B are polish on top.

## 4. Pre-Flight Gaps (Before ANY of A/B/C Can Start)

1. **Verify Hermes gateway env loading (C Risk #1, #4).** Read aahil-sh's gateway config and confirm whether it sources `local/mailbox.env` or `.env` into the Claude Code subprocess. If NO, the entire mailbox board-naming scheme is broken and A/B/C all need a different wiring strategy (likely a `gateway.yaml` patch instead of an env file). **This is a 2-hour read, not a build task — do it first.**
2. **Verify `hermes profile install` CLI contract (B Risk #1).** Run it once, capture exact flags, exit codes, and partial-failure behavior. B's subprocess orchestration is built on assumptions here.
3. **Decide lane CLI strategy (C Risk #2, #3).** Either (a) patch `coordination/src/mailbox/cli.py` to add `claim-lane`/`release-lane` subcommands (small upstream change, ~30 LoC) or (b) declare "war-room template requires `coordination/src` on PYTHONPATH" as a hard prereq. Recommend (a) — it unblocks the SKILL.md upgrade in C and removes a footgun. **Make this call before C's `mailbox_client.py` is written.**
4. **Lock the `war_room:` schema once (shared core).** Create `template/warroom_setup/schema.py` with the canonical key set (`board`, `label`, `min_confidence`, `gate_action`, `show_confidence_badge`, `mailbox_home`, `mailbox_socket`) BEFORE any of A/B/C extend `patch_war_room_block`. Otherwise you get three conflicting signature changes.
5. **Reconcile Discord walkthrough spec disagreement.** A says `MESSAGE CONTENT` intent only; B adds `SERVER MEMBERS` and hardcodes permission integer `277025770560`. Decide intents + permission integer + scopes once, encode in `WALKTHROUGH_STEPS`. ~1 hour with the Discord Developer Portal open.
6. **Extract `patch_persona_decisions` from `run_setup`** (A's plan defines it, but A and B both consume it). Land this refactor as a standalone PR before A/B branch.
7. **Decide label-collision default** (C Risk #9). Default `warroom.label` to Hermes profile `handle`, not `agent_name`. Lock it in `schema.py` and `selectables.py` together.

## 5. Summary Paragraph

I recommend a one-day investigation spike on C's gateway-env and CLI-contract risks (Pre-flight items 1-3), then a shared-core PR that locks the war-room schema, extracts `patch_persona_decisions`, refactors `write_env` to take a `filename=` kwarg, and lands the Discord walkthrough module — followed by C, then B, then A, strictly sequential. C goes first because it is the only feature that delivers standalone value: without it, A and B produce installs that look successful but never actually join a board, so shipping them first burns user trust. B goes second because it amplifies C's reach to fresh installs and exercises the full `run_setup(answers=...)` contract that A will then layer onto for the assimilation path. A goes last because it has the narrowest blast radius (existing Hermes profiles, opt-in) and benefits most from C and B's runtime + UX work being battle-tested first. The shared-core PR is non-negotiable up front — without it, three concurrent signature changes to `patch_war_room_block` and three near-duplicate Discord walkthrough implementations will eat a week of merge pain.

---

## Shared Core Analysis

# Cross-Plan Synthesis Report

## 1. Shared Code Modules (build ONCE)

| Module | Path | Used by | Purpose |
|---|---|---|---|
| **Discord walkthrough** | `template/warroom_setup/discord_walkthrough.py` (A names it) / `walkthrough.py` (B) — **pick A's path** | A, B | `run_discord_walkthrough()` + `WALKTHROUGH_STEPS` constant + `_validate_token`/`_validate_channel_id` |
| **War-room schema** | `template/warroom_setup/schema.py` (A proposes) | A, B, C | Canonical keys: `board`, `agent_id`/`label`, `min_confidence`, `gate_action`, `show_confidence_badge`, `mailbox_home`, `mailbox_socket` |
| **`patch_war_room_block`** | `template/warroom_setup/setup.py` (exists) | A, B, C | A reuses verbatim; C extends signature with `label`, `mailbox_home`, `mailbox_socket` kwargs — coordinate signature |
| **`patch_persona_decisions`** | `template/warroom_setup/setup.py` (A extracts) | A (defined here) | Sentinel-bounded persona append; A creates by refactoring out of `run_setup` |
| **`write_env` (parameterized)** | `template/warroom_setup/setup.py` | A, B, C | C needs `filename=` kwarg to write `local/mailbox.env` — refactor once |
| **`prompt_secret`** | `template/warroom_setup/prompts.py` | A, B | Masked token entry — A adds it, B consumes (currently uses `prompt_text`) |
| **Validators** | `template/warroom_setup/validators.py` (B proposes) | A, B, C | Agent/board name regex, channel-id snowflake check, token shape check |
| **State / atomic JSON** | `template/warroom_setup/state.py` (B) | B, C | C's `_atomic_write_json` duplicates B's `save_state`; collapse into one |
| **Detection / sentinel parsing** | `template/warroom_setup/detect.py` (A) | A, C (status) | `_find_sentinel_block`, `_extract_existing_warroom` — C's `enroll --status` should reuse |

## 2. Cross-Feature Dependencies

**A → C:** A is described as "shippable independently" but its `assimilate` walkthrough writes a `war_room:` block that is **purely decorative** until C wires actual mailbox join. A's "Next: run 'warroom enroll'" message presupposes C exists.

**B → C:** Same problem, sharper. B's installer ends with "Done. Try it: `hermes run`" — but without C, the resulting agent doesn't actually join any board. B's `run_setup(answers=...)` extension feeds the same `patch_war_room_block` that C extends; **the two signature changes must be merged, not stacked.**

**B → A:** B explicitly calls out the dependency: "if A adds a `setup.py::join_mailbox(...)` helper, the installer should call it as a 5th post-install phase." B proposes a `_post_setup_hook` callable to decouple ordering — this is the right escape hatch.

**C blockers for A/B:** C's **Risk #1 and #4** (gateway env propagation of `MAILBOX_BOARD` to Claude subprocess) are gating realism for both A and B. If Hermes gateway does not source `local/mailbox.env`, then A's "assimilation" and B's "installation" both finish with a non-functional war room. **C must verify gateway env loading BEFORE A or B claim "wires you into the war room."**

**C reveals hidden blocker for A:** C's Risk #3 (CLI abspath rewrite breaks `lane://` URIs) means A's "copy `plugins/warroom-gate/`" wholesale assumes a runtime contract that doesn't fully exist for lane ops. A's confidence-gate copy is fine; lane claim/release in the new SKILL.md is not.

**Discord walkthrough divergence:** A specifies 7 steps; B specifies 7 steps but with a hardcoded permission integer (`277025770560`) and additional intent (`SERVER MEMBERS INTENT`). **The two specs disagree on Discord configuration** — must be reconciled in the shared module.

## 3. Risk Register (Top 3)

| # | Severity | Surfaced by | Risk |
|---|---|---|---|
| 1 | **BLOCKER** | C (Risk #1, #4) | `MAILBOX_BOARD` env reaching the Claude subprocess is unverified. If Hermes gateway does not source `local/mailbox.env`, **the entire war-room runtime is non-functional** regardless of A and B's wiring. Two profiles will land on different auto-derived `repo-<hash>` boards and never meet. Must be empirically verified before A/B/C lock signatures. |
| 2 | **MAJOR** | C (Risk #2, #3) | Lane claim/release is **only reachable via in-process import** of `coordination.mailbox.client`. The shim CLI's `abspath` rewrite breaks `lane://auth` → `/cwd/lane:/auth`. C's `MailboxBridge.claim_lane` fails in any pure-template install where `coordination/src` isn't on `sys.path`. A's SKILL.md upgrade and B's installer-time `mailbox enable` cannot rely on this path. Either patch upstream mailbox CLI or document hard prerequisite. |
| 3 | **MAJOR** | A (Risk #1, #6), B (Risk #4, #5) | **YAML/text-level config mutation fragility + Discord/Slack spec drift.** A's `_merge_skill_bundles` text-level merge can corrupt flow-style lists; A and B disagree on Discord intents/permission-integer; B hardcodes `277025770560` and Slack Socket-Mode-vs-Events choice is unverified. Any of these silently produce a broken install that passes tests. A's recommendation (keep bundle entry inside sentinel block, never mutate user's list) is the right mitigation and should be globally enforced. |

Minor (not in top 3 but worth noting): token leaking to scrollback (A Risk #2), label collisions on same-machine installs (C Risk #9), session-id provenance for `enroll --status` (C Risk #5).

## 4. Discord Walkthrough Module — Recommended Reuse

**Recommendation: ONE shared Python module + ONE shared SKILL.md fragment, NOT a templated text file.**

### Structure

```
template/warroom_setup/discord_walkthrough.py   <-- single source of truth
  - WALKTHROUGH_STEPS: list[Step]               <-- data, not code
  - run_discord_walkthrough(prompts, *, context: str) -> DiscordCreds
  - _validate_token, _validate_channel_id

template/skills/_shared/discord-setup.md        <-- short SKILL.md fragment
  - Human-readable version of the same steps for agent-mode invocation
  - Generated from WALKTHROUGH_STEPS by a build step OR hand-kept in sync via test
```

### Why this shape

1. **`WALKTHROUGH_STEPS` as module-level data** (already in A's plan) — B's `_render_step` and A's `_step` both consume the same `Step` dataclass. No copy-paste of step text.
2. **Single function, context parameter.** A calls `run_discord_walkthrough(prompts, context="assimilate")`; B calls it with `context="install"`. The function adjusts the closing message ("Returning to assimilator..." vs "Continuing installation...") but the 7 steps are identical bytes.
3. **Reconcile the spec disagreement once:** intents list (`MESSAGE CONTENT` only vs `+ SERVER MEMBERS`), permission integer, scopes list — decided once in `WALKTHROUGH_STEPS`, tested once.
4. **SKILL.md fragment for agent-mode** — both A's `assimilate-warroom/SKILL.md` and any future "join war room" skill can `@include` or reference `_shared/discord-setup.md`. Hand-keep in sync with a test (`test_walkthrough_steps_match_skill_doc`) that diffs the rendered step bodies against the markdown.
5. **NOT a templated text file** — text templates can't enforce validation (`_validate_token`, snowflake check) and can't conditionally skip steps based on existing env. Python module wins.

### Slack symmetry

Same shape: `template/warroom_setup/slack_walkthrough.py` with `SLACK_WALKTHROUGH_STEPS`. B owns it (A doesn't include Slack); A can opt-in later by importing.

### Migration order

1. B's plan defines the richer 7-step Discord flow with skip/quit affordances and a state machine — **adopt B's structure**, port A's `WALKTHROUGH_STEPS` data-driven approach on top.
2. Land the shared module with B (which has higher LoC investment in walkthroughs), have A import it.
3. Add the test that asserts both A's and B's consumers produce identical step output.

---

## Plan A — Assimilate Existing Profile

# Feature A — Assimilate an Existing Hermes Profile into the War Room

## 1. Goal

Provide a skill + CLI subcommand that converts an existing Hermes profile (with its own pre-wired Discord/Slack/model config) into a war-room participant via an inline Discord walkthrough, sentinel-managed config patches, and idempotent re-runnable assimilation — without clobbering the owner's existing edits.

## 2. Scope

**In:**
- New skill `template/skills/assimilate-warroom/SKILL.md` (agent-loaded protocol).
- New CLI subcommand `warroom assimilate <profile_path>` in `template/warroom_setup/cli.py`.
- New module `template/warroom_setup/assimilate.py` (orchestrator).
- Inline numbered Discord bot walkthrough (create app -> bot token -> Message Content intent -> server invite -> channel ID).
- Detection of existing `hooks:`, `plugins:`, `skill-bundles:`, `war_room:` blocks in target `config.yaml`.
- Idempotent sentinel-managed write of `_WR_BEGIN/_WR_END` block via reused `patch_war_room_block`.
- Idempotent append to `persona/decisions.md` (sentinel `<!-- _WR_PERSONA_BEGIN -->` ... `<!-- _WR_PERSONA_END -->`).
- Optional copy of `template/plugins/warroom-gate/` into `<profile>/plugins/warroom-gate/` (with overwrite confirmation if already present).
- Append-only merge of `skill-bundles:` entry (add `confidence-gate` reference without dropping existing bundles).
- Pre-flight detection report (what we'll change / what's already war-room-ready) before any write.
- Atomic writes (temp + `os.replace`) for every mutated file.
- Backup of `config.yaml` and `persona/decisions.md` to `<file>.bak.<timestamp>` before first mutation.

**Out:**
- Automating Discord application creation (manual walkthrough only).
- Migrating non-Hermes profiles or non-yaml configs.
- Migrating away from a different model provider — detect and preserve, never clobber.
- Mailbox `join` execution (covered by Feature B).
- Brand-new profile bootstrap (existing `warroom setup` covers that).

## 3. File Paths to Create + Modify

**Create:**
- `template/skills/assimilate-warroom/SKILL.md`
- `template/warroom_setup/assimilate.py`
- `template/warroom_setup/discord_walkthrough.py`
- `template/warroom_setup/detect.py`
- `template/tests/test_assimilate.py`
- `template/tests/test_detect.py`
- `template/tests/test_discord_walkthrough.py`
- `template/tests/fixtures/profile_minimal/config.yaml`
- `template/tests/fixtures/profile_with_hooks/config.yaml`
- `template/tests/fixtures/profile_with_warroom/config.yaml`
- `template/tests/fixtures/profile_with_persona/persona/decisions.md`

**Modify:**
- `template/warroom_setup/cli.py` — add `assimilate` subparser.
- `template/warroom_setup/setup.py` — extract `patch_persona_decisions(profile_root, rule_text)` helper from existing persona-writing code so assimilate.py can reuse it. (Currently the persona rule is inlined inside `run_setup`; refactor into a named function.)
- `template/warroom_setup/prompts.py` — add `prompt_secret(label, current=None)` if not already present, for token entry with masking.

## 4. Function Signatures + Responsibility

### `template/warroom_setup/assimilate.py`
- `def assimilate(profile_root: Path, *, interactive: bool = True, dry_run: bool = False, copy_gate_plugin: bool = True) -> AssimilationReport` — top-level orchestrator; runs detect, walkthrough, patches.
- `def _confirm_profile(profile_root: Path) -> ProfileFacts` — validate it's a Hermes-shaped profile (has `config.yaml`, optionally `persona/`), bail loudly otherwise.
- `def _collect_warroom_inputs(facts: ProfileFacts, prior: dict | None) -> WarRoomInputs` — prompts for board name, agent id, Discord token, channel id, gate thresholds; pre-fills from existing block if present.
- `def _apply_patches(profile_root: Path, inputs: WarRoomInputs, facts: ProfileFacts, *, dry_run: bool) -> list[PatchResult]` — fan out: backup, patch yaml, patch persona, copy plugin; each step append-only & sentinel-bounded.
- `def _copy_gate_plugin(profile_root: Path, *, force: bool = False) -> PatchResult` — shutil.copytree of `template/plugins/warroom-gate/` to `<profile>/plugins/warroom-gate/`, skip if hash matches.
- `def _merge_skill_bundles(config_text: str, bundle_id: str) -> str` — yaml-text-level append (avoid PyYAML round-trip loss); sentinel-bounded if no existing block.
- `def _summary(report: AssimilationReport) -> str` — human-readable pre-flight + post-flight summary.

### `template/warroom_setup/detect.py`
- `def detect_profile(profile_root: Path) -> ProfileFacts` — returns dataclass with: `has_config`, `has_persona_dir`, `has_persona_decisions`, `has_hooks_block`, `has_plugins_block`, `has_skill_bundles_block`, `has_warroom_block`, `model_provider` (anthropic / openai / unknown), `existing_warroom_inputs` (parsed sentinel block if present).
- `def _read_yaml_text(path: Path) -> str` — stdlib read; never parses (we operate at text level to preserve comments).
- `def _find_sentinel_block(text: str, begin: str, end: str) -> tuple[int, int] | None` — returns char offsets or None.
- `def _extract_existing_warroom(text: str) -> dict | None` — parses the existing `_WR_BEGIN`/`_WR_END` block with stdlib yaml-lite (key: value lines only — same constraint as `patch_war_room_block` produces).
- `def _detect_model_provider(text: str) -> str` — regex over `model:` / `provider:` lines; returns `"anthropic"`, `"openai"`, `"unknown"`.

### `template/warroom_setup/discord_walkthrough.py`
- `def run_discord_walkthrough(prompts) -> DiscordCreds` — inline numbered walkthrough; calls `prompts.confirm()` and `prompts.prompt_secret()` between steps.
- `def _step(n: int, title: str, body: list[str]) -> None` — pretty-print one numbered step block to stdout.
- `def _validate_token(token: str) -> bool` — regex sanity check (Discord bot tokens: `^[A-Za-z0-9._-]{50,80}$`); does NOT hit network.
- `def _validate_channel_id(cid: str) -> bool` — must be 17-20 digit snowflake.
- `WALKTHROUGH_STEPS: list[Step]` — module-level constant defining the 7 numbered steps below so tests can assert presence of required strings.

### `template/warroom_setup/cli.py` (modify)
- New subparser `assimilate` with args: `profile_path` (positional), `--dry-run`, `--no-copy-plugin`, `--non-interactive`.
- Handler `_cmd_assimilate(args) -> int` — instantiates prompts, calls `assimilate.assimilate(...)`, prints summary, returns 0/1.

### `template/warroom_setup/setup.py` (modify)
- Extract: `def patch_persona_decisions(profile_root: Path, rule_text: str, *, sentinel_id: str = "warroom") -> bool` — sentinel-bounded append; returns True if file changed.

## 5. TUI / UX Flow

The agent (in the existing Hermes session) invokes the skill when the owner says "join the war room" / "assimilate" / "wire me into the war room." Skill instructs agent to run `python -m warroom_setup assimilate $HERMES_PROFILE_DIR`.

1. **Detect.** CLI prints: `Inspecting <profile_path>...` then a 6-line report:
   ```
   config.yaml          found
   persona/decisions.md found
   model provider       anthropic (preserved as-is)
   war_room block       not present
   hooks block          present (preserved)
   plugins block        present (will append warroom-gate)
   ```
2. **Confirm scope.** Prompt: `Proceed with assimilation? [y/N]` — abort on N.
3. **Discord walkthrough** (only if no existing token detected in env or block):
   - Step 1: "Open https://discord.com/developers/applications and click **New Application**. Name it after your war room (e.g. `<board>-bot`)."
   - Step 2: "In the left sidebar click **Bot** -> **Reset Token** -> **Copy**. Paste it below."
   - Prompt: `Discord bot token (input hidden): `
   - Step 3: "On the same Bot page, scroll to **Privileged Gateway Intents** and toggle **MESSAGE CONTENT INTENT** ON. Save."
   - Step 4: "Go to **OAuth2** -> **URL Generator**. Scopes: check `bot`. Bot Permissions: `View Channels`, `Send Messages`, `Read Message History`. Copy the generated URL and open it in your browser to invite the bot to your server."
   - Step 5: "In Discord, enable Developer Mode (User Settings -> Advanced -> Developer Mode). Right-click your war-room channel -> **Copy Channel ID**."
   - Prompt: `Discord channel ID: `
   - Step 6: "Test by typing in the channel. The bot should appear in the member list with a green dot once we run join."
   - Step 7: "Returning to assimilator..."
4. **Collect war-room inputs:**
   - `Board name [hermes-warroom]: `
   - `Agent id [aahil-sh]: ` (default from `profile_root.name`)
   - `Min confidence [75]: `
   - `Gate action on low confidence (abstain/escalate/post-anyway) [abstain]: `
5. **Pre-flight diff.** Print: `The following files will change:` listing each path with `[create]`, `[modify+sentinel-append]`, `[backup -> .bak.<ts>]`. Prompt `Apply? [y/N]`.
6. **Apply.** For each file: backup, atomic write. Stream progress: `[ok] config.yaml`, `[ok] persona/decisions.md`, `[ok] plugins/warroom-gate/ (copied)`, `[ok] skill-bundles entry`.
7. **Post-flight summary.** Print the final state and the exact command to run next (Feature B's `warroom enroll` once it exists): `Next: run 'warroom enroll' to claim a lane in '<board>'.`
8. **Re-run safety message.** `Re-run this command anytime; the sentinel block will be replaced in-place.`

Non-interactive mode (`--non-interactive`) reads from env vars `WARROOM_DISCORD_TOKEN`, `WARROOM_DISCORD_CHANNEL_ID`, `WARROOM_BOARD`, etc., and fails fast if missing.

## 6. Test Strategy

**`test_detect.py`**
- `test_detect_minimal_profile_no_warroom` — fixture with just `model:` and `provider:`; asserts all `has_*_block` flags False except `has_config`.
- `test_detect_existing_warroom_block_parses_inputs` — fixture with a `_WR_BEGIN/_WR_END` block; asserts `existing_warroom_inputs == {"board": "...", "agent": "..."}`.
- `test_detect_preserves_unknown_provider` — fixture with `provider: cohere`; asserts `model_provider == "unknown"` and we do NOT raise.
- `test_find_sentinel_block_not_present_returns_none`.

**`test_discord_walkthrough.py`**
- `test_walkthrough_steps_contain_required_strings` — assert each of "Message Content", "URL Generator", "Developer Mode", "Copy Channel ID" appears in `WALKTHROUGH_STEPS`.
- `test_validate_token_rejects_short` / `test_validate_token_accepts_realistic` (use a synthetic 60-char string).
- `test_validate_channel_id_accepts_18_digit` / `rejects_alphanumeric`.

**`test_assimilate.py`**
- `test_assimilate_dry_run_writes_nothing` — fixture profile, run with `dry_run=True`, assert no file content changed (hash both before & after).
- `test_assimilate_idempotent` — run twice with same inputs, assert second run produces zero diffs in target files (sentinel block bytes identical, plugin dir hash identical).
- `test_assimilate_preserves_existing_hooks_block` — fixture with custom `hooks:` content; assert post-state still contains it byte-for-byte.
- `test_assimilate_preserves_existing_skill_bundles_entries` — fixture with `skill-bundles: [foo, bar]`; assert post-state contains `foo`, `bar`, AND `confidence-gate`.
- `test_assimilate_creates_backup_on_first_run_only` — assert `.bak.<ts>` exists after run 1; assert no NEW backup created after run 2 if no content diff.
- `test_assimilate_persona_append_idempotent` — assert sentinel-bounded persona block written once, no duplicates after re-run.
- `test_assimilate_skips_plugin_copy_when_present_and_unchanged` — pre-stage `plugins/warroom-gate/` with matching content; assert no rewrite.
- `test_assimilate_refuses_non_hermes_profile` — empty dir; assert raises `ProfileShapeError` with helpful message.
- `test_assimilate_non_interactive_uses_env_vars` — monkeypatch env, assert no prompt called.
- `test_assimilate_non_interactive_missing_env_fails_fast` — assert exits non-zero with message naming the missing var.

## 7. Risks / Unknowns

1. **YAML round-trip preservation.** Operating at text level (regex + sentinel) avoids comment loss, but `_merge_skill_bundles` needs care: if existing `skill-bundles:` is a flow-style list `[a, b]` vs block-style `- a\n- b`, our merge logic must handle both — or we sidestep by writing the war-room bundle entry inside the sentinel block instead of mutating the user's list. **Recommendation: keep the bundle entry inside `_WR_BEGIN/_WR_END`** as `skill_bundles_warroom: [confidence-gate]`, and load-merge at runtime — avoids the parse problem entirely.
2. **Discord token in stdout history.** Even with `prompt_secret`, terminal scrollback may retain it. Document this; recommend rotating after first save. Tests should assert token never appears in audit log or stdout summary.
3. **Plugin path collision.** Owner may already have a `plugins/warroom-gate/` they hand-modified. Detect via hash; if mismatch, prompt before overwrite, never silent-clobber.
4. **Persona file may not exist.** If `persona/decisions.md` absent, decide: create it, or skip the persona append. **Recommendation: create with sentinel block only**, mark in summary as `[create]`.
5. **Existing `_WR_BEGIN` block from older template version.** Schema migration risk. **Mitigation:** `_extract_existing_warroom` should tolerate unknown keys and re-emit only the current canonical key set (drop unknowns into a `legacy:` subdict logged to summary).
6. **Non-anthropic provider.** Confidence-gate plugin assumes a `transform_llm_output` hook contract. If provider differs, the gate plugin may not fire. **Recommendation:** detect provider, print warning if not `anthropic`, but still apply the patch (gate fails open in that case — explicit in plugin code, not us).
7. **Concurrent re-entry.** Two simultaneous `assimilate` runs on the same profile could race. Mitigation: write a `.warroom.assimilate.lock` file via `os.open(..., O_CREAT|O_EXCL)`, release in `finally`.

## 8. Existing Code to Reuse

- `patch_war_room_block` (`template/warroom_setup/setup.py`) — primary sentinel-managed yaml block writer. **Reuse verbatim** for the `war_room:` block.
- `write_env` (`template/warroom_setup/setup.py`) — write Discord token/channel id into `<profile>/.env` (sentinel-bounded). Reuse to avoid hardcoding secrets in `config.yaml`.
- `seed_overlay` (`template/warroom_setup/setup.py`) — if assimilator needs to drop an overlay file (e.g. `overlays/warroom.yaml`), reuse this for atomic copy.
- `prompts` module (`template/warroom_setup/prompts.py`) — reuse `prompt_text`, `prompt_choice`, `confirm`; add `prompt_secret` if not present.
- `render.py` raw-mode TUI (`template/warroom_setup/render.py`) — NOT used here. Assimilator is a single linear flow with simple prompts, not a multi-stage form, so we use plain `prompts.py` only. Keeps the surface small.
- `template/plugins/warroom-gate/` — copied wholesale into target profile.
- `template/warroom_setup/selectables.py` — reuse `default_ids()` for default board/agent id derivation.

## 9. Dependencies

- **Blocked by:** none. Assimilator can ship independently; it writes config but doesn't require Feature B's mailbox-join to function.
- **Blocks:** Feature B (enroll). The owner runs assimilate first to get config + plugin in place, then `warroom enroll` actually claims a lane in the mailbox. Feature B's enroll command will read the same `_WR_BEGIN/_WR_END` block we write.
- **Shares code with:**
  - Feature B: both consume the sentinel-managed `war_room:` block. Lock the schema (keys: `board`, `agent_id`, `min_confidence`, `gate_action`, `show_confidence_badge`) in this plan and share via `template/warroom_setup/schema.py` (new module) — Feature B reuses.
  - Feature C: if C is a status/health command, it also reads the same block and the new `plugins/warroom-gate/` location.

## 10. Estimated Effort

**M** — ~1.5-2 days. The orchestration is mostly composition of existing primitives (`patch_war_room_block`, `prompts`, `shutil.copytree`), but detection (`detect.py`) needs careful text-level parsing to avoid yaml round-trip issues, the Discord walkthrough needs careful copy-editing for accuracy (Discord UI changes; need to verify against current Developer Portal), and the test fixture matrix (minimal / with-hooks / with-warroom / non-hermes) is moderate. Idempotency + backup + lock-file logic adds rigor but is straightforward stdlib.

---

## Plan B — Interactive Installer (fresh installs)

# Feature B — ccpkg-style Interactive Installer for Fresh War-Room Agent Installs

## 1. Goal

Deliver a single-command, ccpkg-pattern TUI installer that drives a fresh war-room agent from "owner runs one script" through name validation, inline Discord/Slack walkthroughs, model + board selection, `hermes profile install`, post-install setup, plugin enablement, and `.env` population — composing the existing wizard/render/setup primitives rather than duplicating them.

## 2. Scope

**In:**
- New CLI entry `python3 -m warroom_setup.installer` and a thin shim `template/scripts/install.sh` that bootstraps and invokes it.
- Pre-install collection phase: name, channels, Discord inline walkthrough, Slack inline walkthrough, model, war-room board.
- Orchestration phase: shell out to `hermes profile install`, then drive existing `run_setup` with already-collected answers (no re-prompting), then `hermes plugins enable warroom-gate`, then conditional `.env` write.
- Graceful error handling at each phase boundary (install fail → abort; user skipped Discord → skip Discord-token/channel prompts and exclude Discord from enabled channels).
- Resume-safe state file (`~/.cache/warroom_setup/installer-<name>.json`, atomic write, mode 0600) so a crash mid-`hermes install` doesn't lose collected answers.
- Reuse the raw-mode termios TUI substrate from `template/warroom_setup/render.py` for all interactive prompts.

**Out:**
- Replacing or deprecating `scripts/setup.sh` — it stays valid for power users / re-runs.
- Bundling Discord/Slack SDKs or hitting their APIs (walkthrough is owner-guided in browser, installer captures pasted values).
- Modifying `hermes` itself or the `warroom-gate` plugin code.
- Multi-agent batch install (one agent per invocation).
- Confidence-gate prompting (handled inside `run_setup` already; installer just passes through).

## 3. File Paths to Create + Modify

**Create:**
- `template/warroom_setup/installer.py` — orchestrator (entry: `main()`).
- `template/warroom_setup/walkthrough.py` — inline Discord + Slack step renderers.
- `template/warroom_setup/state.py` — atomic JSON read/write for installer resume state.
- `template/scripts/install.sh` — bash shim that locates `python3`, sets `PYTHONPATH=<template>`, execs `python3 -m warroom_setup.installer "$@"`.
- `template/warroom_setup/tests/test_installer.py`
- `template/warroom_setup/tests/test_walkthrough.py`
- `template/warroom_setup/tests/test_state.py`

**Modify:**
- `template/warroom_setup/cli.py` — add `installer` subcommand alias (so `python3 -m warroom_setup installer` works alongside `python3 -m warroom_setup.installer`).
- `template/warroom_setup/setup.py` — expose `run_setup(answers: dict | None = None, interactive: bool = True)` overload so installer can pass pre-collected answers and skip re-prompting (additive, default behavior unchanged).
- `template/warroom_setup/selectables.py` — add `INSTALLER_STAGES` list (pre-install stages: name → channels → discord_walkthrough → slack_walkthrough → model → board) distinct from existing post-install `TOGGLES` / `TEXT_FIELDS`.
- `template/warroom_setup/render.py` — add `prompt_continue(label: str) -> None` helper (blocking "Press Enter to continue") if not already present; keep raw-mode substrate untouched otherwise.

## 4. Function Signatures + 1-Line Responsibilities

### `template/warroom_setup/installer.py`

- `main(argv: list[str] | None = None) -> int` — CLI entry; parses `--name`, `--resume`, `--non-interactive`, returns POSIX exit code.
- `collect_answers(state_path: Path, resume: bool) -> dict` — Run pre-install stages, merge with resumed state, return answer dict consumed by setup.py.
- `prompt_name(existing: str | None) -> str` — Prompt + validate against `^[a-z][a-z0-9-]{1,30}$`, refuse collisions with existing `hermes profile list`.
- `prompt_channels(existing: list[str]) -> list[str]` — TUI multi-select over `["discord", "slack", "cli-only"]`; returns enabled set.
- `prompt_model(existing: str | None) -> str` — Single-select TUI over `["claude-opus-4-7", "claude-sonnet-4-5", "claude-haiku-4"]`.
- `prompt_board(existing: str | None) -> str` — Free-text prompt, validate `^[a-z0-9-]{1,40}$`, default `"main"`.
- `run_hermes_install(name: str, template_root: Path) -> Path` — `subprocess.run(["hermes", "profile", "install", str(template_root), "--name", name], check=True)`; returns resolved profile root or raises `InstallerError`.
- `enable_gate_plugin(profile_root: Path) -> None` — `subprocess.run(["hermes", "plugins", "enable", "warroom-gate"], cwd=profile_root, check=True)`; tolerates "already enabled".
- `write_env_conditional(profile_root: Path, answers: dict) -> None` — Calls `setup.write_env` only with keys the owner actually provided (filters empty/skipped values).
- `class InstallerError(Exception)` — Raised for fatal stage failures; carries phase name + remediation hint.
- `run_phase(name: str, fn: Callable, state: dict, state_path: Path) -> Any` — Wrapper that logs phase start/end, atomically checkpoints state after each phase, surfaces errors as `InstallerError`.

### `template/warroom_setup/walkthrough.py`

- `discord_walkthrough(agent_name: str) -> dict` — Returns `{"bot_token": str|None, "channel_id": str|None, "skipped": bool}`; renders 7 numbered steps with copy-pasteable strings (bot name suggestion, intent flags, permission integer, invite URL template), pauses on each substep via `prompt_continue`, then collects token + channel ID via `prompt_text`.
- `slack_walkthrough(agent_name: str) -> dict` — Returns `{"bot_token": str|None, "app_token": str|None, "channel_id": str|None, "skipped": bool}`; renders numbered steps (create app, OAuth scopes list, install to workspace, copy bot token, enable Socket Mode, app-level token, invite to channel).
- `_render_step(num: int, total: int, title: str, body: list[str]) -> None` — Pretty-prints one walkthrough step using the same border/style as `render.py`.
- `_offer_skip(channel: str) -> bool` — Standard "[s]kip this channel / [c]ontinue / [q]uit installer" prompt.

### `template/warroom_setup/state.py`

- `load_state(path: Path) -> dict` — Returns `{}` if missing or unreadable; never raises on missing file.
- `save_state(path: Path, data: dict) -> None` — `tempfile.NamedTemporaryFile` in same dir + `os.replace`; chmod 0600 before replace.
- `clear_state(path: Path) -> None` — Best-effort unlink after successful install.
- `state_path_for(agent_name: str) -> Path` — Returns `Path.home() / ".cache" / "warroom_setup" / f"installer-{agent_name}.json"`; creates parent with mode 0700.

### `template/warroom_setup/setup.py` (modified)

- `run_setup(*, answers: dict | None = None, interactive: bool = True, profile_root: Path | None = None) -> int` — New kwargs: if `answers` is provided, skip wizard and feed values straight into `patch_war_room_block` + `write_env` + `seed_overlay`; preserves today's behavior when called with no args.

## 5. TUI / UX Flow

```
$ bash template/scripts/install.sh
```

**Step 1 — Welcome + name**
```
+-------------------------------------------------+
|  War-Room Agent Installer                       |
|  ccpkg-style guided setup                       |
+-------------------------------------------------+
  Agent short name (lowercase, hyphens ok):
  > aria-sh_
```
Validation: regex + collision check against `hermes profile list`. Bad input → red inline error, reprompts.

**Step 2 — Channels**
Numbered fallback view (matches `render.py` style):
```
  Which channels should this agent listen on?
  Space toggles, Enter confirms.
  [x] 1. Discord
  [x] 2. Slack
  [ ] 3. CLI-only
```

**Step 3 — Discord walkthrough (inline, only if Discord checked)**
```
  Step 1/7 - Open the Discord Developer Portal
    https://discord.com/developers/applications

  Press Enter when you have the page open...
```
Substeps inline (each its own screen, owner presses Enter between):
1. Open dev portal.
2. Click "New Application", name it `aria-sh-bot` (copy-pasteable).
3. Bot tab → enable `MESSAGE CONTENT INTENT` + `SERVER MEMBERS INTENT`.
4. Reset Token → copy. Then installer asks: `Paste bot token (will not echo): `
5. OAuth2 → URL Generator → scopes `bot applications.commands`, permissions integer `277025770560` (shown copy-pasteable).
6. Open generated invite URL, authorize to server.
7. Right-click target channel → Copy Channel ID. Installer asks: `Paste channel ID: `

At any step: `[s]kip Discord / [c]ontinue / [q]uit installer`. If skipped: token/channel ID prompts are suppressed and Discord is removed from `enabled_channels`.

**Step 4 — Slack walkthrough (inline, only if Slack checked)** — same shape, ~6 steps, captures `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` + channel ID.

**Step 5 — Model picker**
```
  Default model for this agent:
    1. claude-opus-4-7    (max capability)
  > 2. claude-sonnet-4-5  (balanced)
    3. claude-haiku-4     (fast/cheap)
```

**Step 6 — War-room board**
```
  War-room board name [main]:
  > _
```

**Step 7 — Confirm + execute**
```
  Ready to install:
    name:    aria-sh
    channels: discord, slack
    model:    claude-sonnet-4-5
    board:    main
  Proceed? [Y/n] _
```

**Step 8 — Execute (non-interactive, streamed output)**
```
  [1/4] Running: hermes profile install <template> --name aria-sh
        ... ok (1.2s)
  [2/4] Running post-install setup (patching war-room block)...
        ... ok
  [3/4] Enabling warroom-gate plugin...
        ... ok
  [4/4] Writing .env (Discord + Slack secrets)...
        ... ok

  Done. Try it:
    cd ~/.hermes/profiles/aria-sh
    hermes run
```

On failure at any phase: print phase name, exit code, last 20 lines of stderr, remediation (`Resume with: bash install.sh --resume aria-sh`), exit non-zero. State file preserved so `--resume` skips already-completed phases.

## 6. Test Strategy

**`tests/test_state.py`**
- `test_load_state_missing_returns_empty` — no file, returns `{}`.
- `test_save_state_is_atomic` — kill mid-write via `monkeypatch` on `os.replace` raising; verify original file intact.
- `test_save_state_mode_0600` — assert `stat().st_mode & 0o777 == 0o600`.
- `test_clear_state_idempotent` — call twice, no exception.

**`tests/test_walkthrough.py`**
- `test_discord_walkthrough_happy_path` — feed scripted stdin (Enter x6, token, channel id), assert returned dict has both values, `skipped=False`.
- `test_discord_walkthrough_skip_at_step_3` — feed `s` at step 3, assert `skipped=True`, no token/channel prompts reached.
- `test_slack_walkthrough_happy_path` — symmetric.
- `test_render_step_shape` — snapshot border/numbering matches `render.py` style.

**`tests/test_installer.py`**
- `test_prompt_name_rejects_invalid` — `UPPER`, leading digit, length > 31, all rejected.
- `test_prompt_name_rejects_collision` — monkeypatch `hermes profile list` to return `["aria-sh"]`; reprompt.
- `test_collect_answers_resume_skips_completed_phases` — pre-seed state file with `name` + `channels`, assert only `model` and `board` are prompted.
- `test_run_hermes_install_failure_raises_installer_error` — monkeypatch `subprocess.run` to return code 1; assert `InstallerError("hermes-install", ...)`.
- `test_write_env_conditional_omits_skipped_channels` — answers say Discord skipped; `.env` written has no `DISCORD_*` keys.
- `test_enable_gate_plugin_tolerates_already_enabled` — stderr contains `"already enabled"` → return 0, not raise.
- `test_run_setup_with_answers_skips_wizard` — call `run_setup(answers={...}, interactive=False)`; assert no TTY prompts invoked (patch `render.prompt_*` to assert-not-called).
- `test_end_to_end_dry_run` — set `WARROOM_INSTALLER_DRY_RUN=1`; full flow runs, all `subprocess.run` calls captured + asserted in order.

**Modified `setup.py`**
- Add `test_run_setup_backwards_compat` — calling `run_setup()` with no args still drives the original wizard path.

## 7. Risks / Unknowns

1. **`hermes profile install` invocation contract** — Need to confirm exact flags (`--name`? `--template`? positional?) and exit codes. Plan assumes `hermes profile install <template_root> --name <name>` per task description; verify against `hermes` CLI before implementation.
2. **`hermes plugins enable` cwd semantics** — Does it require running from inside the profile root, or take a `--profile` flag? Affects subprocess `cwd=`.
3. **Terminal capability detection** — If `sys.stdin.isatty()` is False (e.g., piped invocation), installer must refuse cleanly and suggest `--non-interactive` mode with answers via flags/env (out of scope for this plan, but exit path needed).
4. **Discord intent + permission integer drift** — Hardcoding `277025770560` risks staleness. Mitigation: comment with last-verified date + link to Discord permission calculator; revisit on each template release.
5. **Slack Socket Mode vs Events API choice** — Existing `aahil-sh` may use one or the other; the walkthrough must match what the template's runtime expects. Need to confirm before writing step 5 of Slack walkthrough.
6. **Resume after partial `hermes install`** — If `hermes` half-creates a profile then crashes, `--resume` would hit a collision. Mitigation: on resume, detect partial profile (exists but no `setup.sh` marker) and offer `--force` to remove + retry.
7. **`.env` write ordering vs gate plugin enable** — If gate plugin reads `.env` at enable time, env must be written first. Plan currently does enable then env; revisit based on plugin behavior.
8. **TTY echo suppression for token paste** — `getpass.getpass` is stdlib but interacts oddly with raw-mode termios from `render.py`. Need to ensure raw mode is fully restored before token prompt, or use `termios.tcsetattr` to mask echo manually.

## 8. Existing Code to Reuse

- `template/warroom_setup/render.py` — raw-mode termios substrate; specifically the TUI loop driver (whichever function name renders the numbered/arrow-key picker today — installer's `prompt_channels`, `prompt_model` call it directly). Reuse, do not reimplement.
- `template/warroom_setup/render.py` — numbered fallback path when `TERM` is dumb or stdin isn't a TTY; installer inherits this for free.
- `template/warroom_setup/setup.py::patch_war_room_block(profile_root, board, min_confidence=75, gate_action="abstain", enforce=True, show_confidence_badge=True)` — installer drives this via `run_setup(answers=...)` post-install; no direct call.
- `template/warroom_setup/setup.py::write_env` — called by `write_env_conditional` with a filtered dict.
- `template/warroom_setup/setup.py::seed_overlay` — invoked transparently through `run_setup`.
- `template/warroom_setup/setup.py::run_setup` — extended (additive kwargs) to accept pre-collected `answers`.
- `template/warroom_setup/selectables.py::TOGGLES`, `TEXT_FIELDS`, `build_stages`, `default_ids` — reference data; `INSTALLER_STAGES` is additive in the same module for symmetry.
- `template/warroom_setup/cli.py` argparse scaffold — add subcommand, reuse existing parser shape.
- Sentinel-managed block pattern (`_WR_BEGIN` / `_WR_END`) from `setup.py` — already idempotent; installer benefits automatically by routing through `run_setup`.

## 9. Dependencies

- **Blocked by:** none from A/C. Installer is self-contained orchestration over already-shipped primitives.
- **Blocks:** none directly, but **Feature A (warroom.enroll real implementation)** if it adds a `setup.py::join_mailbox(...)` helper, the installer should call it as a 5th post-install phase. Plan should add a hook point (`_post_setup_hook` callable in answers dict) so A and B can ship in either order without churn.
- **Shares code with:**
  - **Feature A** — shares `setup.py::write_env` and the answers-dict shape (board name flows through both).
  - **Feature C** — if C introduces validation utilities (e.g. agent-name regex, board-name regex), installer should import from there rather than duplicate. Coordinate on a `template/warroom_setup/validators.py` module owned by whichever ships first.

## 10. Estimated Effort

**L (Large).** Three new modules (~600 LoC), one modified module with backwards-compat contract, ~15 tests across 3 files, two inline walkthroughs that each need careful step-by-step copy plus skip/resume affordances, subprocess orchestration across two external CLIs (`hermes profile install`, `hermes plugins enable`) with failure recovery, and a resume-safe state machine. The TUI substrate is reused (saves ~200 LoC), but the walkthrough content writing + end-to-end dry-run test harness is the bulk of the work. Estimate 2-3 focused days including review iteration.

---

## Plan C — Cross-Agent Runtime Proof

Now I have a complete picture. Let me write the plan.

---

# Feature C — Cross-agent war-room runtime proof — Implementation Plan

## 1. Goal

Flip the `warroom.enroll` stub into reality: a fresh war-room-agent profile that runs `warroom setup` actually joins a shared mailbox board on first session, sees co-located peers via `mailbox ps`, sends/receives `mailbox` messages, and claims/releases lanes — verified end-to-end by a two-profile integration test where aria-sh and aahil-sh meet on board `default` and exchange a message + a lane claim.

## 2. Scope

In scope:
- Wire `warroom.enroll` from "writes `war_room.board` into config" to "actually causes the running agent's session to join that mailbox board".
- Discovery + invocation of the installed `mailbox` CLI from inside a Hermes profile process (resolve `~/.claude/mailbox/mailbox` or the dev `coordination/bin/mailbox` fallback).
- A first-run-only "ensure mailbox installed" path: warn-and-skip if the mailbox daemon isn't installed (template ships standalone; mailbox is a separate package).
- A `MAILBOX_BOARD` export at first-run so the existing mailbox `SessionStart` hook joins the right board on each subsequent Claude session.
- A new `warroom enroll` CLI subcommand (idempotent runtime join, callable from `first_run.sh` and ad-hoc by user/agent).
- A `/warroom` skill upgrade — promote `template/skills/warroom/SKILL.md` from no-op placeholder to a real skill with: presence check, lane claim/release, send/inbox helpers (thin wrappers around `mailbox` CLI).
- A two-profile scripted integration test (`test_runtime_two_profiles.py`) that boots a mailbox daemon on a temp socket, simulates aahil-sh and aria-sh joining the same board, exchanges a message, claims a lane.
- Failure-mode handling: mailbox not installed, daemon unreachable, socket mismatch, board name mismatch. All fail-warn (never fail-closed) on the template side.

Out of scope:
- Modifying mailbox itself (engine, daemon, hook contract). All work goes through the existing client/CLI surface.
- Hermes runtime changes (gateway, persona).
- Cross-machine coordination (mailbox is local-only by design).
- Auto-installing the mailbox package from the template (we document the prerequisite; we do not vendor or symlink-install).

## 3. File paths to create + modify

**Create (under `template/`):**
- `template/warroom_setup/enroll.py` — runtime mailbox bridge (discovery, join, env export, status).
- `template/warroom_setup/mailbox_client.py` — thin in-process client that prefers `coordination.mailbox.client` (if importable) and falls back to subprocess-invoking `mailbox` CLI; one place to centralize socket/board/session resolution.
- `template/skills/warroom/SKILL.md` — REWRITE from no-op to active skill (claim lane, send, inbox, ps, release).
- `template/skills/warroom/lib/warroom_ops.sh` — bash helper sourced by the skill (small, idiomatic mailbox CLI invocations with safe defaults: `--board`, label fallback).
- `template/tests/test_enroll.py` — unit tests for discovery / first-run wiring / env export.
- `template/tests/test_mailbox_client.py` — unit tests for the in-process client (mocked subprocess + mocked import path).
- `template/tests/test_runtime_two_profiles.py` — INTEGRATION test (spawns real daemon on temp socket, simulates two sessions).
- `template/tests/fixtures/fake_mailbox_cli.py` — stdlib-only fake CLI used by unit tests that don't need a real daemon.

**Modify (under `template/`):**
- `template/warroom_setup/cli.py` — add `enroll` subcommand (and `enroll --status`).
- `template/warroom_setup/setup.py` — call `enroll.bootstrap(...)` from `run_setup` when `warroom.enroll` is selected, after `patch_war_room_block` writes the config block; record `mailbox_installed: true|false` in the answers file.
- `template/warroom_setup/selectables.py` — add `TextField(id="warroom.label", prompt="War-room label (defaults to handle)", required=False, enable_if="warroom.enroll")`.
- `template/hooks/first_run.sh` — append a `warroom enroll --board <board> --label <handle>` invocation after `warroom setup --yes`, fail-warn on missing mailbox.
- `template/config.yaml` — extend the `# >>> warroom-managed` block with a `mailbox:` subsection (socket override, home override — both optional, default null).
- `template/warroom_setup/setup.py` — extend `patch_war_room_block` signature to take `mailbox_home=None, mailbox_socket=None, label=None` and serialize them inside the sentinel block.

**Read-only references (no edits — separate package):**
- `coordination/bin/mailbox`, `coordination/src/mailbox/{cli,client,config,engine}.py` — surface we wrap.
- `coordination/hooks/session_start.py` — the hook that reads `MAILBOX_BOARD` and joins; we do NOT touch it, we just set the env right.

## 4. Function signatures + 1-line responsibility per function

**`template/warroom_setup/enroll.py`:**

- `discover_mailbox_cli() -> Optional[Path]` — return the absolute path of the installed `mailbox` shim, preferring `$MAILBOX_HOME/mailbox`, then `~/.claude/mailbox/mailbox`, then `coordination/bin/mailbox` resolved relative to template repo (dev fallback), then `shutil.which("mailbox")`; `None` if none found.
- `mailbox_is_reachable(cli_path: Path, timeout_s: float = 2.0) -> Tuple[bool, str]` — invoke `<cli> whoami` and return `(ok, diagnostic)`; daemon auto-spawn is the client's job, we just observe.
- `resolve_session_id(env: Mapping[str, str]) -> Optional[str]` — read `MAILBOX_SESSION_ID` from env (set by mailbox's own `SessionStart` hook into `CLAUDE_ENV_FILE`); return None if not set (first_run is not inside a Claude session).
- `bootstrap(profile_root: Path, board: str, label: str, *, dry_run: bool=False) -> EnrollResult` — orchestrates: discover CLI, write/refresh `local/warroom-enroll.json` state file (board, label, cli_path, last_check_ts, status), and write `local/mailbox.env` (one `export MAILBOX_BOARD=...` + `export MAILBOX_LABEL=...` line each) consumed by the gateway's session bootstrap.
- `join_now(cli_path: Path, board: str, label: str, session_id: str) -> EnrollResult` — invoke `mailbox --session <sid> join --board <board> --label <label>`; parse stdout/exit; return structured result.
- `enroll_status(profile_root: Path) -> dict` — read state file + `mailbox ps` snapshot if reachable; return a dict suitable for human print and json output.
- `_atomic_write_json(path: Path, obj: dict) -> None` — same pattern as `setup.write_env` / mailbox's `store.atomic_write_json`; temp + `os.replace`.
- `EnrollResult` dataclass: `ok: bool`, `reason: str`, `cli_path: Optional[str]`, `board: Optional[str]`, `boards_joined: list`, `co_located: dict`.

**`template/warroom_setup/mailbox_client.py`:**

- `MailboxBridge.__init__(self, profile_root: Path, env: Mapping[str, str] = os.environ)` — capture config (board, label, socket, home overrides from `config.yaml`'s warroom block + `local/mailbox.env`).
- `MailboxBridge.is_available(self) -> bool` — discovery wrapper; sets `self.cli_path` / `self.import_path`.
- `MailboxBridge.call(self, op: str, args: dict, *, timeout_s: float = 5.0) -> dict` — prefers in-process `from mailbox import client; client.request(op, args)` if `coordination/src` is on sys.path (dev mode); else subprocess-invokes the CLI and parses output. Returns `{"ok": bool, "data": ..., "error": ...}`.
- `MailboxBridge.join(self, board: str, label: str) -> dict` — wraps `call("join", {...})`.
- `MailboxBridge.send(self, body: str, to: str = "*", kind: str = "note") -> dict`.
- `MailboxBridge.inbox(self) -> list`.
- `MailboxBridge.ps(self) -> list`.
- `MailboxBridge.claim_lane(self, lane: str, note: Optional[str] = None) -> dict` — uses the engine's `claim_lane` op via the daemon (not exposed in CLI today — flagged in Risk #2; current CLI fallback claims `lane://<id>` directly via `mailbox claim`).
- `MailboxBridge.release_lane(self, lane: str) -> dict`.

**`template/warroom_setup/cli.py` (new subcommand):**

- `cmd_enroll(args, in_stream, out_stream) -> int` — args: `--board`, `--label`, `--status` (read-only), `--dry-run`, `--profile-root` (defaults to script's repo root). Routes to `enroll.bootstrap` or `enroll.enroll_status`.

**`template/warroom_setup/setup.py` (modified):**

- `patch_war_room_block(profile_root, board, min_confidence=75, gate_action="abstain", enforce=False, show_confidence_badge=True, label=None, mailbox_home=None, mailbox_socket=None)` — new optional kwargs serialized inside the sentinel-managed block.

## 5. TUI / UX flow

### A. First-time `warroom setup` (interactive)

1. User runs `warroom setup` (wizard).
2. Toggle stage `WarRoom` shows two toggles (`warroom.enroll` default ON, `warroom.enforce` default ON) — unchanged.
3. After toggles, text prompt: `War-room board name [default]:` — user types `default` or presses Enter.
4. Text prompt: `War-room label (defaults to <handle>):` — NEW. Enter accepts default.
5. Text prompt: `War-room min confidence % [75]:` — unchanged.
6. Setup writes `config.yaml` block + `.env` + `local/answers.json` as today.
7. NEW: `enroll.bootstrap(...)` runs:
   - Discovers `mailbox` CLI.
   - Writes `local/warroom-enroll.json` (state).
   - Writes `local/mailbox.env` with `export MAILBOX_BOARD=<board>` and `export MAILBOX_LABEL=<label>`.
   - Prints one of:
     - OK: `war-room: enrolled on board "default" as label "aria-sh" (mailbox at ~/.claude/mailbox)`.
     - Skipped: `war-room: mailbox CLI not found; install it from <repo url>, then run `warroom enroll`. War-room features will no-op until installed.`
8. Final summary line unchanged.

### B. First Claude session — the actual join

1. `first_run.sh` fires (sentinel-guarded, runs once per profile).
2. Runs `warroom setup --yes` (headless). For an unconfigured profile this writes defaults.
3. NEW: `warroom enroll --board <board> --label <handle>` runs. If mailbox CLI absent → prints warning to `local/setup.log`, exits 0 (fail-warn).
4. Gateway later sources `local/mailbox.env` into the Claude Code subprocess environment. (See Risk #4.)
5. Claude Code's `SessionStart` hook (the mailbox-owned one in `~/.claude/mailbox/hooks/session_start.py`) sees `MAILBOX_BOARD`, calls `client.request("join", ...)`. The mailbox daemon auto-spawns if down. Co-location notice fires if a peer is live.
6. On `PostToolUse` / `UserPromptSubmit`, mailbox's existing hooks heartbeat + poll inbox; peer messages arrive as `additionalContext` injected into the model.

### C. Two-profile proof-point flow (the hero scenario, end-user view)

1. User installs the war-room-agent template via `hermes profile install ./template --handle aahil-sh`.
2. User runs `warroom setup` (or accepts first_run defaults). Board = `default`.
3. User installs a second profile: `hermes profile install ./template --handle aria-sh`.
4. User runs `warroom setup` for aria. Board = `default`.
5. User opens two Claude Code sessions, one per profile.
6. aria's session bootstraps; mailbox `SessionStart` joins board `default`; sees aahil already there; emits co-location note → injected into aria's model context: `aahil-sh joined board — 2 now active; coordinate via mailbox`.
7. aria runs `mailbox send --to aahil-sh "hello from aria"`.
8. aahil's next `PostToolUse`/`UserPromptSubmit` polls inbox; mailbox hook injects `[note] from aria-sh: hello from aria` as additionalContext.
9. aahil runs `mailbox claim '/Users/.../warroom-demo/src/auth/**' --note "auth refactor"`. aria runs `mailbox ps` and sees aahil-sh active + their claim via `mailbox claims --all`.
10. aahil edits a file in `src/auth/` (allowed). aria attempts to Edit a file in `src/auth/` → mailbox `PreToolUse` denies with reason `auth refactor (aahil-sh, 2s ago)`.
11. aahil runs `mailbox release all`; aria's next Edit is allowed.

### D. Ad-hoc `warroom enroll --status`

1. User runs `warroom enroll --status` from anywhere inside a profile.
2. Output:
   ```
   board:         default
   label:         aria-sh
   mailbox cli:   /Users/.../.claude/mailbox/mailbox
   daemon:        reachable (whoami: aria-sh-9f0a)
   board peers:   aahil-sh (active, 3s ago), aria-sh (active, 0s ago)
   ```
3. If mailbox not installed: `mailbox cli: NOT FOUND. War-room features are inactive. Install mailbox: <link>`.

## 6. Test strategy

### `template/tests/test_enroll.py` (unit)
- `test_discover_mailbox_cli_prefers_mailbox_home_env(monkeypatch, tmp_path)` — set `MAILBOX_HOME`, drop a fake `mailbox` executable, assert it's chosen.
- `test_discover_mailbox_cli_falls_back_to_claude_default(monkeypatch, tmp_path)` — unset `MAILBOX_HOME`, fake `~/.claude/mailbox/mailbox`, assert chosen.
- `test_discover_mailbox_cli_returns_none_when_absent(monkeypatch, tmp_path)` — empty PATH, no `MAILBOX_HOME`, no `~/.claude/mailbox`, assert None and no exception.
- `test_bootstrap_writes_local_mailbox_env(tmp_path)` — exports `MAILBOX_BOARD=...` line, 0600 perms.
- `test_bootstrap_writes_warroom_enroll_json_atomically(tmp_path)` — file appears in one `os.replace` step (assert no `.tmp` leftover, use `glob`).
- `test_bootstrap_is_idempotent(tmp_path)` — call twice, content stable byte-for-byte except `last_check_ts`.
- `test_bootstrap_skipped_when_cli_missing(tmp_path)` — returns `EnrollResult(ok=False, reason="mailbox-cli-not-found")`, still writes state file recording the miss.
- `test_resolve_session_id_reads_env`.
- `test_join_now_invokes_cli_with_correct_args(tmp_path, monkeypatch)` — fake CLI as a stdlib python script in `fixtures/fake_mailbox_cli.py` that records argv to a file; assert argv matches.

### `template/tests/test_mailbox_client.py` (unit)
- `test_call_subprocess_path_parses_data(tmp_path)` — fake CLI emits `{"ok":true,"data":{...}}`; assert bridge returns parsed dict.
- `test_call_subprocess_path_timeout(monkeypatch)` — fake CLI sleeps; assert bridge returns `{"ok":False,"error":"timeout"}` after 5s (use short timeout in test).
- `test_call_in_process_when_coordination_importable(monkeypatch)` — monkeypatch a fake `mailbox.client.request` and assert it's used instead of subprocess.
- `test_send_inbox_claim_lane_each_call_correct_op(monkeypatch)` — parametrize over ops.

### `template/tests/test_cli.py` (extend)
- `test_cli_enroll_invokes_bootstrap(monkeypatch)` — `warroom_setup enroll --board foo --dry-run` calls `enroll.bootstrap(..., dry_run=True)`.
- `test_cli_enroll_status_prints_json_when_flag(monkeypatch)`.

### `template/tests/test_setup.py` (extend)
- `test_run_setup_calls_enroll_bootstrap_when_toggle_on(monkeypatch, tmp_path)` — monkeypatch `enroll.bootstrap`, assert called with `(profile_root, "default", expected_label)`.
- `test_run_setup_skips_enroll_when_toggle_off(monkeypatch, tmp_path)`.
- `test_patch_war_room_block_serializes_mailbox_subkeys(tmp_path)` — assert `mailbox:` lines appear inside sentinel block.

### `template/tests/test_runtime_two_profiles.py` (INTEGRATION — load-bearing)
Bootstraps a real mailbox daemon on a temp socket inside `tmp_path` (re-uses `coordination/tests/conftest.py` pattern: set `MAILBOX_HOME=tmp/home`). Then:
1. Builds two fake profiles via the same `_fake_profile` helper used in `test_setup.py`, customized with distinct handles `aahil` / `aria`.
2. Runs `warroom setup --yes` for each (using distinct synthetic `MAILBOX_SESSION_ID`s in env).
3. Calls the bridge's `join("default", "aahil-sh")` and `join("default", "aria-sh")` (impersonates the mailbox `SessionStart` hook by setting session ids directly).
4. Asserts `bridge_a.ps()` returns rows including `aria-sh`, and vice versa.
5. Calls `bridge_b.send("hello")` to `aahil-sh`.
6. Asserts `bridge_a.inbox()` contains a `note` from `aria-sh` with body `hello`, and subsequent inbox is empty (read-once).
7. Calls `bridge_a.claim_lane("auth")`; asserts `bridge_b.claim_lane("auth")` returns `decision: deny`.
8. Calls `bridge_a.release_lane("auth")`; asserts `bridge_b.claim_lane("auth")` returns `decision: allow`.
9. SKIP-marked with `pytest.importorskip("mailbox")` so this test only runs in environments where the coordination/ package is importable (CI installs both; pure-template installs may not).

Marker: `pytest.mark.integration` so it can be selectively skipped on slow machines.

### `template/tests/fixtures/fake_mailbox_cli.py`
A minimal stdlib script that:
- Reads argv.
- Echoes `{"ok": true, "data": {...}}` to stdout in mailbox's response format.
- Records argv to `$FAKE_MAILBOX_ARGV_LOG` env file if set.

## 7. Risks / unknowns

1. **Session ID provenance.** Mailbox's `SessionStart` hook expects Claude Code to set `session_id` on stdin (Claude harness contract). When the template's `first_run.sh` invokes `warroom enroll` outside a Claude session (it runs from gateway bootstrap, not from a Claude session), there is no `MAILBOX_SESSION_ID` yet — the mailbox `SessionStart` hasn't fired. So **the first_run-time `enroll` cannot actually perform a `mailbox join`**; it can only write `local/mailbox.env` which a SUBSEQUENT Claude session sources. Verify: does Hermes gateway source `local/mailbox.env` before launching Claude? If NO, we need a second mechanism — either patch Hermes (out of scope) or use mailbox's own `SessionStart` hook from inside Claude (which requires `MAILBOX_BOARD` to be present in Claude's env, which means we must export it from the gateway). **Critical to verify before writing code** — read Hermes gateway env loading first, otherwise the entire wiring is decorative.

2. **No CLI op for `claim_lane`.** The engine has `claim_lane`/`release_lane`/`list_lanes` methods, but `coordination/src/mailbox/cli.py` exposes only `claim`/`release`/`seize` (file-glob territory). The lane abstraction is reachable via in-process import (`client.request("claim_lane", {...})`) but NOT via the shim CLI. **We have two options**: (a) require dev-import (only works when `coordination/src` is on sys.path), or (b) extend `coordination/src/mailbox/cli.py` with `claim-lane`/`release-lane`/`list-lanes` subcommands (touches the other package). The plan currently picks (a) for the in-process bridge, with a CLI fallback that uses `mailbox claim lane://<id>` (since the engine stores lanes as `lane://` URIs and `mailbox claim` accepts arbitrary path strings). Need to confirm `mailbox claim lane://auth` actually round-trips through the daemon — it should per engine code, since `path_matches` exact-matches non-glob strings. Risk: the daemon may abspath the argument and turn `lane://auth` into `/cwd/lane:/auth`.

3. **CLI abspath rewrite of lane URIs.** Inspecting `cli.py:130`: `op_args["globs"] = [_abspath(g) for g in args.globs]`. `os.path.abspath("lane://auth")` becomes `/cwd/lane:/auth` — which breaks the lane prefix matching in engine (`_LANE_PREFIX = "lane://"`). **CLI fallback for lane claim is broken today.** Either (a) extend mailbox CLI (small patch to that package), or (b) make the bridge always go in-process for lane ops and fail loud if `coordination/src` isn't importable. Plan picks (b) and documents (a) as the recommended cross-cutting fix.

4. **`MAILBOX_BOARD` reaching the Claude subprocess.** Mailbox's `SessionStart` hook reads `os.environ["MAILBOX_BOARD"]` to decide which named board to join. We write `local/mailbox.env`, but Hermes gateway must source that into Claude Code's env. If it doesn't, the `SessionStart` hook joins only the auto-repo-board (a `repo-<hash>` derived from `cwd`), and the two profiles will land on DIFFERENT boards (since their cwd's differ). We need to verify Hermes gateway behavior — likely we have to add a `gateway.env` patch via `patch_war_room_block` that writes the env into a Hermes-readable location. **Read aahil-sh's existing gateway config to see how it loads `.env` and whether a non-`.env` file is honored.**

5. **`whoami` requires presence.** `mailbox whoami` returns `{"exists": false}` until a `join` happens for that session_id. So `enroll --status` from outside a Claude session will look like "not joined" even if everything is wired correctly. Need to distinguish "no MAILBOX_SESSION_ID yet" (fine, hasn't started a Claude session) from "joined but daemon doesn't know me" (broken). Plan: `enroll --status` falls back to printing `mailbox ps` (which doesn't require a specific session_id to be joined — wait, it does: it returns `[]` if `me is None`). May need to add a `--probe` mode that just `ping`s the daemon socket directly without requiring presence.

6. **Mailbox daemon auto-spawn cwd assumption.** `client.ensure_running()` spawns the daemon with cwd = `CLAUDE_PROJECT_DIR` or `MAILBOX_HOME`. If first_run runs before Hermes sets that, the daemon may inherit an unexpected cwd, affecting log path discovery. Probably benign (state dir is computed from env, not cwd) but worth verifying with the integration test.

7. **Mailbox not installed at all.** The template SHOULD work as a standalone Hermes profile even with no mailbox installed (the gate, persona, channels all still function). All enroll code paths must fail-warn, never fail-closed. Verify by running `test_runtime_two_profiles.py` skip-path with mailbox uninstalled.

8. **Discord/Slack mention races.** If both aahil-sh and aria-sh subscribe to the same Discord channel + same board, who replies? Mailbox doesn't gate channel replies — that's Hermes' job. Out of scope for this plan but worth flagging for the integration demo: pick a channel where only one agent listens, or use `require_mention` to disambiguate.

9. **Label collisions.** Two profiles installed on the same machine both defaulting label to `agent_name`. If both pick `warroom`, mailbox sees two sessions with label `warroom` — `mailbox send --to warroom` is ambiguous. The wizard should default `warroom.label` to `handle` (which IS guaranteed unique per Hermes profile), not `agent_name`. The new TextField above does this.

## 8. Existing code to reuse

- `template/warroom_setup/setup.py::patch_war_room_block` — extend (not replace) to serialize mailbox-specific subkeys inside the existing sentinel block. Sentinel pattern + idempotency comes free.
- `template/warroom_setup/setup.py::write_env` — atomic-write env-file pattern; mirror it for `local/mailbox.env` (or just call it with a different filename — refactor to accept `filename=".env"` kwarg).
- `template/warroom_setup/setup.py::_secure_file` — chmod 0600 on the state file (mailbox env exposes only a board name, low-risk, but keep consistent).
- `template/warroom_setup/cli.py` — argparse skeleton + subcommand dispatch idiom.
- `template/warroom_setup/answers.py::Answers.save/load` — for round-tripping `mailbox_installed` / `enroll_status` into `local/answers.json`.
- `template/warroom_setup/render.py::_is_tty` — TTY detection for picking interactive vs replay enroll behavior.
- `coordination/src/mailbox/client.py::request` — when importable, use directly (skip subprocess entirely).
- `coordination/src/mailbox/client.py::ensure_running` — the daemon auto-spawn we get for free.
- `coordination/src/mailbox/config.py::socket_path / home` — for diagnostic printing in `enroll --status`.
- `coordination/hooks/session_start.py` — DO NOT TOUCH; treat as the contract. We just feed it the right env (`MAILBOX_BOARD`, `MAILBOX_LABEL`).
- `coordination/tests/conftest.py` — fixture pattern for booting a daemon on a temp socket via `MAILBOX_HOME` env; cargo-cult into `test_runtime_two_profiles.py`.
- `coordination/docs/handoff-extension.md` — already documents the exact `MAILBOX_BOARD` + `mailbox join` + `mailbox claim` + `mailbox ps` workflow. Re-use as the canonical sequence in the new `SKILL.md`.

## 9. Dependencies

- **Blocked by:** Nothing strictly. Feature C can land before A and B. BUT — Risk #1 (gateway env propagation) may require a small Hermes change or a documented workaround; if that workaround takes the form of "edit a Hermes config block", then the sentinel-managed config-block writer reused from A is the right tool.
- **Blocks:** The truthful claim that "this template ships a war-room agent" — until C lands, A (wizard) and B (Discord walkthrough) are decorative as you said.
- **Shares code with:**
  - **A (wizard)**: `selectables.py` (new `warroom.label` TextField), `setup.py::patch_war_room_block` (new mailbox subkeys), `cli.py` (new `enroll` subcommand). All three are touched by both A and C — coordinate ordering or merge order.
  - **B (Discord walkthrough)**: shares the integration-demo narrative ("two installed agents talking via Discord"). C provides the mailbox layer underneath B's user-visible Discord chat. The two-profile integration test (C) and the Discord smoke test (B) should be runnable independently but compose.
  - **Confidence gate** (already shipped): `mailbox send` payloads from this skill must respect the gate (the `transform_llm_output` plugin hook will see them). Worth confirming in the integration test: a gated send-suppression path doesn't break the proof.

## 10. Estimated effort

**L (large).** 

Reason: The wiring code itself is modest (~400-600 LoC across `enroll.py`, `mailbox_client.py`, modified `cli.py`/`setup.py`, and the new SKILL.md/`warroom_ops.sh`). What pushes it to L is the **runtime integration test** (`test_runtime_two_profiles.py`) — it has to boot a real daemon, simulate two distinct sessions cleanly, manage temp sockets, and exercise the deny-on-conflict path end-to-end without flakes. Plus the four high-confidence risks (1, 2, 3, 4) each require empirical verification against the live mailbox package + a Hermes profile before the design is even locked. Realistic budget: 1-2 days of investigation (Risks 1 + 4 are the big ones — answer them first), then 2-3 days of TDD implementation, then 1 day of integration-test stabilization.
