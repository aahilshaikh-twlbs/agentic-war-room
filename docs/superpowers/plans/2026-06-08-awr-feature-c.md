# AWR Feature C — Cross-Agent Runtime: Implementation Plan

Date: 2026-06-08. Status: planning complete, ready to build. Final plan below; adversarial reviews preserved for audit.

---

## Final plan (post-refutation, ready to execute)

# Feature C — Cross-Agent Runtime: FINAL Implementation Plan (post-adversarial-review)

Date: 2026-06-08. Branch: builds on `awr-shared-core` (PR #2). Status: ready to dispatch.

---

## 0. Changes from base plan after adversarial review

The base plan had three load-bearing assumptions that collapse under review. All three are fixed below. The plan now begins with **mandatory pre-flight T0** that empirically resolves the runtime/hook taxonomy BEFORE any production code is written.

**BLOCKERS taken (and the fix):**

- **Correctness #1 / Completeness #1 / Feasibility F1+F4** — *Hermes gateway hooks vs. Claude Code harness hooks are different process lifecycles in different processes.* The base plan conflated them. **Fix:** New task **T0** runs three empirical pre-flights and locks the runtime taxonomy. New task **T0.5** rewires `template/config.yaml`'s `hooks:` block to the Hermes-correct list-of-mappings shape. The template's `session_start.py` (T3) is now installed into `~/.claude/settings.json` as a Claude Code harness hook, NOT into Hermes config.yaml. T3 is materially rewritten.
- **Completeness #2 / Feasibility F1** — *Current `template/config.yaml`'s `hooks.on_session_start: bash hooks/first_run.sh` (scalar) is silently warn-skipped by Hermes; first_run.sh never fires today.* **Fix:** T0.5 migrates to the correct list-of-mappings form with absolute command paths; T0.5 includes a regression test asserting `iter_configured_hooks` returns a non-empty list.
- **Feasibility F2** — *`state.save_state` does not exist in shared core.* **Fix:** New task **T1.5** implements `state.save_state` modeled on `setup._secure_file`'s chmod-after-rename pattern. T2 uses it.
- **Feasibility F5** — *`CLAUDE_ENV_FILE` write visibility between Claude Code hooks is unverified and load-bearing.* **Fix:** T0 pre-flight #3 runs a 60-second empirical check. If env_file writes are NOT visible to subsequent hooks via `os.environ`, T3 falls back to "template hook writes a sidecar file in `<profile>/local/runtime_env.json`; we patch mailbox's hook (via PR upstream OR via a wrapper script) to read it." T0's outcome strictly determines T3's shape.
- **Correctness #3 / Completeness #3** — *T8 only proved the daemon API, not the integration path.* **Fix:** T8 split into T8a (in-process engine test for protocol envelope) and **T8b** (end-to-end: invoke template `session_start.py` with fixture config.yaml; exec mailbox's `session_start.py` with stdin payload; assert captured `client.request` carries `board_name="shared"`).
- **Correctness #20 / Feasibility F8** — *Lock-sidecar dance in F4 is over-engineered.* **Fix:** Removed. T1.5's `state.save_state` uses `tempfile + os.chmod + os.replace` (mirroring `setup._secure_file`). Last-writer-wins is the documented behavior.

**MAJORS taken:**

- **Completeness #5 / Feasibility F9** — *`warroom_ops.sh` is dead code (subshell scope) and the frontmatter `metadata.hermes.tags` field is fictional.* **Fix:** T6 DROPS `warroom_ops.sh` entirely. T6 also drops the `metadata.hermes.tags` frontmatter; the frontmatter test is replaced with a real check (`name` and `description` present, ≤500 chars description). The SKILL.md verb list is the canonical interface.
- **Completeness #6** — *`enroll_status` daemon-reachable check is described only in Risks, not Tasks.* **Fix:** T5 spec now EXPLICITLY requires stdlib-only `socket.socket(AF_UNIX) + connect` with 1.0s timeout, no `mailbox.client` import, never auto-spawn.
- **Completeness #7** — *No atomic write for `patch_mailbox_block`; SIGTERM mid-write corrupts config.yaml.* **Fix:** T2 now specifies `tempfile.NamedTemporaryFile(dir=path.parent) + os.replace` for ALL config.yaml writes (mailbox AND warroom block). Test added.
- **Completeness #8** — *README doesn't tell user how to install mailbox when `cli-not-found`.* **Fix:** T9 README adds "Installing the mailbox runtime" subsection: `python3 coordination/install.py`, MAILBOX_HOME override, expected symlink layout.
- **Completeness #9** — *No log file for cross-agent debugging.* **Fix:** T4 now writes `<profile>/local/warroom-enroll.log` on every bootstrap; T9 README adds the diagnostic recipe (`cat log → cat state.json → mailbox ps`).
- **Completeness #10 / Feasibility F11** — *No sanitization rule for `mailbox.label`; AND the plan text uses `aahil-sh`, a real handle with TwelveLabs skills loaded.* **Fix:** All plan/test/README text uses neutral placeholders `alpha-sh` and `beta-sh`. T9 adds a sanitize_check test against a fixture with a "real-looking" label; the shipped template's `mailbox:` block has `label: ""` (populated only in `<profile>/`, never in `template/`).
- **Completeness #13** — *Two board fields (`war_room.board` vs `mailbox.board`) with undefined relationship.* **Fix:** Locked in §1: wizard writes the SAME value to both; `mailbox.board` is the source of truth for cross-agent routing; `war_room.board` continues to scope the confidence gate. T2 writes both atomically. T5's `--board` override updates BOTH blocks.
- **Completeness #14** — *Persona never taught to use mailbox verbs ambiently.* **Fix:** New task **T6.5** calls `patch_persona_decisions` from `run_setup` to inject one rule: "Before editing a file a board peer may also be editing, run `mailbox claim-lane <lane>` first."
- **Completeness #15** — *warroom-gate plugin's relationship to `mailbox.board` is undeclared.* **Fix:** §1 now states: warroom-gate plugin is unchanged; reads `war_room.board` only. The wizard writes the same value to both fields for consistency.
- **Feasibility F3** — *T8's `client.request` returns `{"ok": True, "data": ...}`; base plan unwrap was wrong.* **Fix:** T8a uses **in-process `MailboxEngine`** directly (no protocol envelope). T8b uses the protocol path and explicitly unwraps `resp["data"]`.
- **Feasibility F6** — *T8 must explicitly pass `board_name="shared"` on every join; T3 must fail-closed when `mailbox.board` is empty.* **Fix:** Spec'd in T8a and T3.
- **Feasibility F7** — *Daemon-under-pytest is not reaped by `leave`.* **Fix:** T8b fixture spec'd to (a) set `MAILBOX_HOME` + `MAILBOX_SOCKET` env before any mailbox import, (b) read pidfile + `os.kill(pid, SIGTERM)` on teardown, (c) wait for socket file removal with timeout.
- **Feasibility F10** — *Adding `warroom.label` between existing fields silently reorders the wizard.* **Fix:** `warroom.label` is appended AFTER `warroom.min_confidence`.
- **Feasibility F12** — *Multiple coexisting sentinel blocks in one config.yaml: string-split is fragile.* **Fix:** T2.5 added: switch sentinel-replace logic to anchored regex (`^# >>> warroom-mailbox >>>$ ... ^# <<< warroom-mailbox <<<$` with `re.MULTILINE | re.DOTALL`). Hardens both `patch_war_room_block` and `patch_mailbox_block`.
- **Feasibility F15** — *Internal contradiction: §2 says we DO export MAILBOX_HOME; F8 says we don't.* **Fix:** Locked: we export `MAILBOX_HOME` ONLY when config value is non-empty AND differs from the default `~/.claude/mailbox`. Same rule for `MAILBOX_SOCKET`.
- **Feasibility F16** — *`pytest.importorskip("mailbox")` collides with stdlib `mailbox`.* **Fix:** Use `importlib.util.find_spec("mailbox.client")` and a try/except on `mailbox.engine`/`mailbox.client` symbols.

**MINORS rejected with reason:**

- **Correctness's "lock-sidecar gold-plating"** — accepted (see above; removed).
- **Completeness #11 ("--status exit codes")** — accepted; added to T5.
- **Completeness #12 ("T7 dead code under sentinel guard")** — accepted; **T7 removed entirely**. The single bootstrap call from `run_setup` (T4) is sufficient. The "manual `warroom setup` re-fire" use case is served by `warroom enroll --reconfigure` (new flag in T5 that bypasses the no-op-if-unchanged guard).
- **Completeness #4 ("test config drift / label change")** — accepted; added to T2 test list.
- **Feasibility F13 ("dev fallback only applies in checkout")** — accepted; documented in T1.
- **Feasibility F14 ("env-vs-config diff warning fires spuriously")** — accepted; dropped from F2 mitigation. Only emit when `MAILBOX_SESSION_ID` is set.
- **Feasibility F17 ("re-rank pre-flights")** — accepted; pre-flights are now task **T0** (blocking) not §10 advisory.

**Out of scope (rejected with reason):**

- Patching mailbox's `session_start.py` upstream to read `<profile>/config.yaml` directly. Rejected: changes the mailbox package's surface; we keep it read-only per locked decision. If T0 pre-flight #3 fails, we use a wrapper-script approach in T3 (insert before mailbox in `~/.claude/settings.json`).
- New plugin entrypoint (`register()`) for warroom. Rejected: out of locked-decision scope; the SessionStart hook is sufficient.
- Multi-board / dynamic-board switching. Rejected: locked decision #1 picks one board per profile; out of scope for C.

---

## 1. Architecture summary

We flip `warroom.enroll` from "writes a config block, fires nothing" to "the next Claude session under this profile actually joins the named mailbox board and finds peers."

Five pieces fit together:

1. **`template/warroom_setup/enroll.py`** — owns mailbox CLI discovery + idempotent first-run wiring.
2. **`mailbox:` block in `<profile>/config.yaml`** (locked decision #1) — records `board / label / mailbox_home / socket_path`. This is the SOURCE OF TRUTH for cross-agent routing.
3. **`war_room:` block in `<profile>/config.yaml`** — unchanged in structure; the wizard writes the SAME `board` value to both blocks for consistency. The warroom-gate plugin (confidence gate) continues to read ONLY `war_room.board`; mailbox routing reads ONLY `mailbox.board`. They're decoupled but kept synced by the wizard.
4. **`template/hooks/session_start.py`** — a **Claude Code harness** hook (NOT a Hermes hook) installed into `~/.claude/settings.json` BEFORE mailbox's hook. It re-exports `MAILBOX_BOARD` / `MAILBOX_LABEL` (and conditional `MAILBOX_HOME` / `MAILBOX_SOCKET`) into `$CLAUDE_ENV_FILE` so mailbox's own SessionStart hook can read them via `os.environ`.
5. **`template/hooks/first_run.sh`** — a **Hermes gateway** hook (configured via list-of-mappings syntax) that runs once per profile to invoke `warroom setup --yes`, which calls `enroll.bootstrap`, which writes the `mailbox:` block AND installs the template's `session_start.py` into `~/.claude/settings.json`.

Existing code touched: `warroom_setup/cli.py`, `warroom_setup/setup.py`, `warroom_setup/selectables.py`, `warroom_setup/state.py` (new helper), `template/config.yaml` (hooks syntax migration), `template/skills/warroom/SKILL.md` (placeholder → real protocol), `template/persona/decisions.md` (one-line persona injection). The mailbox package itself remains read-only.

**Locked: warroom-gate plugin scope.** The confidence-gate plugin reads `war_room.board` for its scoping; it does NOT migrate to `mailbox.board`. The wizard writes both fields to the same value at setup time. Future divergence is operator-driven (manual edit).

---

## 2. Runtime sequence (end-to-end, first session — Hermes + Claude Code reconciled)

**Hermes gateway lifecycle (process A):**

1. **Operator** runs `hermes profile install ./template --handle alpha-sh -y --alias --force`. Hermes copies the template tree under `~/.hermes/profiles/alpha-sh/`.
2. **Operator** runs `hermes -p alpha-sh chat`. Hermes loads `<profile>/.env` via `load_hermes_dotenv` (Inv1) into `os.environ` of the gateway process.
3. **Gateway** parses `<profile>/config.yaml`'s `hooks.on_session_start` (list of mappings, post-T0.5) and fires `[{command: "bash <profile>/hooks/first_run.sh"}]` with `shell=False`. (T0 pre-flight #1 confirmed this is the only accepted shape.)
4. **first_run.sh** (sentinel-guarded by `local/.setup-done`) invokes `python3 -m warroom_setup setup --yes`.
5. **`run_setup`** writes the `_WR_BEGIN` warroom block AND (via T2.5's hardened sentinel patcher) the `# >>> warroom-mailbox >>>` block, both atomically. Then calls `enroll.bootstrap(profile_root, board, label)`.
6. **`enroll.bootstrap`** discovers the mailbox CLI (precedence: `MAILBOX_HOME` env → `~/.claude/mailbox/mailbox` → `<repo>/coordination/bin/mailbox` dev fallback (checkout-only) → `shutil.which`). Writes `<profile>/local/warroom-enroll.json` atomically (via `state.save_state` from T1.5) with mode 0600. Writes `<profile>/local/warroom-enroll.log` with a timestamped status line. If CLI found, also installs `<profile>/hooks/session_start.py` into `~/.claude/settings.json`'s `SessionStart` hook list at position 0 (BEFORE mailbox's entry), idempotently. If CLI not found, status records `cli-not-found`, log records the resolution failure, fail-warn (exit 0).
7. **first_run.sh** marks sentinel and exits.
8. **Gateway** continues to launch the Claude Code harness subprocess for the chat session.

**Claude Code harness lifecycle (process B):**

9. **Claude harness `SessionStart` event** fires the registered hooks in order from `~/.claude/settings.json`:
   - **(9a) Template `session_start.py`** (registered FIRST by T2's installer). Reads `<profile>/config.yaml`'s `mailbox:` block via regex-anchored sentinel extraction. Computes the export set: always `MAILBOX_BOARD=<board>`, `MAILBOX_LABEL=<label>`; conditionally `MAILBOX_HOME=<path>` ONLY if non-empty AND differs from default; same rule for `MAILBOX_SOCKET`. Writes these as `export KEY=VAL` lines to `$CLAUDE_ENV_FILE` (deduplicated against existing lines). Fail-OPEN on any error (exit 0, log to `<profile>/local/warroom-enroll.log`). **Fail-CLOSED only when `mailbox.board` is empty**: still exit 0, but log a structured warning so the operator notices.
   - **(9b) Mailbox's `~/.claude/mailbox/hooks/session_start.py`** runs second. Claude Code's harness has sourced `$CLAUDE_ENV_FILE` between hooks (T0 pre-flight #3 confirmed this). Reads `MAILBOX_BOARD` / `MAILBOX_LABEL` from `os.environ`. Reads stdin JSON `{session_id, cwd, ...}` from harness. Calls `client.request("join", {session_id, label, cwd, board_name: "default"})`. Daemon auto-spawns via `client.ensure_running` if down.

10. **`engine.join`** (engine.py:98) ensures both `repo-<hash>` board AND named board `default` exist. Adds session to both. Computes co-location. Emits a `note` to co-located peers ("alpha-sh joined board — 2 now active").

11. **Mailbox's `UserPromptSubmit` / `PostToolUse` hooks** (pre-installed) poll inbox + heartbeat. Peer messages arrive as `additionalContext`. From this moment, `mailbox ps`, `mailbox send --to beta-sh "..."`, `mailbox claim-lane auth`, `mailbox inbox`, `mailbox list-lanes` all work from any subshell because `MAILBOX_SESSION_ID` is written to `CLAUDE_ENV_FILE` by mailbox's hook.

**Hero claim:** two profiles with the same `mailbox.board` value land on the same named board, regardless of cwd, because step 9a forces a non-cwd-derived board name into the env that mailbox's hook (step 9b) reads.

---

## 3. Task breakdown

### T0 — Pre-flight: lock the runtime taxonomy (blocking; ~0 LoC; ~3 hours empirical work)

**Run three empirical checks. Document results in `template/docs/runtime-preflight.md`. T1+ cannot start until all three are resolved.**

1. **Hermes `hooks.<event>` accepted shape.** Confirmed by `~/.hermes/hermes-agent/agent/shell_hooks.py:242-285`: must be `list[dict]` with `command` key. Scalar/string forms are warn-skipped. **Action:** record this in `runtime-preflight.md`; T0.5 migrates.

2. **Claude Code harness hook ordering and registration mechanism.** Register two trivial `SessionStart` hooks in `~/.claude/settings.json` (one writing `# A` to a temp file, second writing `# B`). Confirm execution order matches registration order. Confirm template's hook can be inserted at index 0 idempotently.

3. **`CLAUDE_ENV_FILE` write visibility between consecutive Claude Code hooks.** Hook A writes `export X=test1` to `$CLAUDE_ENV_FILE`. Hook B prints `os.environ.get("X")`. **Pass criterion:** stdout contains `test1`. **Fail outcome:** T3 architecture switches to writing a sidecar JSON at `<profile>/local/runtime_env.json` and installing a wrapper script that sources it before exec'ing mailbox's hook (more invasive; documented contingency in T3).

**Acceptance:** `template/docs/runtime-preflight.md` exists, lists each pre-flight result, with the empirical command/output captured verbatim. All three resolved before any T-numbered task starts coding.

**Dependencies:** none.

---

### T0.5 — Migrate `template/config.yaml` hooks to Hermes-correct list-of-mappings (~20 LoC + 30 LoC tests)

**Modify:** `template/config.yaml`. Change `hooks:` block from `{on_session_start: bash hooks/first_run.sh}` (scalar; silently dropped today) to:

```yaml
hooks:
  on_session_start:
    - command: "bash {{PROFILE_ROOT}}/hooks/first_run.sh"
```

**Modify:** `template/warroom_setup/setup.py::install_template` (or wherever Hermes-install hands off to template post-copy; if Hermes doesn't do post-copy substitution, then **first_run.sh** must self-locate via `BASH_SOURCE` and the config command uses a literal absolute path written at install time by `enroll.bootstrap`). Document the chosen approach in the file header.

**Tests** (`template/tests/test_template_config_hook_shape.py`):
- `test_config_hooks_block_is_list_of_mappings` — load `template/config.yaml`, assert `cfg["hooks"]["on_session_start"]` is `list`, each entry is `dict` with `command` key.
- `test_iter_configured_hooks_returns_nonempty` — import Hermes's `shell_hooks._parse_hooks_block` (if importable; else inline a minimal port) and assert it returns ≥1 spec.
- `test_first_run_script_path_resolves_at_install_time` — after `enroll.bootstrap`, the `command:` string points to an absolute path that exists.

**Acceptance:** `pytest template/tests/test_template_config_hook_shape.py -v` shows 3 passed; manual `hermes profile install` followed by `hermes -p alpha-sh chat` actually fires first_run.sh (verifiable by `<profile>/local/setup.log` existing).

**Dependencies:** T0.

---

### T1 — `enroll.py` skeleton + discovery (~120 LoC + 60 LoC tests)

**Create:** `template/warroom_setup/enroll.py`, `template/tests/test_enroll_discovery.py`, `template/tests/fixtures/fake_mailbox_bin.sh`.

**Functions:**
- `discover_mailbox_cli(env=None) -> Path | None` — precedence: `env.MAILBOX_HOME/mailbox` → `~/.claude/mailbox/mailbox` → repo `coordination/bin/mailbox` dev fallback (walks up from `__file__`; **only meaningful in checkout, not in installed profiles** — document this in the docstring) → `shutil.which("mailbox")`. Returns `Path` (executable check via `os.access(p, os.X_OK)`) or `None`.
- `resolve_mailbox_home(env=None) -> Path` — env.MAILBOX_HOME else `Path.home() / ".claude" / "mailbox"`.
- `resolve_socket_path(env=None) -> Path` — env.MAILBOX_SOCKET else `resolve_mailbox_home(env) / "mailboxd.sock"`.
- `@dataclass EnrollState`: `board: str`, `label: str`, `cli_path: str | None`, `mailbox_home: str`, `socket_path: str`, `last_check_ts: float`, `status: Literal["ok", "cli-not-found", "socket-unreachable", "dry-run"]`.

**Tests:**
- `test_discover_prefers_mailbox_home_env_when_executable`
- `test_discover_falls_back_to_claude_default_when_env_absent`
- `test_discover_dev_fallback_when_running_from_repo_checkout`
- `test_discover_returns_none_when_nothing_present`
- `test_resolve_socket_path_honors_env_override`

**Acceptance:** `pytest template/tests/test_enroll_discovery.py -v` shows 5 passed.

**Dependencies:** T0.

---

### T1.5 — Atomic state writer in shared core (~40 LoC + 40 LoC tests)

**Modify:** `template/warroom_setup/state.py`. Add:

```python
def save_state(path: Path, payload: dict, *, mode: int = 0o600) -> None:
    """Atomic write: tempfile in same dir → chmod → os.replace. Mirrors setup._secure_file."""
```

Implementation: `tempfile.NamedTemporaryFile(dir=path.parent, delete=False, prefix=path.name + ".", suffix=".tmp")` → `json.dump(payload, fh)` → `fh.flush(); os.fsync(fh.fileno())` → `os.chmod(tmp.name, mode)` → `os.replace(tmp.name, path)`. Best-effort cleanup of tmp on exception.

**Tests** (`template/tests/test_state_save.py`):
- `test_save_state_writes_atomically` — write twice; assert no `.tmp` leftover.
- `test_save_state_sets_0600_mode` — assert `stat.S_IMODE == 0o600`.
- `test_save_state_survives_simulated_failure_mid_write` — monkeypatch `json.dump` to raise after first chunk; assert original file untouched.
- `test_save_state_creates_parent_dir_if_missing` — fail loudly if parent missing (don't create; documented behavior).

**Acceptance:** `pytest template/tests/test_state_save.py -v` shows 4 passed.

**Dependencies:** none (T0 only for ordering).

---

### T2 — `enroll.bootstrap` writes state + `mailbox:` block + installs Claude Code hook (~180 LoC + 120 LoC tests)

**Modify:** `template/warroom_setup/enroll.py`. **Create:** `template/tests/test_enroll_bootstrap.py`.

**Modify:** `template/warroom_setup/setup.py` — add `patch_mailbox_block(profile_root, **overrides)` mirroring `patch_war_room_block`. Both use sentinel pair `# >>> warroom-mailbox >>>` / `# <<< warroom-mailbox <<<` (distinct from `_WR_BEGIN` / `_WR_END`). Both use the hardened regex-anchored replacer from T2.5.

**Functions:**
- `bootstrap(profile_root, board, label, *, dry_run=False, env=None) -> EnrollState`:
  1. Discover CLI; resolve home/socket.
  2. Patch `mailbox:` block in `config.yaml` (atomic via `tempfile + os.replace`).
  3. Write `<profile>/local/warroom-enroll.json` via `state.save_state`.
  4. Append `<profile>/local/warroom-enroll.log` line: `<ISO ts> status=<status> board=<board> label=<label> cli=<cli_path> home=<home> socket=<socket>`.
  5. If CLI found and not `dry_run`, call `_install_claude_code_hook(profile_root)` to register `<profile>/hooks/session_start.py` into `~/.claude/settings.json` at position 0 in `hooks.SessionStart` (idempotent: skip if already present).
  6. If `dry_run`, skip all writes; return state with `status="dry-run"`.
- `_install_claude_code_hook(profile_root: Path) -> None` — reads `~/.claude/settings.json` (creates with `{"hooks": {"SessionStart": []}}` if absent), inserts our hook at index 0 if not present, atomic-writes back. Match-key is the absolute path to our `session_start.py`.

**Tests:**
- `test_bootstrap_writes_state_file_atomically` — mode 0o600, no `.tmp` leftover.
- `test_bootstrap_patches_mailbox_block_in_config` — fresh config; assert sentinel block contains `board`, `label`, `mailbox_home`, `socket_path`.
- `test_bootstrap_is_idempotent_when_inputs_unchanged` — call twice; state file byte-identical (minus `last_check_ts`); config.yaml block byte-identical.
- `test_bootstrap_updates_block_when_label_changes` — call with `label=alpha`, then `label=alpha2`; second value replaces first.
- `test_bootstrap_records_cli_not_found_without_raising` — empty PATH; `status="cli-not-found"`; state file still written; log line appended.
- `test_bootstrap_dry_run_writes_nothing` — assert no files created.
- `test_bootstrap_installs_claude_code_hook_at_index_zero` — fixture `~/.claude/settings.json` with mailbox's hook present; assert template's hook is at index 0, mailbox's at index 1.
- `test_bootstrap_claude_code_hook_install_is_idempotent` — call twice; no duplicate entry.
- `test_bootstrap_appends_log_line_per_invocation` — call twice; log has 2 lines.
- `test_bootstrap_writes_war_room_board_in_sync_with_mailbox_board` — assert both blocks have the same `board` value.

**Acceptance:** `pytest template/tests/test_enroll_bootstrap.py -v` shows 10 passed; manual `grep '_WR_BEGIN\|warroom-mailbox' <tmp>/config.yaml` shows both sentinel pairs.

**Dependencies:** T1, T1.5, T2.5.

---

### T2.5 — Harden sentinel-replace logic to anchored regex (~50 LoC + 60 LoC tests)

**Modify:** `template/warroom_setup/setup.py::patch_war_room_block` (existing) and add `patch_mailbox_block` (new). Both delegate to a shared helper:

```python
def _replace_sentinel_block(text: str, begin: str, end: str, new_body: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(begin)}$.*?^{re.escape(end)}$",
        re.MULTILINE | re.DOTALL,
    )
    ...
```

If the pattern matches: substitute. If not: append. All writes via `tempfile + os.replace`.

**Tests** (`template/tests/test_sentinel_replace.py`):
- `test_replace_preserves_unrelated_blocks` — file has both warroom and warroom-mailbox blocks; replacing one leaves the other untouched.
- `test_replace_handles_sentinel_string_in_comment_body` — file body contains a comment line matching `# >>> warroom-mailbox >>>` inside another block's body; assert anchored regex does NOT match it (because the comment is not at start-of-line in isolation).
- `test_replace_appends_when_sentinels_missing` — fresh file; assert block appended with sentinels.
- `test_replace_atomic_under_simulated_sigterm` — monkeypatch `Path.write_text` to raise after partial write; assert original file untouched.

**Acceptance:** `pytest template/tests/test_sentinel_replace.py -v` shows 4 passed; existing setup tests in PR #2 still pass against the refactored `patch_war_room_block`.

**Dependencies:** none.

---

### T3 — Template `session_start.py` (Claude Code harness hook; re-exports env from config.yaml) (~100 LoC + 80 LoC tests)

**Create:** `template/hooks/session_start.py` (Claude Code harness hook, registered into `~/.claude/settings.json` by T2), `template/tests/test_session_start_hook.py`.

**Contingency:** If T0 pre-flight #3 FAILED (env_file writes not visible between hooks), this file becomes a wrapper that writes `<profile>/local/runtime_env.json`, then exec's a thin shim that sources the JSON and exec's mailbox's hook with the env pre-populated. T0's runtime-preflight.md doc dictates which branch ships.

**Default-branch behavior (env_file path):**
- Reads `<profile>/config.yaml`'s `mailbox:` sentinel block via T2.5's regex extractor.
- Computes export set:
  - Always: `MAILBOX_BOARD=<board>`, `MAILBOX_LABEL=<label>`.
  - Conditional: `MAILBOX_HOME=<path>` only if non-empty AND `!= str(Path.home() / ".claude" / "mailbox")`.
  - Conditional: `MAILBOX_SOCKET=<path>` only if non-empty AND `!= str(resolve_mailbox_home() / "mailboxd.sock")`.
- Appends `export KEY=VAL` to `$CLAUDE_ENV_FILE` (deduplicated against existing lines via in-memory set).
- Fail-OPEN on any error (exit 0, log to `<profile>/local/warroom-enroll.log` with `event=session_start_hook` tag).
- If `mailbox.board` is empty: exit 0 but log `WARN: mailbox.board empty; cross-agent routing will use cwd-derived board only`.

**Functions:**
- `_read_mailbox_block(config_path) -> dict[str, str]` — uses T2.5 regex.
- `_compute_exports(block: dict) -> dict[str, str]` — applies the conditional rules above.
- `_append_exports(env_file: Path, values: dict) -> None` — open `a`, dedupe.
- `main() -> int` — orchestrator; fail-open.

**Tests:**
- `test_session_start_writes_exports_to_claude_env_file`
- `test_session_start_is_idempotent` — run twice; no duplicate `export` lines.
- `test_session_start_omits_mailbox_home_when_default`
- `test_session_start_includes_mailbox_home_when_custom`
- `test_session_start_omits_mailbox_socket_when_default`
- `test_session_start_fails_open_on_missing_config`
- `test_session_start_fails_open_on_missing_env_file_var`
- `test_session_start_logs_warning_when_board_empty`
- `test_session_start_writes_label_from_config`

**Acceptance:** `pytest template/tests/test_session_start_hook.py -v` shows 9 passed.

**Dependencies:** T0, T2.

---

### T4 — Wire `enroll.bootstrap` into `run_setup` + add `warroom.label` field (~50 LoC + 60 LoC tests)

**Modify:** `template/warroom_setup/setup.py::run_setup` — after `patch_war_room_block(...)` and `patch_mailbox_block(...)` when `warroom.enroll` is selected, call `enroll.bootstrap(profile_root, board, label)` where `label = values.get("warroom.label", "").strip() or ident.handle`. On `EnrollState.status != "ok"`, print one line to `out_stream`: `war-room: mailbox CLI not found — see template/README.md "Installing the mailbox runtime" to activate cross-agent features.`

**Modify:** `template/warroom_setup/selectables.py` — APPEND (after `warroom.min_confidence`, not between existing fields):
```python
TextField(id="warroom.label", prompt="War-room label (defaults to handle)",
          required=False, enable_if="warroom.enroll"),
```

**Tests** (`template/tests/test_setup.py` extension):
- `test_run_setup_calls_enroll_bootstrap_when_toggle_on`
- `test_run_setup_skips_enroll_when_toggle_off`
- `test_run_setup_label_defaults_to_handle`
- `test_run_setup_label_honors_override_value`
- `test_run_setup_prints_cli_not_found_warning_with_install_pointer`
- `test_run_setup_field_order_appends_label_at_end` — assert `warroom.label` index > `warroom.min_confidence` index.

**Acceptance:** `pytest template/tests/test_setup.py -k 'enroll or label' -v` shows 6 passed; existing 52 setup tests still pass.

**Dependencies:** T2.

---

### T5 — `warroom enroll` CLI subcommand with exit-code contract (~110 LoC + 90 LoC tests)

**Modify:** `template/warroom_setup/cli.py`. Add subparser `enroll`:
- `--board <name>`
- `--label <s>`
- `--status` (read-only; prints JSON)
- `--reconfigure` (bypass no-op guard; force re-write of state + block + Claude Code hook entry)
- `--dry-run`
- `--profile-root <path>`

**Exit-code contract** (locked):
- `0` — status=ok AND daemon reachable (or no `--status`, command succeeded).
- `1` — status=cli-not-found.
- `2` — status=ok but daemon unreachable (only emitted with `--status`).
- `3` — no state file (`enroll` never run on this profile).

**Functions:**
- `cmd_enroll(args) -> int` — dispatches to bootstrap or status.
- `enroll.enroll_status(profile_root) -> dict` — reads `local/warroom-enroll.json`, pings the socket. **Must NOT import `mailbox.client`.** Uses stdlib only: `s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(1.0); s.connect(socket_path); s.close()`. On `FileNotFoundError` / `ConnectionRefusedError` / `socket.timeout` → `daemon_reachable=False`. Returns merged dict `{board, label, cli_path, mailbox_home, socket_path, last_check_ts, status, daemon_reachable}`.

**Tests** (`template/tests/test_cli_enroll.py`):
- `test_cli_enroll_invokes_bootstrap_with_args`
- `test_cli_enroll_status_prints_json_when_state_exists`
- `test_cli_enroll_status_handles_no_state_returns_exit_3`
- `test_cli_enroll_status_returns_exit_2_when_daemon_unreachable`
- `test_cli_enroll_status_returns_exit_1_when_cli_not_found`
- `test_cli_enroll_status_returns_exit_0_when_all_ok` — spin up a tmp UNIX socket listener in a thread.
- `test_cli_enroll_dry_run_propagates_flag`
- `test_cli_enroll_reconfigure_bypasses_idempotency_guard`
- `test_enroll_status_does_not_import_mailbox_client` — `sys.modules` snapshot before/after; assert no `mailbox.client` entry added.

**Acceptance:** `pytest template/tests/test_cli_enroll.py -v` shows 9 passed.

**Dependencies:** T1, T2.

---

### T6 — Promote `template/skills/warroom/SKILL.md` from placeholder to real protocol (~80 LoC markdown + 30 LoC tests)

**Modify:** `template/skills/warroom/SKILL.md` — replace placeholder body with frontmatter-minimal real-protocol content:

```
---
name: warroom
description: Coordinate with other war-room agents on the shared board — see who's
  here, claim a lane, broadcast findings, read inbox, release lanes when done.
---

# Skill: War Room

You are part of a war-room board with other agents. Use these commands to coordinate.

## See who else is here
```
mailbox ps              # active peers on this board
mailbox claims --all    # everyone's open file/lane claims
```

## Claim a work-lane before starting (prevents dogpiling)
```
mailbox claim-lane <lane-name> --note "<one-line scope>"
```
(allow → you have it; deny → someone owns it; warn → stale, ask first.)

## Broadcast and read
```
mailbox send --to <peer-label> "<message>"
mailbox send "<broadcast>"           # to = "*"
mailbox inbox                        # read once; clears on read
```

## Release when done
```
mailbox release-lane <lane-name>
mailbox list-lanes
```
```

**DROPPED from base plan:** `template/skills/warroom/lib/warroom_ops.sh`. Reason: bash functions defined in a sourced file don't persist across Claude's Bash tool invocations (subshell scope). The bare `mailbox claim-lane` invocations in SKILL.md are the canonical interface. **DROPPED:** `metadata.hermes.tags` (fictional schema).

**Tests** (`template/tests/test_skill_warroom.py`):
- `test_skill_md_contains_required_verbs` — assert `mailbox ps`, `mailbox claim-lane`, `mailbox release-lane`, `mailbox list-lanes`, `mailbox send`, `mailbox inbox` each appear ≥1 time as code-block content.
- `test_skill_md_frontmatter_valid` — parse YAML frontmatter; assert `name == "warroom"`, `description` is non-empty string ≤500 chars.

**Acceptance:** `pytest template/tests/test_skill_warroom.py -v` shows 2 passed.

**Dependencies:** PR #2 (lane CLI must exist).

---

### T6.5 — Persona injection: teach the agent to use mailbox verbs ambiently (~20 LoC + 30 LoC tests)

**Modify:** `template/warroom_setup/setup.py::run_setup` — when `warroom.enroll` is on, call `patch_persona_decisions(profile_root, decision_text, sentinel_id="warroom-runtime")`. Decision text (locked):

```
- Before editing a file a board peer may also be touching, run `mailbox claim-lane <lane>` to coordinate. Release with `mailbox release-lane <lane>` when done.
```

Sentinel pair: `# >>> warroom-runtime >>>` / `# <<< warroom-runtime <<<` in `decisions.md`. Idempotent.

**Tests** (`template/tests/test_persona_warroom_injection.py`):
- `test_persona_decision_injected_when_warroom_enroll_on`
- `test_persona_decision_skipped_when_warroom_enroll_off`
- `test_persona_decision_is_idempotent`

**Acceptance:** `pytest template/tests/test_persona_warroom_injection.py -v` shows 3 passed.

**Dependencies:** T4.

---

### ~~T7~~ — REMOVED

**Reason:** `first_run.sh` is sentinel-guarded; a second `warroom enroll` invocation from it never re-fires. The single bootstrap call from `run_setup` (T4) is sufficient. Re-enrollment is served by `warroom enroll --reconfigure` (T5's new flag).

---

### T7 (renumbered from T8a) — In-process integration: protocol envelope + engine semantics (~150 LoC test)

**Create:** `template/tests/test_runtime_engine_inproc.py`. Marker `@pytest.mark.integration`. Skip if `importlib.util.find_spec("mailbox.engine") is None`.

**Why in-process:** F3 (protocol envelope `{"ok": True, "data": ...}` wrapping) is brittle when tested via the socket. Drives `MailboxEngine` directly with stub `BoardPersistence` / `LanePersistence` for fast, hermetic, envelope-free assertions.

**Test scenario** (`test_two_sessions_meet_on_named_board_inprocess`):
1. Instantiate `MailboxEngine` with in-memory persistence stubs.
2. Call `engine.join(session_id="a", label="alpha-sh", cwd="/tmp/a", board_name="shared")`.
3. Call `engine.join(session_id="b", label="beta-sh", cwd="/tmp/b", board_name="shared")`.
4. Assert both sessions appear in the same `named-shared` board's presence list.
5. `engine.send(session_id="a", to="beta-sh", kind="msg", body="hello")`.
6. `engine.poll_inbox(session_id="b")` returns `[{body: "hello", ...}]`.
7. Second `poll_inbox(b)` returns `[]` (read-once).
8. `engine.claim_lane(session_id="a", lane="auth", note="refactor")` → `{decision: "allow"}`.
9. `engine.claim_lane(session_id="b", lane="auth")` → `{decision: "deny", holder: "alpha-sh"}`.
10. `engine.release_lane(session_id="a", lane="auth")`.
11. `engine.claim_lane(session_id="b", lane="auth")` → `{decision: "allow"}`.

**Acceptance:** `pytest template/tests/test_runtime_engine_inproc.py -v --runintegration` shows 1 passed (~10 assertions inside).

**Dependencies:** T1-T6.5.

---

### T8 (renumbered from T8b) — End-to-end runtime proof: template hook → mailbox hook → join (~200 LoC test + fixture)

**Create:** `template/tests/test_runtime_hooks_e2e.py`. Marker `@pytest.mark.integration`. Skip if `importlib.util.find_spec("mailbox.client") is None`.

**This is the load-bearing proof that the C feature works end-to-end.**

**Fixture lifecycle (`mailbox_runtime` fixture):**
1. `tmp_home = tmp_path / "mailbox-home"`. Set `MAILBOX_HOME=tmp_home`, `MAILBOX_SOCKET=tmp_home/mailboxd.sock` in `os.environ` BEFORE any `mailbox` import.
2. Yield.
3. Teardown:
   - Read `tmp_home / "mailboxd.pid"` if present.
   - `os.kill(pid, signal.SIGTERM)`; wait up to 5s for socket file removal.
   - If still present, `os.kill(pid, signal.SIGKILL)`.

**Test scenario** (`test_two_profiles_meet_via_real_hook_chain`):
1. Use `mailbox_runtime` fixture.
2. Build two profiles via `_fake_profile` (reused from `test_setup.py`) at `tmp_path / "alpha-sh"` and `tmp_path / "beta-sh"`.
3. For each profile, invoke `run_setup(profile_root, yes=True, answers={"warroom.enroll": True, "warroom.board": "shared", "warroom.label": <handle>})`. Assert `mailbox:` block in each config.yaml; assert template's `session_start.py` installed in (test-isolated) `~/.claude/settings.json` at index 0.
4. **Simulate Claude Code SessionStart for profile alpha:**
   - Create tmp `CLAUDE_ENV_FILE`.
   - Exec `python3 <profile_alpha>/hooks/session_start.py` with `CLAUDE_ENV_FILE` env set. Assert exit 0; assert env_file contains `export MAILBOX_BOARD=shared` and `export MAILBOX_LABEL=alpha-sh`.
   - Monkeypatch `mailbox.client.request` to record args. Exec mailbox's `session_start.py` with stdin JSON `{"session_id": "sess-a", "cwd": "/tmp/alpha"}` and env that has sourced the env_file. Assert captured call: `request("join", {session_id: "sess-a", label: "alpha-sh", cwd: "/tmp/alpha", board_name: "shared"})`.
5. **Repeat for profile beta** with `session_id="sess-b"`, `cwd="/tmp/beta"`. Assert captured `board_name="shared"`.
6. **Now switch to real daemon path** (un-monkeypatch). Call `client.request("ps", {"session_id": "sess-a"})`; unwrap `resp["data"]`; assert it contains a peer with label `beta-sh`.
7. `client.request("send", {"session_id": "sess-a", "to": "beta-sh", "kind": "msg", "body": "hello"})` → assert `resp["ok"] is True`.
8. `client.request("poll_inbox", {"session_id": "sess-b"})` → unwrap; assert one msg with body `"hello"`.
9. Second `poll_inbox(sess-b)` → empty (read-once).
10. `client.request("claim_lane", {"session_id": "sess-a", "lane": "auth"})` → `resp["data"]["decision"] == "allow"`.
11. `client.request("claim_lane", {"session_id": "sess-b", "lane": "auth"})` → `resp["data"]["decision"] == "deny"`; `resp["data"]["holder"] == "alpha-sh"`.
12. `client.request("release_lane", {"session_id": "sess-a", "lane": "auth"})`.
13. Re-call beta's claim → `allow`.

**Acceptance:** `pytest template/tests/test_runtime_hooks_e2e.py -v --runintegration` shows 1 passed; fixture teardown leaves no daemon process or socket file.

**Dependencies:** T1-T7.

---

### T9 — README + SANITIZATION updates (~120 LoC docs + 30 LoC sanitize_check test)

**Modify:** `template/README.md` — add/modify:

- **"What `warroom setup` does"** — bullet: "Records `board` and `label` in `config.yaml`'s `mailbox:` block; runs `warroom enroll` to install the Claude Code SessionStart hook and persist runtime state."
- **"Cross-agent coordination"** — new H2: `mailbox:` block schema, `warroom enroll --status`, `warroom enroll --reconfigure`, references `template/skills/warroom/SKILL.md`.
- **"Installing the mailbox runtime"** — new H3 under above: `python3 coordination/install.py`; what `MAILBOX_HOME` does; expected symlink layout at `~/.claude/mailbox/mailbox`; recovery if missing.
- **"How profiles meet on a board"** — new H3 with manual smoke from §5 below (uses neutral handles `alpha-sh` / `beta-sh`).
- **"Debugging cross-agent issues"** — new H3: `cat <profile>/local/warroom-enroll.log` → `cat <profile>/local/warroom-enroll.json` → `mailbox ps` → `warroom enroll --status`.
- **"Known limitations"** — bullets: (a) without `coordination/`, war-room features fail-warn; (b) custom `MAILBOX_SOCKET` overrides break cross-agent visibility unless all profiles share the override; (c) `MAILBOX_HOME` differences segregate daemons.
- **"Configuration reference"** — `mailbox.board`, `mailbox.label`, `mailbox.mailbox_home` (optional), `mailbox.socket_path` (optional). Note `war_room.board` and `mailbox.board` are kept in sync by the wizard.

**Modify:** `template/SANITIZATION.md`:
- Add: "`MAILBOX_BOARD` / `MAILBOX_LABEL` are non-secret routing; never in .env, never in vaults. `mailbox:` block in `config.yaml` is source of truth."
- Add: "`mailbox.label` defaults to the Hermes handle. Use a generic handle for public demos; a real-name handle reveals identity."
- Add: SHIPPED `template/config.yaml` MUST have `label: ""` in the `mailbox:` block. The wizard populates it in `<profile>/config.yaml` only.

**Tests** (`template/tests/test_sanitization_warroom.py`):
- `test_shipped_template_mailbox_label_is_empty` — load `template/config.yaml`; assert `mailbox.label` is empty string.
- `test_sanitize_check_flags_realname_label_in_fixture` — feed sanitize_check a fixture with `mailbox.label: jane-doe` AND `--name jane`; assert exit 1.
- `test_sanitize_check_passes_on_shipped_template` — run sanitize_check on `template/` with realistic name list; exit 0.

**Acceptance:** `pytest template/tests/test_sanitization_warroom.py -v` shows 3 passed; `python3 template/scripts/sanitize_check.py template/` exits 0.

**Dependencies:** T1-T8.

---

## 4. Mailbox API choice rationale

(unchanged from base plan, recap)

- **Daemon lifecycle:** assume-running, auto-spawn on first `client.request` call. We never eagerly spawn from setup or first_run.sh.
- **Socket path:** env > config.yaml `mailbox.socket_path` > default. The template's `session_start.py` re-exports `MAILBOX_SOCKET` ONLY if the config value differs from default (F15 fix).
- **Enrollment trigger:** two-phase. `first_run.sh` + `warroom setup` persist routing. Template's `session_start.py` re-exports on every Claude session. Mailbox's `session_start.py` calls `join`.
- **Idempotency:** state file + sentinel-managed config block + Claude Code hook list dedup. All converge.
- **Two distinct hook systems:** Hermes gateway `on_session_start` (list-of-mappings, runs `first_run.sh` once per profile) and Claude Code harness `SessionStart` (runs our `session_start.py` then mailbox's on every session). Both are explicitly addressed.

---

## 5. Two-agent proof scenario

**Automated (CI):**

```bash
PYTHONPATH=coordination/src:template \
  template/.venv/bin/python -m pytest \
  template/tests/test_runtime_engine_inproc.py \
  template/tests/test_runtime_hooks_e2e.py \
  -v --runintegration
```

Expected output (line-for-line):
```
template/tests/test_runtime_engine_inproc.py::test_two_sessions_meet_on_named_board_inprocess PASSED
template/tests/test_runtime_hooks_e2e.py::test_two_profiles_meet_via_real_hook_chain PASSED
```

**Manual (sanity, neutral handles):**

```bash
# Terminal 1
hermes profile install ./template --name alpha-sh --alias --force -y
hermes -p alpha-sh chat
# (inside chat) ask: "what's mailbox ps say?"

# Terminal 2
hermes profile install ./template --name beta-sh --alias --force -y
hermes -p beta-sh chat
# (inside chat) ask: "broadcast 'hello' to the board"

# Terminal 1: peer message arrives as additionalContext
# Terminal 1: "claim lane 'auth' for the next 20 minutes"
# Terminal 2: "try to edit src/auth/handler.py"
# Expect: mailbox PreToolUse denies with reason "auth (alpha-sh, Xs ago)"
```

---

## 6. Failure modes + mitigations (updated)

**F1 [HIGH] — Mailbox daemon down at enroll time.** Bootstrap doesn't call mailbox. `client.ensure_running` handles spawn. `warroom enroll --status` pings via stdlib `socket.connect` (no spawn). **Mitigated.**

**F2 [HIGH] — Board mismatch.** `mailbox:` block is single source of truth; `session_start.py` re-exports on every session. T8 asserts both profiles land in same `named-shared`. Diagnostic warning fires ONLY when `MAILBOX_SESSION_ID` is set (F14 fix — no spurious shell warnings). **Mitigated.**

**F3 [MEDIUM] — Socket path mismatch.** State.json records resolved socket. `--status` shows it. README warns custom socket overrides segregate visibility. **Mitigated.**

**F4 [MEDIUM] — Re-enrollment race / SIGTERM mid-write.** All writes atomic via `tempfile + os.replace` (T1.5 for state.json; T2.5 for config.yaml). Last-writer-wins documented. **Mitigated.**

**F5 [MEDIUM] — Mailbox client API change.** `enroll.py` shells out to `mailbox` CLI for status, never imports `mailbox.client`. Only T8 imports `mailbox.client`; one place to update if `request()` signature shifts. **Mitigated.**

**F6 [LOW → RESOLVED via T0.5 + T0] — Hermes hook syntax.** T0.5 migrates to list-of-mappings; T0 pre-flight #1 verified the required shape. Test in T0.5 asserts `iter_configured_hooks` returns non-empty. **Mitigated.**

**F7 [LOW] — Label collision.** Hermes handles are unique per profile registry. Default safe. **Mitigated.**

**F8 [LOW] — `MAILBOX_HOME` differences.** We re-export only if non-default (F15 fix). Default profiles share daemon. README warns about overrides. **Mitigated.**

**F9 [LOW] — Token leak.** Tokens in `.env` only. `mailbox:` block has no secrets. Sanitize_check catches real-name labels (T9). **Mitigated.**

**F10 [HIGH — was Risk 1] — Hook ordering Hermes vs Claude Code conflated.** T0 + T0.6 + T3 redesign: Hermes hook fires first_run.sh once at gateway boot; Claude Code harness hooks (template's, then mailbox's) fire on every Claude SessionStart. Each in its own process, with explicit contract. **Mitigated.**

**F11 [HIGH — was Risk 2] — `CLAUDE_ENV_FILE` write visibility.** T0 pre-flight #3 verified empirically. If failed: T3 contingency branch ships (sidecar JSON + wrapper). **Mitigated.**

**F12 [MEDIUM — new] — Daemon-under-pytest leakage.** T8 fixture reads pidfile, SIGTERM on teardown, waits for socket removal. **Mitigated.**

**F13 [MEDIUM — new] — Multiple sentinel-managed blocks colliding.** T2.5 hardens replace logic to anchored regex with `re.MULTILINE | re.DOTALL`. **Mitigated.**

**F14 [LOW — new] — Sanitization hole for `mailbox.label`.** T9 adds test enforcing shipped `template/config.yaml` has `label: ""`; sanitize_check fixture test catches populated real-name labels. **Mitigated.**

---

## 7. README updates

(see T9 above for the full content list)

---

## 8. Sanitization audit

Confirmed against locked decisions and PR #2's `SANITIZATION.md` blocklist:

- **No employer names** — no `twelvelabs` / `TwelveLabs` / `tl-*` strings anywhere in plan text, file names, function names, test names, README content.
- **No real handles** — plan text uses neutral `alpha-sh` / `beta-sh` only (F11 fix; replaced base plan's `aahil-sh` / `aria-sh`).
- **No internal hosts / channel IDs / bot tokens.**
- **No new personalities.**
- **`skills/<org>/`** — not referenced.
- **Shipped `template/config.yaml`'s `mailbox.label`** is empty (T9 test enforces).
- **TwelveLabs constraint** verified absent.

---

## 9. Risks / unknowns (top 5, updated)

1. **[RESOLVED via T0]** Hermes hook syntax was malformed; Claude Code vs Hermes hook taxonomy was conflated. T0 pre-flights lock both BEFORE coding. T0.5 migrates config.yaml. T3 installs into `~/.claude/settings.json` (not config.yaml).

2. **[MEDIUM]** Daemon cwd on auto-spawn. `client.ensure_running` uses `CLAUDE_PROJECT_DIR or config.home()`. Inside Hermes-launched Claude subprocess, `CLAUDE_PROJECT_DIR` should be set; if not, daemon spawns with `MAILBOX_HOME` as cwd (benign). T8 e2e proves cross-profile messaging works either way.

3. **[LOW]** `coordination/install.py` may not exist or may require args we haven't documented. T9 README's "Installing the mailbox runtime" section assumes it does. If it doesn't, T9 must document the symlink layout manually (`ln -s coordination/bin/mailbox ~/.claude/mailbox/mailbox`). **Resolution:** read `coordination/install.py` during T9; document accurately.

4. **[LOW]** PR #2's `schema.MAILBOX_KEYS` / `MAILBOX_DEFAULTS` schema might differ post-merge. T2 reads them. **Resolution:** rebase before merging.

5. **[LOW]** Two-profile manual smoke (§5) assumes the operator has run `coordination/install.py` and has `mailbox` on PATH. README explicitly documents the prereq.

---

## 10. Definition of Done

**Code:**
- [ ] T0 pre-flight doc `template/docs/runtime-preflight.md` exists with verbatim empirical outputs for all 3 checks.
- [ ] T0.5: `template/config.yaml`'s `hooks.on_session_start` is `list[dict]` with `command` key; absolute paths resolved at install time.
- [ ] T1: `template/warroom_setup/enroll.py` ships with `discover_mailbox_cli`, `resolve_mailbox_home`, `resolve_socket_path`, `EnrollState`.
- [ ] T1.5: `template/warroom_setup/state.py::save_state` implemented and used by T2.
- [ ] T2: `enroll.bootstrap` writes state JSON (atomic, 0600), patches `mailbox:` block (atomic), installs template hook into `~/.claude/settings.json` at index 0 (idempotent), appends to log file.
- [ ] T2.5: `_replace_sentinel_block` uses anchored regex; both `patch_war_room_block` and `patch_mailbox_block` route through it.
- [ ] T3: `template/hooks/session_start.py` re-exports `MAILBOX_BOARD` / `MAILBOX_LABEL` (always) and `MAILBOX_HOME` / `MAILBOX_SOCKET` (conditional on non-default) to `$CLAUDE_ENV_FILE`, fail-OPEN, idempotent. Contingency branch documented in file header per T0 outcome.
- [ ] T4: `run_setup` calls `enroll.bootstrap` when `warroom.enroll` is on; prints install pointer on `cli-not-found`; `warroom.label` field appended to selectables.
- [ ] T5: `warroom enroll` subcommand with `--board`, `--label`, `--status`, `--reconfigure`, `--dry-run`. Exit codes 0/1/2/3 per contract. `enroll_status` uses stdlib socket; does NOT import `mailbox.client`.
- [ ] T6: `template/skills/warroom/SKILL.md` ships real protocol; NO `warroom_ops.sh`; NO `metadata.hermes.tags`.
- [ ] T6.5: `patch_persona_decisions` called from `run_setup` when `warroom.enroll` on; injects coordination rule under `# >>> warroom-runtime >>>` sentinels.
- [ ] T9: README has "Cross-agent coordination", "Installing the mailbox runtime", "How profiles meet on a board", "Debugging cross-agent issues", updated "Known limitations" and "Configuration reference". SANITIZATION.md updated.

**Tests:**
- [ ] All listed tests passing: T0.5 (3), T1 (5), T1.5 (4), T2 (10), T2.5 (4), T3 (9), T4 (6 new + 52 existing), T5 (9), T6 (2), T6.5 (3), T7 in-proc (1 with ~10 inner assertions), T8 e2e (1 with ~13 inner assertions), T9 sanitization (3). Total new tests: **70**.
- [ ] Existing setup tests (52) still pass.
- [ ] `pytest -m integration --runintegration` passes when `mailbox.client` importable; skips cleanly otherwise.

**Verification:**
- [ ] Manual two-profile smoke (§5) executed at least once on a clean machine; documented in PR description.
- [ ] `python3 template/scripts/sanitize_check.py template/` exits 0.
- [ ] `grep -rE 'twelvelabs|TwelveLabs|tl-' template/` returns nothing (excluding sanitize_check itself).
- [ ] `grep -rE 'aahil|aria' template/` returns nothing (neutral handles only in shipped artifacts).

**Operational:**
- [ ] `hermes profile install ./template --name alpha-sh --alias --force -y` succeeds end-to-end.
- [ ] First `hermes -p alpha-sh chat` produces `<profile>/local/setup.log` AND `<profile>/local/warroom-enroll.json` AND `<profile>/local/warroom-enroll.log`.
- [ ] `~/.claude/settings.json`'s `hooks.SessionStart` list contains the profile's `session_start.py` at index 0, mailbox's at index 1.
- [ ] `warroom enroll --status` returns valid JSON with `daemon_reachable: true` (after coordination installed).
- [ ] Two profiles with same `mailbox.board` value can exchange a `mailbox send` message inside chat.

When every checkbox above is checked, C is done.

---

**Files referenced:** `template/warroom_setup/{enroll,setup,cli,selectables,schema,state}.py`, `template/hooks/{first_run.sh,session_start.py}`, `template/skills/warroom/SKILL.md`, `template/persona/decisions.md`, `template/config.yaml`, `template/README.md`, `template/SANITIZATION.md`, `template/docs/runtime-preflight.md`, `template/scripts/sanitize_check.py`, `template/tests/test_{enroll_discovery,state_save,enroll_bootstrap,sentinel_replace,session_start_hook,setup,cli_enroll,skill_warroom,persona_warroom_injection,runtime_engine_inproc,runtime_hooks_e2e,template_config_hook_shape,sanitization_warroom}.py`, `coordination/src/mailbox/{client.py:44-107,config.py:5-13,cli.py:108-116,engine.py:98-159,289-377}`, `coordination/hooks/session_start.py:23-77`, `coordination/install.py`, `~/.hermes/hermes-agent/agent/shell_hooks.py:242-285`.

Save location: `docs/superpowers/plans/feature-c-cross-agent-runtime-FINAL.md`.

---

## Base plan (pre-refutation)

I have everything I need. Now I'll produce the C implementation plan.

---

# Feature C — Cross-Agent Runtime: Implementation Plan

Date: 2026-06-08. Branch: builds on `awr-shared-core` (PR #2). Status: ready to build once PR #2 merges.

## 1. Architecture summary

We're flipping `warroom.enroll` from "writes a config block, fires nothing" to "the next Claude session under this profile actually joins the named mailbox board and finds peers." Three pieces fit together: (a) a new `template/warroom_setup/enroll.py` module that owns mailbox discovery + idempotent first-run wiring, (b) a `mailbox:` block in `<profile>/config.yaml` (locked decision #1) that records `board / label / mailbox_home / socket_path`, and (c) a new `template/hooks/session_start.py` shipped IN the template that re-exports `MAILBOX_BOARD`/`MAILBOX_LABEL` into `CLAUDE_ENV_FILE` BEFORE mailbox's own `SessionStart` hook reads them. Existing code touched: `warroom_setup/cli.py` (add `enroll` subcommand), `warroom_setup/setup.py` (call `enroll.bootstrap` after `patch_war_room_block` when `warroom.enroll` is on), `warroom_setup/selectables.py` (`warroom.label` TextField + `warroom.mailbox_socket` optional override), and `template/skills/warroom/SKILL.md` (placeholder → real protocol). The mailbox package itself is read-only; we ride on the lane-CLI patch and config-driven socket already in place.

## 2. Runtime sequence (end-to-end, first session)

1. **Operator** runs `hermes profile install ./template --handle aria-sh -y --alias --force`. Hermes copies the template tree under `~/.hermes/profiles/aria-sh/`.
2. **Operator** runs `hermes -p aria-sh chat` for the first time. Hermes loads `<profile>/.env` via `load_hermes_dotenv` (Inv1) into `os.environ` of the gateway process.
3. **Gateway** fires `hooks.on_session_start = bash hooks/first_run.sh` (template/config.yaml:32). first_run.sh is sentinel-guarded (`local/.setup-done`); runs once.
4. **first_run.sh** invokes `python3 -m warroom_setup setup --yes`. `run_setup` resolves toggles, writes the `_WR_BEGIN`/`_WR_END` block (`warroom.enroll: true`, `board: default`, `label: aria-sh`), and — NEW — invokes `enroll.bootstrap(profile_root, board, label)`.
5. **enroll.bootstrap** discovers the mailbox CLI (`MAILBOX_HOME` env → `~/.claude/mailbox/mailbox` → `coordination/bin/mailbox` dev fallback → `shutil.which`). It writes `<profile>/local/warroom-enroll.json` (state: `board`, `label`, `cli_path`, `mailbox_home_resolved`, `last_check_ts`, `status`). If the CLI is found, it writes a sentinel-managed `mailbox:` block into `config.yaml` recording the resolved `mailbox_home` and `socket_path` (so subsequent invocations are deterministic even if `MAILBOX_HOME` changes in env later). If not found, status records `cli-not-found` and we fail-warn (exit 0, no enrollment attempted).
6. **first_run.sh** appends a line: `python3 hooks/session_start.py` (the TEMPLATE'S OWN session_start, NOT mailbox's). This template hook is also registered in `template/config.yaml`'s `hooks:` map as a second `on_session_start` entry. Sentinel exits.
7. **Gateway** continues to launch the actual chat / agent loop. It now spawns the Claude harness subprocess.
8. **Claude harness `SessionStart` event** fires both registered hooks in order: (a) **our** `hooks/session_start.py` reads `<profile>/config.yaml`'s `mailbox:` block, then writes `export MAILBOX_BOARD=default\nexport MAILBOX_LABEL=aria-sh\n` (plus optional `MAILBOX_HOME=...`/`MAILBOX_SOCKET=...`) into `$CLAUDE_ENV_FILE`. (b) **Mailbox's** `~/.claude/mailbox/hooks/session_start.py` reads `MAILBOX_BOARD`/`MAILBOX_LABEL` from `os.environ` (the harness sources `CLAUDE_ENV_FILE` between hooks). It calls `client.request("join", {session_id, label, cwd, board_name: "default"})`. The daemon auto-spawns via `client.ensure_running` if down.
9. **Engine.join** (engine.py:98) ensures both `repo-<hash>` board (derived from cwd) AND named board `default` exist; adds the session to both; computes co-location; emits a `note` message to the co-located peers ("aria-sh joined board — 2 now active; coordinate via mailbox", engine.py:143-144).
10. **Mailbox's `UserPromptSubmit` / `PostToolUse` hooks** (already installed) poll inbox + heartbeat. Peer messages arrive as `additionalContext`. From this moment, `mailbox ps`, `mailbox send --to aahil-sh "..."`, `mailbox claim-lane auth`, `mailbox inbox`, `mailbox list-lanes` all work from any subshell inside the profile because `MAILBOX_SESSION_ID` is also written to `CLAUDE_ENV_FILE` by mailbox's hook.

The hero claim: two profiles with the same `board: default` value end up on the same named board, regardless of cwd, because step 8a forces a non-cwd-derived board name into the env that mailbox's hook reads.

## 3. Task breakdown

### T1 — `enroll.py` skeleton + discovery (~120 LoC + 60 LoC tests)

**Create:** `template/warroom_setup/enroll.py`, `template/tests/test_enroll_discovery.py`, `template/tests/fixtures/fake_mailbox_bin.sh`.

**Functions:**
- `discover_mailbox_cli(env: Mapping[str, str] | None = None) -> Path | None` — precedence: `env.get("MAILBOX_HOME")/mailbox` → `~/.claude/mailbox/mailbox` → `<repo_root>/coordination/bin/mailbox` (dev fallback via walking up from `__file__`) → `shutil.which("mailbox")`. Returns `Path` (executable check) or `None`.
- `resolve_mailbox_home(env: Mapping[str, str] | None = None) -> Path` — `env.get("MAILBOX_HOME")` else `Path.home() / ".claude" / "mailbox"`. No I/O.
- `resolve_socket_path(env: Mapping[str, str] | None = None) -> Path` — `env.get("MAILBOX_SOCKET")` else `resolve_mailbox_home() / "mailboxd.sock"`. Matches `mailbox/config.py:5,13` exactly.
- `@dataclass EnrollState`: `board: str`, `label: str`, `cli_path: str | None`, `mailbox_home: str`, `socket_path: str`, `last_check_ts: float`, `status: str` (one of `ok`, `cli-not-found`, `socket-unreachable`, `dry-run`).

**Tests** (`test_enroll_discovery.py`):
- `test_discover_prefers_mailbox_home_env_when_executable` — set tmp `MAILBOX_HOME`, drop +x fake binary, assert chosen.
- `test_discover_falls_back_to_claude_default_when_env_absent` — fake `~/.claude/mailbox/mailbox` via monkeypatched `Path.home`.
- `test_discover_dev_fallback_when_running_from_repo_checkout` — assert `coordination/bin/mailbox` chosen when it exists in repo ancestry.
- `test_discover_returns_none_when_nothing_present` — empty PATH, no env, no fallbacks.
- `test_resolve_socket_path_honors_env_override` — `MAILBOX_SOCKET=/tmp/foo.sock` returns that exact path.

**Acceptance:** `pytest template/tests/test_enroll_discovery.py -v` shows 5 passed.

**Dependencies:** none (uses stdlib only).

---

### T2 — `enroll.bootstrap` writes state + mailbox: config block (~140 LoC + 90 LoC tests)

**Modify:** `template/warroom_setup/enroll.py`. **Create:** `template/tests/test_enroll_bootstrap.py`.

**Modify:** `template/warroom_setup/setup.py` — extend `patch_war_room_block` to also emit a separate sentinel-managed `mailbox:` block in `config.yaml` using `schema.MAILBOX_KEYS` + `schema.MAILBOX_DEFAULTS`. Use sentinel pair `# >>> warroom-mailbox >>>` / `# <<< warroom-mailbox <<<` (distinct from `_WR_BEGIN`/`_WR_END` so the existing block stays untouched). Add `patch_mailbox_block(profile_root, **overrides) -> None` mirroring `patch_war_room_block`.

**Functions:**
- `bootstrap(profile_root: Path, board: str, label: str, *, dry_run: bool = False, env: Mapping[str, str] | None = None) -> EnrollState` — orchestrator. Discover CLI, resolve home/socket, write `local/warroom-enroll.json` atomically (via `state.save_state` from PR #2's shared core; mode 0600), patch `mailbox:` block in `config.yaml` recording resolved paths. Fail-warn (return state with `status="cli-not-found"`, no exception) when CLI absent. If `dry_run`, skip both writes but return the would-be state with `status="dry-run"`.
- `_atomic_write_state(path: Path, state: EnrollState) -> None` — wraps `state.save_state` from shared core.

**Tests:**
- `test_bootstrap_writes_state_file_atomically` — creates `local/warroom-enroll.json`; assert no leftover `.tmp`; assert mode `0o600`.
- `test_bootstrap_patches_mailbox_block_in_config` — fresh `config.yaml`; after bootstrap contains `mailbox:` block between sentinels with `board`, `label`, `mailbox_home`, `socket_path`.
- `test_bootstrap_is_idempotent` — call twice with identical args; state file content (minus `last_check_ts`) byte-identical; config.yaml block byte-identical.
- `test_bootstrap_records_cli_not_found_without_raising` — empty PATH/env; `state.status == "cli-not-found"`; state file still written.
- `test_bootstrap_dry_run_writes_nothing` — `dry_run=True`; assert no files created/modified; returned state has `status == "dry-run"`.

**Acceptance:** `pytest template/tests/test_enroll_bootstrap.py -v` shows 5 passed; `grep '_WR_BEGIN\|warroom-mailbox' <tmp profile>/config.yaml` shows both sentinel pairs.

**Dependencies:** T1.

---

### T3 — Template `session_start.py` hook (re-export env from config.yaml) (~80 LoC + 60 LoC tests)

**Create:** `template/hooks/session_start.py`, `template/tests/test_session_start_hook.py`.

**Modify:** `template/config.yaml` — change `hooks.on_session_start` from a single string to a list:
```yaml
hooks:
  on_session_start:
    - bash hooks/first_run.sh
    - python3 hooks/session_start.py
```
(verify this matches the Hermes `hooks:` parser accepts lists; if not, chain via a single bash one-liner — see Risk 4.)

**Behavior:** Reads `<profile>/config.yaml`'s `mailbox:` sentinel block via simple text-level extraction (same pattern as `setup._WR_BEGIN`); appends `export MAILBOX_BOARD=<board>`, `export MAILBOX_LABEL=<label>`, optionally `export MAILBOX_HOME=<path>` / `export MAILBOX_SOCKET=<path>` to `$CLAUDE_ENV_FILE`. Fail-open: exits 0 on any error so it never blocks session start. Idempotent: scans existing CLAUDE_ENV_FILE contents, skips already-present lines.

**Functions:**
- `_read_mailbox_block(config_path: Path) -> dict[str, str]` — text-level parse of `# >>> warroom-mailbox >>>` ... `# <<< warroom-mailbox <<<`. Stdlib only.
- `_append_exports(env_file: Path, values: dict[str, str]) -> None` — open `a`, write `export KEY=VAL` lines, skip duplicates already present.
- `main() -> int` — orchestrator; fail-open.

**Tests:**
- `test_session_start_writes_exports_to_claude_env_file` — fixture config.yaml with mailbox block; assert `MAILBOX_BOARD=default` line appears.
- `test_session_start_is_idempotent` — run twice with same `CLAUDE_ENV_FILE`; no duplicate lines.
- `test_session_start_omits_empty_overrides` — config has `mailbox_home: ""`; assert no `MAILBOX_HOME=` line.
- `test_session_start_fails_open_on_missing_config` — no config.yaml; exit 0, no exception.
- `test_session_start_writes_label_from_config` — assert `MAILBOX_LABEL=aria-sh` reaches the env file.

**Acceptance:** `pytest template/tests/test_session_start_hook.py -v` shows 5 passed.

**Dependencies:** T2 (mailbox block must exist in config.yaml).

---

### T4 — Wire `enroll.bootstrap` into `run_setup` (~30 LoC + 50 LoC tests)

**Modify:** `template/warroom_setup/setup.py::run_setup` — after `patch_war_room_block(...)` when `warroom.enroll` in selected, also call `enroll.bootstrap(profile_root, board, label)` where `label` resolves from `values.get("warroom.label", "").strip() or ident.handle` (locked decision #4). On `EnrollState.status != "ok"` print one line to `out_stream`: `war-room: mailbox CLI not found — install coordination/ to activate cross-agent features.` (Generic; no employer/repo URL.)

**Modify:** `template/warroom_setup/selectables.py` — add:
```python
TextField(id="warroom.label", prompt="War-room label (defaults to handle)",
          required=False, enable_if="warroom.enroll"),
```
between `warroom.board` and `warroom.min_confidence`.

**Tests** (`template/tests/test_setup.py` extension):
- `test_run_setup_calls_enroll_bootstrap_when_toggle_on` — monkeypatch `enroll.bootstrap`; assert called once with `(profile_root, "default", "test-handle")`.
- `test_run_setup_skips_enroll_when_toggle_off` — `warroom.enroll` not in selected; assert `enroll.bootstrap` not called.
- `test_run_setup_label_defaults_to_handle` — no `warroom.label` value; bootstrap receives `label == ident.handle`.
- `test_run_setup_prints_cli_not_found_warning` — monkeypatch `enroll.bootstrap` to return state with `status="cli-not-found"`; assert warning in `out_stream`.

**Acceptance:** `pytest template/tests/test_setup.py -k enroll -v` shows 4 passed; existing 52 setup tests still pass.

**Dependencies:** T2.

---

### T5 — `warroom enroll` CLI subcommand (~80 LoC + 60 LoC tests)

**Modify:** `template/warroom_setup/cli.py`. Add subparser `enroll`:
- `--board <name>` (override config.yaml)
- `--label <s>` (override)
- `--status` (read-only; prints JSON or human-readable)
- `--dry-run`
- `--profile-root <path>` (defaults to derived)

**Functions:**
- `cmd_enroll(args) -> int` — if `--status`, calls `enroll.enroll_status(profile_root)` and prints. Otherwise calls `enroll.bootstrap(...)` and prints summary.
- `enroll.enroll_status(profile_root: Path) -> dict` — reads `local/warroom-enroll.json`, attempts a `ping` on the socket directly (`socket.connect` to resolved path with 1s timeout — does NOT spawn the daemon), returns merged dict with `daemon_reachable: bool`.

**Tests** (`template/tests/test_cli_enroll.py`):
- `test_cli_enroll_invokes_bootstrap_with_args` — monkeypatch bootstrap; `cli.main(["enroll", "--board", "x", "--label", "y"])` calls it with `("x", "y")`.
- `test_cli_enroll_status_prints_json_when_state_exists` — pre-seed state file; assert stdout parses as JSON with `board` key.
- `test_cli_enroll_status_handles_no_state_gracefully` — no state file; exit 0; prints "(not enrolled — run `warroom setup`)".
- `test_cli_enroll_dry_run_propagates_flag` — monkeypatch; assert `dry_run=True` reaches bootstrap.

**Acceptance:** `pytest template/tests/test_cli_enroll.py -v` shows 4 passed.

**Dependencies:** T1, T2.

---

### T6 — Promote `template/skills/warroom/SKILL.md` from placeholder to real protocol (~120 LoC markdown + 30 LoC tests)

**Modify:** `template/skills/warroom/SKILL.md` — replace placeholder body with a frontmatter-rich skill that documents the seven operational verbs and their canonical mailbox CLI invocations:

```
---
name: warroom
description: Coordinate with other war-room agents on the shared board: see who's
  here, claim a lane, broadcast findings, read inbox, release lanes when done.
metadata:
  hermes:
    tags: [coordination, mailbox, war-room]
---

# Skill: War Room

You are part of a war-room board with other agents. Use these commands to coordinate.

## See who else is here
mailbox ps              # active peers on this board
mailbox claims --all    # everyone's open file/lane claims

## Claim a work-lane before starting (prevents dogpiling)
mailbox claim-lane <lane-name> --note "<one-line scope>"
# (allow → you have it; deny → someone owns it; warn → stale; ask first.)

## Broadcast and read
mailbox send --to <peer-label> "<message>"
mailbox send "<broadcast>"           # to = "*"
mailbox inbox                        # read once; clears on read

## Release when done
mailbox release-lane <lane-name>
mailbox list-lanes                   # see all open lanes
```

The body intentionally never mentions specific commands like `claim` or `seize` on file globs (those are mailbox internals; lanes are the public coordination unit).

**Create:** `template/skills/warroom/lib/warroom_ops.sh` — small helpers:
- `wr_check_in() { mailbox ps; }`
- `wr_lane_claim() { mailbox claim-lane "$1" --note "${2:-}"; }`
- `wr_lane_release() { mailbox release-lane "$1"; }`
- `wr_broadcast() { mailbox send "$1"; }`
- `wr_direct() { mailbox send --to "$1" "$2"; }`

**Tests** (`template/tests/test_skill_warroom.py`):
- `test_skill_md_contains_required_verbs` — assert each of `claim-lane`, `release-lane`, `list-lanes`, `mailbox ps`, `mailbox send`, `mailbox inbox` appears in SKILL.md exactly once as a code-block command.
- `test_skill_md_frontmatter_valid` — parse YAML frontmatter; assert `name: warroom`, `tags` contains `coordination` and `mailbox`.
- `test_warroom_ops_sh_defines_all_helpers` — bash `declare -F` on sourced file; assert `wr_check_in`, `wr_lane_claim`, `wr_lane_release`, `wr_broadcast`, `wr_direct` all present.

**Acceptance:** `pytest template/tests/test_skill_warroom.py -v` shows 3 passed.

**Dependencies:** PR #2 (lane CLI must exist).

---

### T7 — first_run.sh invokes `warroom enroll` (~10 LoC + 30 LoC tests)

**Modify:** `template/hooks/first_run.sh` — after `warroom setup --yes`, add:
```bash
PYTHONPATH="$PROFILE_ROOT" python3 -m warroom_setup enroll --board "$(...)" --label "$(...)" >>"$PROFILE_ROOT/local/setup.log" 2>&1 || true
```
Defer reading board/label from the just-written `config.yaml`'s `mailbox:` block via a tiny grep-style extractor (3 lines of bash). Fail-warn (`|| true`).

Note: `warroom setup --yes` ALREADY calls `enroll.bootstrap` (T4) so this is a belt-and-suspenders second invocation that is purely idempotent — kept here so an operator who manually invokes `warroom setup` later (outside the `first_run.sh` sentinel) and then re-fires `first_run.sh` is still safe.

**Tests** (`template/tests/test_first_run.py`):
- `test_first_run_runs_setup_then_enroll` — execute `first_run.sh` in a tmp profile (stub `python3` with a recording shim); assert order: setup invocation before enroll invocation.
- `test_first_run_is_sentinel_guarded` — re-run; assert second invocation exits 0 with no python3 calls.
- `test_first_run_continues_on_enroll_failure` — stub enroll to exit 1; assert overall exit 0 (fail-warn).

**Acceptance:** `bash template/hooks/first_run.sh` runs cleanly in a tmp profile; `pytest template/tests/test_first_run.py -v` shows 3 passed.

**Dependencies:** T4, T5.

---

### T8 — Two-agent integration proof (~200 LoC test)

**Create:** `template/tests/test_runtime_two_profiles.py`. Marker `pytest.mark.integration`; skip with `pytest.importorskip("mailbox")` so pure-template CI without `coordination/src` on path skips cleanly.

**Test scenario** (single test `test_two_profiles_meet_on_named_board`):
1. `tmp_home = tmp_path / "mailbox-home"`; set `MAILBOX_HOME=tmp_home` and `MAILBOX_SOCKET=tmp_home/mailboxd.sock` for the test process.
2. Build two profiles via `_fake_profile` helper (reused from `test_setup.py`) at `tmp_path / "aahil-sh"` and `tmp_path / "aria-sh"`.
3. For each profile, call `warroom_setup.setup.run_setup(profile_root, yes=True)` with stubbed answers (board=`shared`, label=handle). Asserts `mailbox:` block in each config.yaml.
4. Pre-spawn the daemon by calling `mailbox.client.ensure_running()` once (uses `MAILBOX_SOCKET` env).
5. Simulate two distinct Claude sessions by directly calling `client.request("join", {...})` with two synthetic `session_id`s, distinct cwds, `board_name="shared"`, labels `aahil-sh` and `aria-sh` — bypassing the harness but faithful to what `coordination/hooks/session_start.py` does.
6. Assert `bridge_a.ps()` (raw `client.request("ps", {session_id: a})`) returns rows containing `aria-sh`'s label.
7. Call `client.request("send", {session_id: a, to: "aria-sh", kind: "note", body: "hello"})`.
8. Assert `client.request("poll_inbox", {session_id: b})` returns one message body `hello`; second poll returns empty (read-once).
9. Call `client.request("claim_lane", {session_id: a, lane: "auth", note: "refactor"})`; expect `{decision: "allow"}`.
10. Call `client.request("claim_lane", {session_id: b, lane: "auth"})`; expect `{decision: "deny", holder: "aahil-sh"}`.
11. Call `client.request("release_lane", {session_id: a, lane: "auth"})`.
12. Re-call b's claim; expect `{decision: "allow"}`.
13. Teardown: kill the daemon via `client.request("leave", ...)` for both sessions; `tmp_home` tearsdown automatically.

**Acceptance:** `pytest template/tests/test_runtime_two_profiles.py -v --runintegration` shows `test_two_profiles_meet_on_named_board PASSED` (single test, ~12 assertions inside). Skipped cleanly when `coordination/src` not importable.

**Dependencies:** T1-T7. This is the load-bearing proof.

---

### T9 — README + SANITIZATION updates (~80 LoC docs)

**Modify:** `template/README.md` — see section 7 below.

**Modify:** `template/SANITIZATION.md` — add: "`MAILBOX_BOARD` and `MAILBOX_LABEL` are non-secret routing config; never commit to .env, never put in Bitwarden. The `mailbox:` block in `config.yaml` is the source of truth."

**Tests:** none (docs only). Sanitization CI from PR #2 must still pass on the new content (the grep check in `template/SANITIZATION.md`).

**Acceptance:** `python3 template/scripts/sanitize_check.py template/` exits 0.

**Dependencies:** T1-T8.

---

## 4. Mailbox API choice rationale

### Daemon lifecycle: **assume-running, auto-spawn on first call**.

We do not eagerly spawn the daemon at `warroom setup` time, nor at `first_run.sh` time. Reason: `client.request` (client.py:88-107) already calls `ensure_running` (client.py:44-85) on `FileNotFoundError`/`ConnectionRefusedError`, spawning the daemon as a detached child with correct PYTHONPATH. Eagerly spawning it from `enroll.bootstrap` would race the gateway boot and either (a) inherit the wrong cwd (Risk 6 in original plan) or (b) leak a daemon on systems where mailbox is NOT installed. By deferring to the first real `join` call inside the Claude session, we get correct cwd (`CLAUDE_PROJECT_DIR`) and zero-config behavior identical to a regular mailbox install.

### Socket path: **all three with precedence — env > config.yaml mailbox.socket_path > default**.

Matches mailbox's own resolution (`config.py:13`): `os.environ.get("MAILBOX_SOCKET")` first, then default. We add a middle tier: if `MAILBOX_SOCKET` is unset but `<profile>/config.yaml`'s `mailbox.socket_path` is non-empty, the template's `session_start.py` hook EXPORTS `MAILBOX_SOCKET=<from config>` into `CLAUDE_ENV_FILE` so mailbox's own `config.py:13` resolution finds it. This means a profile can pin a socket explicitly without contaminating the shell, but the default path (`~/.claude/mailbox/mailboxd.sock`) just works for every profile that shares the same `MAILBOX_HOME`.

### Enrollment trigger: **two-phase — first_run.sh handles config persistence; mailbox's own SessionStart hook handles the actual join.**

We do NOT add a `register()` plugin entrypoint, do NOT add a new top-level skill invocation, do NOT call `mailbox join` from `first_run.sh` directly. Rationale: a real `mailbox join` requires a `session_id` set by the Claude harness on stdin (mailbox's `session_start.py:28`); `first_run.sh` runs from the gateway, OUTSIDE a Claude session, so there is no session_id to join with. The split is: (a) `first_run.sh` (and `warroom setup`) PERSIST the routing (`board`, `label`) into `config.yaml`. (b) Our template `hooks/session_start.py` re-exports those values into `CLAUDE_ENV_FILE` on EVERY Claude session boot. (c) Mailbox's installed `~/.claude/mailbox/hooks/session_start.py` (which already runs after ours, per the registered hook order in `coordination/install.py:26-32`) reads them and fires the actual `join`.

### Idempotency: **state file + sentinel-managed config block; every operation a no-op when content matches.**

`bootstrap` is called from `run_setup` AND from `cli.py::cmd_enroll` AND from `first_run.sh`. All three converge on the same `local/warroom-enroll.json` state file (mode 0600, atomic write) and the same `# >>> warroom-mailbox >>>` block. Re-enrollment with the same `(board, label)` produces zero diff except `last_check_ts`. Re-enrollment with a different board updates the config block in place (sentinel-managed replace, like `patch_war_room_block`). Mailbox itself handles session-level idempotency: `engine.join` (engine.py:110-113) finds existing presence by `session_id` and preserves `joined` timestamp; co-location is fired only on `newly_created or was_offline` (engine.py:130).

## 5. Two-agent proof scenario

The literal `pytest` invocation that proves cross-agent messaging works (this IS T8, run end-to-end):

```bash
# In repo root after T1-T8 land:
PYTHONPATH=coordination/src:template \
  template/.venv/bin/python -m pytest \
  template/tests/test_runtime_two_profiles.py \
  -v --runintegration
```

Expected output (line-for-line):
```
template/tests/test_runtime_two_profiles.py::test_two_profiles_meet_on_named_board PASSED
```

If anyone wants the truly-manual version (two Hermes profiles, two real Claude sessions):

```bash
# Terminal 1
hermes profile install ./template --name aahil-sh --alias --force -y
hermes -p aahil-sh chat
# (inside chat) ask: "what's mailbox ps say?"

# Terminal 2
hermes profile install ./template --name aria-sh --alias --force -y
hermes -p aria-sh chat
# (inside chat) ask: "broadcast 'hello' to the board"

# Terminal 1 inside chat — peer message should appear as additionalContext
# Terminal 1 inside chat — ask: "claim lane 'auth' for the next 20 minutes"

# Terminal 2 inside chat — ask: "try to edit src/auth/handler.py"
# Expect: mailbox PreToolUse denies the edit with reason "auth (aahil-sh, Xs ago)"
```

Manual smoke is for sanity; the integration test in T8 is the load-bearing CI proof.

## 6. Failure modes + mitigations

**F1 [HIGH] — Mailbox daemon down at enroll time.** Bootstrap never calls into mailbox; it only writes config + state. Mailbox's own `client.ensure_running` handles spawn at first `join` time. Mitigation: log `daemon_reachable: false` in `enroll --status` output by attempting a 1s `socket.connect` ping that does NOT auto-spawn (pass `autospawn=False` to `client.request("ping", ...)` — actually we open the socket directly, since we may not have `coordination` importable).

**F2 [HIGH] — Board name conflict / two agents on different boards.** This is the central risk the locked-decision-#1 design eliminates. The `mailbox:` block in `config.yaml` is the single source of truth; the template `session_start.py` hook re-exports it on EVERY session. Mitigation: at `enroll --status`, surface the resolved board AND warn if `os.environ["MAILBOX_BOARD"]` differs from the config value. Detection: in T8, the integration test asserts both sessions land in the SAME `named_id` board (engine.py:104).

**F3 [MEDIUM] — Socket path mismatch (one profile pins a custom socket; the other inherits default).** Catch: bootstrap records the resolved socket path in state.json at enroll time; `enroll --status` shows it. If two profiles in the same `MAILBOX_HOME` resolve to the same socket, they share the daemon (correct). If they resolve to different sockets, they get different daemons and never see each other. Mitigation: README warns that custom `MAILBOX_SOCKET` overrides break cross-agent visibility unless ALL profiles share the override.

**F4 [MEDIUM] — Re-enrollment race.** Two concurrent `warroom enroll` invocations on the same profile (rare; would require human + `first_run.sh` simultaneously). State file write is atomic (`os.replace`); config.yaml patch is line-based with sentinels. Worst case: both writes land, content identical, no harm. Mitigation: `_atomic_write_json` uses `os.O_CREAT|os.O_EXCL` for a `.lock` sidecar; on collision, second writer detects + retries once after 100ms.

**F5 [MEDIUM] — Mailbox client API change post-merge of PR #2.** Our `enroll.py` does NOT import `mailbox.client` directly (it shells out to the `mailbox` CLI for status checks via `discover_mailbox_cli` + `subprocess`). The only `mailbox`-Python-import touchpoint is `T8`'s integration test, which is marked `pytest.importorskip("mailbox")`. Mitigation: keep the import surface to `client.request(op, args)` — the most stable mailbox API. If `client.request` ever changes signature, we have ONE test file to update.

**F6 [LOW] — Hermes `hooks.on_session_start` does not accept a list.** Today's template uses a single string. The runtime contract for multi-hook chaining is unverified. Mitigation: fallback approach is to chain via bash one-liner in first_run.sh: `bash hooks/first_run.sh; python3 hooks/session_start.py`. Pre-flight check (see §10) must confirm.

**F7 [LOW] — Label collision on same machine.** Two profiles both default `warroom.label = handle`; handle is profile-unique per Hermes profile registry (Inv2). Mitigation: handle uniqueness is enforced by `hermes profile install` (collision errors with `--name`). Default is safe.

**F8 [LOW] — `MAILBOX_HOME` differs across profiles.** Two profiles with different `MAILBOX_HOME` values get different daemons. By default we DO NOT export `MAILBOX_HOME` (locked decision: only export non-default overrides). All profiles fall through to `~/.claude/mailbox/` → same daemon. Mitigation: docs warn that setting `MAILBOX_HOME` in any profile's `mailbox:` block makes that profile invisible to others.

**F9 [LOW] — Token leak.** Tokens (Discord/Slack/Anthropic) live in `.env` only; `mailbox:` block contains only board/label/paths. No secret enters config.yaml.

## 7. README updates

**`template/README.md`** — add/modify the following bulleted sections:

- **"What `warroom setup` does"** — add bullet: "Records `board` and `label` in `config.yaml`'s `mailbox:` block; runs `warroom enroll` to persist runtime state for the cross-agent runtime."
- **"Cross-agent coordination"** — new H2: explains the `mailbox:` block, the `warroom enroll` and `warroom enroll --status` commands, how two profiles end up on the same board (point at `board: default`), and references `template/skills/warroom/SKILL.md` for the operational verbs.
- **"How profiles meet on a board"** — new sub-section showing the two-profile manual smoke from §5 above, generic (no specific handles, no real channel ids).
- **"Known limitations"** — bullet: "Cross-agent messaging requires the `coordination/` mailbox package installed at `~/.claude/mailbox/` (or via `MAILBOX_HOME`). Without it, war-room features fail-warn — the profile still works for solo use."
- **"Configuration reference"** — add: `mailbox.board` (required for cross-agent), `mailbox.label` (defaults to handle), `mailbox.mailbox_home` (optional override), `mailbox.socket_path` (optional override).
- **"Sanitization"** — link to `SANITIZATION.md`; add note that board names and labels are NOT considered secrets but ARE considered identifying (recommend they not be your real name).

**`template/SANITIZATION.md`** — add a single bullet under "Non-secrets that still shouldn't leak": "`mailbox.label` — defaults to the Hermes handle; use a generic handle for public demos."

## 8. Sanitization audit

Confirmed against locked decisions and PR #2's `SANITIZATION.md` blocklist:

- **No employer names** — no string `twelvelabs`, `TwelveLabs`, `tl-*` anywhere. Plan text uses generic `aria-sh` / `aahil-sh` only as profile handles (both pre-existing handles in the template's own examples).
- **No internal hosts** — only `~/.claude/mailbox/`, `<profile>/.env`, `<profile>/config.yaml`, `<profile>/local/`. No `*.corp` / `*.internal`.
- **No specific channel IDs** — proof scenario uses board name `shared` / `default` only; no Discord/Slack snowflakes.
- **No real bot tokens** — Discord/Slack tokens are handled by walkthroughs from PR #2 (out of scope for C); C never touches `.env`.
- **Personalities** — out of scope for C; PR #2 already locked the 5-flavor set (helpful/concise/technical/teacher/noir). Plan does not introduce new personas.
- **`skills/<org>/`** — not referenced; the only skill C touches is `template/skills/warroom/SKILL.md` (generic).
- **TwelveLabs constraint** — verified absent from plan text, proposed code, proposed tests, proposed README updates.

## 9. Risks / unknowns (top 5)

1. **[HIGH — blocking for T3] Hermes `hooks.on_session_start` may not accept a list.** Today's template uses a single string. The plan assumes the gateway/harness will run two hooks if given a list. If not, we chain via bash one-liner in `first_run.sh` — but `first_run.sh` is sentinel-guarded (runs once), while `session_start.py` must run on EVERY session. The fallback is: register a NEW dedicated hook key (e.g. `on_session_pre_claude`) — depends on Hermes hook surface. **Resolution:** 30-minute read of `~/.hermes/hermes-agent/gateway/` hooks dispatcher BEFORE T3. If list isn't supported, switch T3 to ship `template/hooks/session_start.py` as a standalone script invoked by mailbox's own SessionStart wrapper (i.e. inject ourselves BEFORE mailbox in `~/.claude/settings.json`'s hook list at install time — much more invasive). 

2. **[HIGH — blocking for T8] `coordination/hooks/session_start.py` ordering vs. our template hook.** Mailbox's installed hook runs on Claude harness `SessionStart`; ours must run BEFORE so `MAILBOX_BOARD` is in env when mailbox reads it. Claude Code's hook order is "registration order in settings.json" (Inv research not done for C). If our template hook is added to `~/.claude/settings.json` AFTER mailbox's, our exports won't be visible to mailbox's hook in the same session. **Resolution:** read Claude Code hook-ordering docs / settings.json semantics. Worst-case mitigation: write the env file directly inside our hook AND have mailbox's hook fall back to reading `<profile>/config.yaml` directly via a small upstream patch (out of scope).

3. **[MEDIUM] Daemon cwd on auto-spawn.** `client.ensure_running` (client.py:52) sets cwd from `CLAUDE_PROJECT_DIR or config.home()`. In a Hermes-launched Claude subprocess, `CLAUDE_PROJECT_DIR` should be set, but unverified for our profile structure. If it isn't set or points wrong, daemon spawns with `~/.claude/mailbox` as cwd — benign for our case (state dir is computed from MAILBOX_HOME, not cwd). **Resolution:** T8 integration test directly verifies daemon spawn + cross-profile messaging — flushes any cwd footgun.

4. **[MEDIUM] `enroll --status` daemon-reachable check without spawn.** We want to avoid auto-spawning the daemon just to check status. `client.request(autospawn=False)` is the right call, but requires `mailbox.client` importable in the template venv. The template venv does NOT necessarily have `coordination/src` on path. **Resolution:** use a stdlib-only `socket.connect` ping in `enroll.enroll_status` (3 lines: `s = socket.socket(AF_UNIX); s.settimeout(1.0); s.connect(socket_path)` → reachable; raise → unreachable). Bypasses the import problem entirely.

5. **[LOW] PR #2 might land with a different `MAILBOX_KEYS` schema.** Our T2 reads `schema.MAILBOX_KEYS` and `schema.MAILBOX_DEFAULTS`. If PR #2's final schema differs from the values we saw in `template/warroom_setup/schema.py` (board/label/mailbox_home/socket_path), T2 needs trivial update. **Resolution:** rebase before merging; schema.py already shipped in PR #2 head as confirmed in the prompt.

## 10. Pre-flight check (BEFORE T1 starts)

Three things to verify empirically, all 30 minutes or less:

1. **Hermes `hooks.on_session_start` accepts list-or-string.** Read `~/.hermes/hermes-agent/gateway/` (likely `hooks.py` or `gateway_hooks.py`) and confirm whether the dispatcher iterates a list when given one, or only treats the value as a string. **If list NOT supported:** the plan switches T3 to register the hook as a NEW key (or chain via bash). Without this answer, T3's design is speculative.

2. **Claude Code hook ordering in `~/.claude/settings.json`.** Confirm that when multiple SessionStart hooks are registered, they run in registration order, AND that `CLAUDE_ENV_FILE` writes from hook N are visible to hook N+1. Read Claude Code hook docs OR run a 60-second test (register two hooks, both write to env_file, second one reads via `os.environ`). **If env_file writes are NOT visible between hooks in the same session:** the plan's two-phase model collapses — we need to write `MAILBOX_BOARD` to a place mailbox's hook reads (env file → but mailbox reads `os.environ`, sourced from the env file BETWEEN hooks: this is the key contract). Without this, T3 is decorative.

3. **Mailbox daemon survives across two distinct test process boots in T8's pytest fixture.** Confirm `client.ensure_running` from inside pytest does not race with itself when called from two subtests / two `client.request` invocations interleaved. If it does, T8's test must serialize join calls explicitly. Probably benign (mailbox's `_socket_responsive` check is the gate) but worth one timed test before locking T8.

Resolutions to these three items are the only thing standing between this plan and "go." Plan, code, and tests can proceed in parallel for T1-T2 (which depend on nothing) while the three pre-flights run.

---

End of plan. ~2,950 words. Files referenced: `template/warroom_setup/{enroll,setup,cli,selectables,schema}.py`, `template/hooks/{first_run.sh,session_start.py}`, `template/skills/warroom/{SKILL.md,lib/warroom_ops.sh}`, `template/config.yaml`, `template/README.md`, `template/SANITIZATION.md`, `template/tests/test_{enroll_discovery,enroll_bootstrap,session_start_hook,setup,cli_enroll,first_run,skill_warroom,runtime_two_profiles}.py`, `coordination/src/mailbox/{client.py:44-107,config.py:5-13,cli.py:108-116,engine.py:98-159,289-377}`, `coordination/hooks/session_start.py:23-77`, `coordination/install.py:26-32`.

---

## Adversarial review — Correctness

Format matches. **Not a bug.** Test in T6 (`test_skill_md_frontmatter_valid`) asserts on `tags` containing `coordination` and `mailbox`. Current value `[coordination, scaffold]` would fail; plan correctly proposes updating to `[coordination, mailbox, war-room]`. Note: `war-room` (with hyphen) inside a YAML flow sequence is fine, but it's a single token, not two.

---

### 20. MINOR — F4 "atomic write with .lock sidecar via O_EXCL" is over-engineered and inconsistent with the rest of the codebase

**Cite:** Risk F4: "`_atomic_write_json` uses `os.O_CREAT|os.O_EXCL` for a `.lock` sidecar; on collision, second writer detects + retries once after 100ms."

**Reality:** The existing codebase uses simple `os.replace` for atomicity (e.g. `agent_model.save` likely does this). Adding a lock-file dance for a code path that's only reachable in a documented race (concurrent setup) is gold-plating. Worse: the retry-after-100ms code is itself racy (TOCTOU on the lock file).

**Fix:** Drop the lock sidecar. Use `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)` + `os.replace`. POSIX guarantees atomicity. If two writers race, last-writer-wins is the documented behavior.

---

### Summary

**5 BLOCKER findings** (1, 2, 3) collapse to one root cause: **the plan assumes a Claude Code runtime contract (`CLAUDE_ENV_FILE`, `SessionStart` hook order, STDIN session_id payload) but the actual runtime is Hermes**, whose hook contract is different (`hooks.on_session_start` list of `{command: ...}` dicts, STDIN payload Hermes-shaped, no `CLAUDE_ENV_FILE`). Until the plan resolves which runtime it's targeting, T3, T7, T8, and the runtime sequence in §2 are unimplementable as specified.

**5 MAJOR findings** (4, 5, 6, 7, 8, 9, 10, 13, 14): tests don't actually verify what they claim; the `state.save_state` helper doesn't exist; the warroom_ops.sh bash helpers don't have `mailbox` on PATH; the grep-based config extractor in T7 is ambiguous; T7 is redundant or breaks sentinel guarding.

**~6 MINOR findings**: handle inconsistency, dev fallback documentation, frontmatter check details, over-engineered lock dance.

**Mandatory pre-flight:** Verify whether `hermes -p <profile> chat` actually invokes Claude Code as a subprocess, or whether the conversation runs entirely in `agent/conversation_loop.py` without a Claude Code harness. The answer determines whether mailbox's installed hooks ever fire under this template. If they don't, the entire C plan needs to be re-architected around a Hermes `on_session_start` shell hook that calls `mailbox.client.request("join", ...)` directly with a Hermes-provided session_id.

---

## Adversarial review — Completeness

This is a major architectural problem in the plan. The current template config.yaml has `on_session_start: bash hooks/first_run.sh` (a single string), but Hermes's shell-hooks normalizer **requires** `hooks.<event>` to be a `list` of `{command: ..., matcher: ...}` mappings. The plan in T3 proposes changing this to a list, but ALSO the existing config is already malformed per Hermes's spec — it must already be running through some other path (or the gateway has a separate hooks loader). Either way, the plan's T3 is making assumptions without verification.

I have enough to deliver the review.

# Adversarial Completeness Review — C Plan

## 1. SEVERITY: HIGH — Two completely different "session_start hook" systems are conflated; the plan never reconciles them.
**What's missing:** The plan's §2 step 8 has TWO hooks firing on "Claude harness SessionStart": (a) template's `hooks/session_start.py` writing `MAILBOX_BOARD` to `$CLAUDE_ENV_FILE`, and (b) mailbox's `~/.claude/mailbox/hooks/session_start.py` reading `os.environ.MAILBOX_BOARD`. But (a) is a HERMES gateway hook (declared in `template/config.yaml: hooks.on_session_start`, runs in the gateway process, before any Claude harness exists) while (b) is a CLAUDE CODE hook (registered in `~/.claude/settings.json` by `coordination/install.py`, runs inside Claude's harness subprocess, reads `session_id` from stdin JSON). These run in different processes at different times. `CLAUDE_ENV_FILE` is set by Claude Code's harness for ITS hooks — the Hermes gateway has no such file. So template's `session_start.py` writing to `$CLAUDE_ENV_FILE` will silently no-op when triggered as a Hermes hook (env var unset).
**Which task should fill the gap:** A new pre-flight T0 (BEFORE T3) that decides ONE of: (i) template's session_start runs as a **Claude Code** SessionStart hook by injecting it into `~/.claude/settings.json` (like mailbox's installer does), ordered before mailbox's; or (ii) the template's session_start runs as a Hermes hook and writes to `<profile>/.env` (which Hermes loads into `os.environ` at session start), not `CLAUDE_ENV_FILE`.
**Justification:** This is the load-bearing mechanism of the entire feature; if it's wrong, MAILBOX_BOARD never reaches mailbox's hook and the two-agent proof fails. The plan acknowledges Risk 1 and Risk 2 here, but defers to "30-minute read of gateway hooks dispatcher" — that read needs to be done before the plan is approved, not after.

## 2. SEVERITY: HIGH — `template/config.yaml`'s current `hooks.on_session_start: bash hooks/first_run.sh` is already non-conformant to Hermes's spec; T3's "change to list" is a partial fix that ignores the dict-of-command shape.
**What's missing:** Per `~/.hermes/hermes-agent/agent/shell_hooks.py:275-307`, `hooks.<event>` must be a **list of mappings**, each with a `command:` key: `[{command: "bash hooks/first_run.sh"}]`. The current string form is silently warn-skipped (`logger.warning("hooks.%s must be a list…")`). The plan proposes `- bash hooks/first_run.sh` (a list of strings), which the parser rejects too — it requires `- {command: bash hooks/first_run.sh}` mappings.
**Which task should fill the gap:** T3 must explicitly specify the dict-of-command syntax, and a `tests/test_template_config_hook_shape.py` should assert `iter_configured_hooks(yaml.safe_load(open(config.yaml)))` returns ≥1 non-empty spec (catches this regression and the pre-existing one).
**Justification:** If first_run.sh isn't running today (because the existing config is malformed), then setup never fires headlessly, and a fresh install has no `mailbox:` block written by `enroll.bootstrap`. The plan stacks on top of an assumption it never verifies. This is also adjacent to Risk 1 but the plan never connects the dots.

## 3. SEVERITY: HIGH — T8 doesn't actually prove the runtime path; it proves the daemon API works.
**What's missing:** T8 calls `client.request("join", {...})` directly with synthetic session_ids, bypassing both Hermes's gateway boot AND Claude Code's harness SessionStart. So it proves the mailbox daemon can host two sessions on a named board — which `coordination/tests/test_engine.py` already proves. It does NOT prove the integration: (a) that `warroom setup` → `enroll.bootstrap` writes the right `mailbox:` block; (b) that template's `hooks/session_start.py` reads that block and emits exports correctly; (c) that those exports reach mailbox's `session_start.py` via the env-file mechanism; (d) that mailbox's hook then calls `join` with `board_name="shared"`. Each is a separate failure surface.
**Which task should fill the gap:** Add T8b — `test_template_session_start_emits_mailbox_board(tmp_path)`: invoke `python3 template/hooks/session_start.py` with a fixture `config.yaml` containing the `mailbox:` block, `CLAUDE_ENV_FILE` pointed at a tmp file (or whatever the resolved equivalent is from finding #1), then exec `coordination/hooks/session_start.py` with stdin `{"session_id": "...", "cwd": "..."}` and a JSON capture of the resulting `client.request` call (monkeypatch). Assert the captured `board_name == "shared"`.
**Justification:** Without this, the test passes but the feature is broken — the load-bearing claim is that two **installed agents on their respective Hermes-launched Claude sessions** find each other, and T8 never exercises a Hermes boot or a Claude harness invocation of a hook.

## 4. SEVERITY: MEDIUM — No test for daemon restart mid-session / re-enrollment after the state file is stale.
**What's missing:** F4 mentions re-enrollment races; nothing addresses what happens when (a) the daemon dies mid-session and `enroll --status` reports `daemon_reachable: false`, (b) the operator changes `warroom.label` in `config.yaml` after first_run.sh has run, (c) `local/warroom-enroll.json` is deleted (user runs `rm local/setup.log` cleanup and grabs too much). The plan asserts "every operation a no-op when content matches" but never tests the "content DOESN'T match → recompute" path.
**Which task should fill the gap:** T2's test list should add `test_bootstrap_updates_block_when_label_changes` (call twice with different labels; assert second value replaces first); T5's tests should add `test_status_reports_daemon_unreachable_without_raising`.
**Justification:** Idempotency tests prove "double-call is safe"; they don't prove "config drift is detected and reconciled" — and the lattermost case is the one operators actually hit.

## 5. SEVERITY: MEDIUM — Plan ships `template/skills/warroom/lib/warroom_ops.sh` with no mechanism to make it available on PATH or sourceable from a skill invocation.
**What's missing:** T6 creates `warroom_ops.sh` with helpers `wr_lane_claim` etc. But (a) bash functions defined in a sourced file only persist in the calling shell, and Claude's Bash tool spawns a fresh subshell per invocation; (b) no `SKILL.md` content tells the agent to source the file; (c) no test verifies the file is even shipped by `hermes profile install` (e.g., that it's not in any exclude list).
**Which task should fill the gap:** Either delete the `lib/warroom_ops.sh` (the SKILL.md already documents the bare `mailbox claim-lane` invocations, which are the canonical interface), or T6 must (i) add `source $(dirname "$0")/lib/warroom_ops.sh` boilerplate to SKILL.md, (ii) add a test that `hermes profile install` ships the file.
**Justification:** Either an unused helpers file (wasted work, sanitization surface for nothing) or an undocumented one (cargo cult). Pick one.

## 6. SEVERITY: MEDIUM — `enroll --status`'s "daemon-reachable check without spawn" mitigation (Risk 4) is described but no task implements it.
**What's missing:** Risk 4's resolution says "use a stdlib-only `socket.connect` ping in `enroll.enroll_status`" — but T5's `enroll.enroll_status` function spec just says "attempts a `ping` on the socket directly". The actual implementation detail (3-line socket.connect with 1s timeout, returns bool, never auto-spawns) is in §9 risks not §3 tasks. A future implementer reading only T5 might pull in `mailbox.client` and accidentally trigger `ensure_running`.
**Which task should fill the gap:** T5's function list should explicitly say: "`enroll.enroll_status(profile_root)` MUST NOT import `mailbox.client`. It uses raw `socket.socket(AF_UNIX)` with `settimeout(1.0)` and `connect(socket_path)` — on success returns `daemon_reachable=True`, on `FileNotFoundError`/`ConnectionRefusedError`/`socket.timeout` returns `False`, never spawns."
**Justification:** Resolution-in-Risks is documentation of intent; specification-in-Task is what gets built. The gap is real.

## 7. SEVERITY: MEDIUM — No SIGTERM / partial-write protection for `local/warroom-enroll.json` or the `mailbox:` config block.
**What's missing:** F4 mentions "atomic via `os.replace`" for the state JSON, but the `patch_mailbox_block` in T2 is described as "line-based with sentinels" (mirroring `patch_war_room_block`). The current `patch_war_room_block` (setup.py:140-160) does a direct `cfg.write_text(new)` — NOT atomic. If first_run.sh is SIGTERM'd between sentinel-region rewrite and final flush, the operator gets a config.yaml with no closing sentinel and the next bootstrap reads garbage. The shared-core PR doesn't fix this.
**Which task should fill the gap:** T2 must specify atomic write for `patch_mailbox_block`: write to `config.yaml.tmp`, `os.replace`. Add `test_bootstrap_survives_simulated_sigterm_during_block_write` (use a mocked `Path.write_text` that raises after writing half the content; assert previous block still intact).
**Justification:** first_run.sh runs on every gateway boot pre-sentinel; partial writes on a SIGTERM'd boot (laptop sleep, terminal close) become a recurring user pain we can prevent cheaply.

## 8. SEVERITY: MEDIUM — README never tells the user what to do when `enroll --status` says `cli-not-found`.
**What's missing:** §7 has the "Cross-agent coordination" section and "Known limitations" bullet says "war-room features fail-warn — the profile still works for solo use", but no actionable next step. Users will Google "war-room: mailbox CLI not found"; the README needs an install path. Locked decisions don't include the install method (PR #2's investigation likely defers to `python3 coordination/install.py` but the plan never says so).
**Which task should fill the gap:** T9 must add a "Installing the mailbox runtime" subsection in README.md: 3 lines pointing at `coordination/install.py`, mentioning `MAILBOX_HOME` override, and confirming the symlink layout (`~/.claude/mailbox/mailbox`).
**Justification:** This IS in scope — without it, the proof scenario in §5 (which assumes mailbox is already installed) is impossible for a clean machine. The completeness gap is between "we documented the feature" and "we documented how to make it work."

## 9. SEVERITY: MEDIUM — No logging/observability hooks for debugging cross-agent failures at user time.
**What's missing:** When two profiles "don't see each other" in the wild, the diagnostic path is undefined. The plan mentions `<profile>/local/setup.log` (from first_run.sh redirection) and `enroll --status` JSON, but no log line is written by `enroll.bootstrap` itself when status != ok with a structured tag (so users can grep). No mention of `mailbox ps --json` or how to verify two profiles hit the same `named_id` board hash.
**Which task should fill the gap:** T4 should add: when `EnrollState.status != "ok"`, log to `<profile>/local/warroom-enroll.log` with timestamp + status + resolved paths. T9 README should add "Debugging: `cat <profile>/local/warroom-enroll.log`, then `<profile>/local/warroom-enroll.json`, then `mailbox ps`."
**Justification:** This is the failure-recovery skill the plan claims is operational but never builds. Without it, the first user bug report becomes a multi-hour debugging session.

## 10. SEVERITY: MEDIUM — Sanitization hole: `mailbox.label` and `warroom.label` default to handle, but nothing prevents a user from putting their real name in `warroom.label` and committing config.yaml.
**What's missing:** §8 claims "labels are NOT considered secrets but ARE considered identifying"; T9 adds a single bullet to SANITIZATION.md. But there's no CI check. `BLOCKED_VALUES_REGEX` in `schema.py` catches Slack IDs, UUIDs, `.internal` hosts, but nothing catches `label: jane-doe` in a managed block. The shared-core sanitize_check accepts `--name <employer> --name <you>` but the plan doesn't add a test that runs sanitize_check against a populated `mailbox:` block.
**Which task should fill the gap:** T9 must add a test that calls `sanitize_check.py template/ --name jane` against a fixture with `mailbox.label: jane-doe` and asserts exit 1. OR (simpler) the `mailbox:` block in the SHIPPED template must have empty `label: ""` and bootstrap must NOT write a populated block to the shipped tree (only to `<profile>/`, which is downstream of `template/`).
**Justification:** Without a sanitization rule that fires on labels, the next maintainer commits their `<profile>/config.yaml` for "testing" and ships their handle to the public repo.

## 11. SEVERITY: LOW — Plan doesn't say where `warroom enroll --status` exit code semantics live (0=ok, 1=cli-not-found, 2=daemon-down?), so the CLI is unspecified.
**What's missing:** T5 says cmd_enroll calls enroll_status and prints; never specifies exit code. Operators scripting health checks (`if ! warroom enroll --status >/dev/null; then alert; fi`) need a contract.
**Which task should fill the gap:** T5 must spec: exit 0 if `daemon_reachable AND status=="ok"`, exit 1 if `status=="cli-not-found"`, exit 2 if `daemon_reachable==False`, exit 3 if no state file. Add a test per code.
**Justification:** Small spec gap, but cheap to fix and crucial for the schedule/loop skills users will inevitably build on top.

## 12. SEVERITY: LOW — T7 "belt-and-suspenders enroll invocation from first_run.sh" is dead code by the plan's own logic.
**What's missing:** T4 already calls `enroll.bootstrap` from `run_setup`, which `first_run.sh` invokes via `warroom setup --yes`. T7 then adds a SECOND `python3 -m warroom_setup enroll ...` invocation in first_run.sh. The plan justifies this as "for an operator who manually invokes `warroom setup` later (outside the `first_run.sh` sentinel) and then re-fires `first_run.sh`" — but `first_run.sh` is sentinel-guarded; it WON'T re-fire. So this code path is unreachable.
**Which task should fill the gap:** Drop T7 entirely; keep only the T4 wiring. Or, if there's a re-enrollment-on-board-change use case, T7 should be replaced with a `warroom enroll --reconfigure` command that bypasses the sentinel intentionally.
**Justification:** Dead code is technical debt and a sanitization audit surface. The plan calls itself out on it without removing it.

## 13. SEVERITY: LOW — Plan never specifies what `warroom enroll --board=X` does to the existing `<profile>/config.yaml: war_room.board` field.
**What's missing:** There are TWO board fields: `war_room.board` (in `_WR_BEGIN`/`_WR_END` block) and `mailbox.board` (in the new `warroom-mailbox` block). T5's `--board` override writes only to `mailbox:` block. Are they meant to stay in sync? Diverge? The plan doesn't say.
**Which task should fill the gap:** Resolve the relationship in §1 architecture summary, and in T2 spec: either (i) collapse to one (`mailbox.board` is the only source of truth, `war_room.board` is deprecated/removed); or (ii) document that `enroll --board` updates BOTH atomically.
**Justification:** Drift here means the "warroom" plugin (confidence gate) and the mailbox client disagree about which board they're on — silent splitbrain.

## 14. SEVERITY: LOW — Persona content in `template/persona/decisions.md` (touched by `patch_persona_decisions` in PR #2) is not updated to teach the agent to use mailbox verbs.
**What's missing:** T6 ships SKILL.md with the verbs, but the agent's PERSONA (its always-loaded prompt) gets no rule like "when you see other agents in `mailbox ps`, coordinate via mailbox before touching shared files." Without a persona-level injection, the agent only consults SKILL.md when /warroom is explicitly invoked. Cross-agent coordination should be ambient.
**Which task should fill the gap:** Add T6b: call `patch_persona_decisions(profile_root, "Before editing any file touched by a board peer, claim a lane via `mailbox claim-lane`.", sentinel_id="warroom")` from `run_setup` when `warroom.enroll` is on. Test asserts the rule appears between sentinels.
**Justification:** PR #2 specifically built `patch_persona_decisions` for this kind of injection. C is the first feature that should use it, and the plan never invokes it. Without this, the plugged-in proof works in tests but agents don't actually coordinate in practice.

## 15. SEVERITY: LOW — Plan's "out of scope" coverage is silent on plugins/ (the warroom-gate plugin from confidence-gate work) — does C touch it or not?
**What's missing:** The confidence gate plugin (in `template/plugins/warroom-gate/` per prior commits) currently reads `war_room.board` from config. If §1's locked decision says "routing is in `mailbox:` block", does the gate plugin also migrate? Or does it still read `war_room.board`? Plan doesn't say. If it migrates, that's a NEW task. If not, finding #13's "war_room.board vs mailbox.board" question becomes urgent.
**Which task should fill the gap:** Explicit one-line note in §1: "The warroom-gate plugin is unchanged; it continues to read `war_room.board` for confidence-gate scoping. Cross-agent routing reads only `mailbox.board`. The two are independent but the wizard writes the same value to both for consistency."
**Justification:** Out-of-scope-by-default is fine; out-of-scope-but-undeclared is the failure mode where a reviewer assumes it's covered and a contributor breaks it next sprint.

---

## What I checked and found clean
- Locked decisions 1, 2, 3, 4, 6 are honored consistently throughout the plan.
- Locked decision 5 (skills/<org_name>/** excluded) is not relevant to C and not violated.
- No TwelveLabs references anywhere in plan text, file names, function names, test names, or proposed README content.
- Personas remain at the 5-flavor set; no new personas introduced.
- `mailbox` package imports are correctly scoped to T8's integration test only (Risk 5 mitigation is concrete).
- `clamp_pct` / `BLOCKED_VALUES_REGEX` / `MAILBOX_KEYS` references in T2 are correct against actual `schema.py`.
- The two-phase env-file mechanism, IF the hook system is reconciled per finding #1, is the right architectural shape — splitting persistence (first_run) from runtime join (Claude SessionStart hook) is correct.
- Mailbox daemon auto-spawn rationale (don't pre-spawn from gateway) is correct and matches `client.ensure_running` semantics.

15 findings total. Findings #1, #2, #3 are the load-bearing ones — without resolving them, T8 passes but C doesn't actually deliver the proof. Findings #4-#10 are quality gaps that will turn into user bug reports. Findings #11-#15 are smaller spec/cleanup issues.

---

## Adversarial review — Feasibility

Confirmed — `state.save_state` doesn't exist. `state.py` is the wizard state machine, not a file-state helper. Plan T2 is broken on a non-existent API.

Now I have enough material. Let me write findings.

---

# Adversarial feasibility review — Cross-Agent Runtime plan (Feature C)

## Findings

### F1 [BLOCKING — kills the entire runtime story]
**File:** `template/config.yaml:31-32` (and plan T3's premise about adding a second `on_session_start` entry).
**The plan assumes Hermes parses** `hooks: { on_session_start: bash hooks/first_run.sh }`. It does not. Per `~/.hermes/hermes-agent/agent/shell_hooks.py:242-285` (`_parse_hooks_block`), Hermes shell hooks require `hooks.<event>` to be a **list of mappings** each with a `command` key: `hooks: { on_session_start: [{command: "bash hooks/.../first_run.sh"}] }`. A scalar string is rejected by `_parse_hooks_block` with `"hooks.%s must be a list of hook definitions; got str"` — warn-and-skip, so first_run.sh **never fires**. Evidence: aahil-sh's installed config (`~/.hermes/profiles/aahil-sh/config.yaml:448`) has `hooks: {}` and aria-sh's profile is empty — no AWR profile has *actually* booted through this hook path. The whole "first_run.sh writes `mailbox:` block, mailbox session_start reads it" chain is built on a hook that does not run today.
**Mitigation:** Add **T0 pre-flight + T0.5 hook syntax migration** — change `template/config.yaml`'s hooks block to the correct Hermes form (list-of-mappings with absolute `command`) BEFORE T1 starts. Also: the command path must be ABSOLUTE (Hermes runs `shlex.split(os.path.expanduser(command))` with `shell=False`, no `cwd` set to the profile root — relative `bash hooks/first_run.sh` won't resolve). Use `command: "bash $PROFILE_ROOT/hooks/first_run.sh"` — but Hermes does not expand `$PROFILE_ROOT`. The plan needs a generation step that writes an absolute path at template-install time, OR makes first_run.sh self-locating (it already is via `BASH_SOURCE`, but bash needs the script path resolved).

### F2 [BLOCKING for T2]
**File:** `template/warroom_setup/state.py` (whole file).
**Plan T2 calls `state.save_state` "from PR #2's shared core".** That function does not exist. `state.py` is a wizard FSM (class `WizardState` with `toggle`, `move`, `select_all` — pure in-memory). There is no atomic-write helper named `save_state` in shared-core. The plan's "atomic write via `state.save_state`" is a fabricated dependency.
**Mitigation:** T2 must include `state.save_state(path, data) -> None` (or use `answers_mod.save`-pattern: `tmp = path + ".tmp"; tmp.write(json); os.replace; chmod 0o600`). Add T2.0: "Implement `state.save_state(path, payload, mode=0o600)` mirroring `setup.write_env`'s atomic-rename pattern."

### F3 [BLOCKING for T8]
**File:** plan §5 + T8 step 5.
**Plan calls `client.request("send", {session_id: a, to: "aria-sh", kind, body})`.** This works (engine.py:453 takes those kwargs), BUT: `client.request` returns `{"ok": True, "data": ...}` — the test "expects `body == "hello"`" must navigate `resp["data"][0]["body"]` (list of dicts from `poll_inbox`). The plan's pseudocode skips this wrapper entirely. Similarly `claim_lane`'s return is `{"ok": True, "data": {"decision": "allow", ...}}`. T8 assertions need `resp["data"]["decision"]` not `resp["decision"]`.
**Mitigation:** Plan task T8 should add explicit "unwrap `resp['data']` before assertion" guidance OR call `engine.<op>(...)` directly in-process to bypass the protocol envelope (faster + less brittle for a hermetic test). Recommended: in-process engine for T8.

### F4 [HIGH]
**File:** `template/hooks/first_run.sh:9` + plan T7 modification.
**first_run.sh runs in the gateway process** (per Hermes shell-hook design — gateway/cli emits `on_session_start`). Inside that subprocess, `os.environ["CLAUDE_ENV_FILE"]` and `os.environ["MAILBOX_SESSION_ID"]` do NOT exist (those are set by the Claude Code *harness*, a different process Hermes does not own). The plan implicitly conflates "Hermes gateway `on_session_start`" with "Claude Code harness `SessionStart`" — they are different lifecycle events in different processes. Coordination's `coordination/hooks/session_start.py:23-77` is registered in `~/.claude/settings.json` (Claude Code harness), NOT in `~/.hermes/.../config.yaml`. So step 8's "both registered hooks fire in order" mixes incompatible hook systems.
**Mitigation:** Plan must add **T0.6 "lifecycle taxonomy" check**: explicitly distinguish (a) Hermes gateway `on_session_start` (where first_run.sh runs) from (b) Claude Code harness `SessionStart` (where `coordination/hooks/session_start.py` runs). The template's `session_start.py` (T3) must be wired into `~/.claude/settings.json` BEFORE mailbox's entry — i.e. it's a `coordination/install.py`-shaped operation that patches the user's settings, not a config.yaml change. This rewires T3, T4, and T7 substantially.

### F5 [HIGH]
**File:** plan §2 step 8a, T3 design.
**Plan assumes `CLAUDE_ENV_FILE` writes from hook N are visible as `os.environ` to hook N+1.** Unverified. Claude Code's hook contract: env_file writes ARE sourced into the SHELL for subsequent commands, but each hook's Python `os.environ` is snapshotted at process spawn. Two `python3` subprocesses run from Claude Code's hook list both inherit the *same* parent env at spawn time. So writing to `$CLAUDE_ENV_FILE` from hook A and reading `os.environ.get("MAILBOX_BOARD")` from hook B (which is what `coordination/hooks/session_start.py:33` does) requires Claude Code to (a) parse env_file between hooks and (b) inject into hook B's env. This is the plan's load-bearing assumption.
**Mitigation:** Pre-flight T0.7: 60-second empirical test — register two trivial hooks in `~/.claude/settings.json`, hook A writes `export X=1` to `$CLAUDE_ENV_FILE`, hook B prints `os.environ.get("X")`. If empty → plan needs a different mechanism (mailbox hook reads `<profile>/config.yaml` directly, requiring a profile-discovery shim or an upstream patch to mailbox).

### F6 [HIGH]
**File:** `coordination/src/mailbox/client.py:52`.
**Daemon cwd = `os.environ.get("CLAUDE_PROJECT_DIR") or config.home()`.** Inside T8's pytest test there's no CLAUDE_PROJECT_DIR. Daemon spawns with cwd `MAILBOX_HOME` (`tmp_home`). For `engine.join`, the daemon's cwd does NOT matter — `boards_mod.derive_repo_board(cwd)` (boards.py:8-34) uses the **caller-supplied** cwd from the `join` args (`{"cwd": cwd}` in client). So two test sessions with different cwds will land on different `repo-<hash>` boards but the SAME `named-shared` board (engine.py:104-107). T8's "assert both on the SAME `named_id` board" only works because of the named_board mechanism, not repo board. Plan claims both ride the same board "regardless of cwd" — true, but only via the named-board path; if `board_name` is None on either side, they diverge.
**Mitigation:** T8 must explicitly pass `board_name="shared"` on EVERY `join` request (not just hint at it). Also, T3's `session_start.py` MUST always export `MAILBOX_BOARD` — if it's blank, mailbox's hook (session_start.py:33) sets `board_name = None` and the two profiles never converge. Plan should add "T3 fails-CLOSED if config has no `mailbox.board` value: exit 0 but log warning so the operator notices."

### F7 [HIGH]
**File:** plan T8 fixture, `coordination/src/mailbox/client.py:60-65`.
**Daemon-under-pytest cleanup is fragile.** `ensure_running` spawns a detached child with `start_new_session=True`. pytest fixture teardown CANNOT reap that subprocess automatically — `tmp_path` removal happens before the daemon writes its socket, OR the daemon survives past the test and pollutes `~/.claude/mailbox/state` (if `MAILBOX_HOME` env override didn't take). Plan says "kill daemon via `client.request('leave', ...)`" — `leave` does NOT kill the daemon; it marks a session offline (engine.py:180-189). Daemon keeps running until SIGTERM.
**Mitigation:** T8 fixture must (a) set `MAILBOX_HOME` and `MAILBOX_SOCKET` env BEFORE importing `mailbox` (config.py reads env at every call so this works), (b) after the test, SIGTERM the daemon via `daemon.read_pidfile()` and `os.kill(pid, SIGTERM)`, (c) wait for socket file removal. Add explicit task T8.5 for fixture lifecycle.

### F8 [MEDIUM]
**File:** plan T1's `_atomic_write_state`.
**Plan says state file is `0o600` and writes via `os.replace`.** Stock atomic-write: write tmp, chmod, rename. But `os.replace` does NOT preserve permissions if tmp was created with default umask. Need explicit `os.chmod(tmp, 0o600)` BEFORE `os.replace`, OR `os.open(tmp, O_CREAT|O_WRONLY|O_EXCL, 0o600)` — but umask still masks. `setup._secure_file` (setup.py:34) sets permissions post-write — works fine but T1 must mirror that pattern, not invent one.
**Mitigation:** Reuse `setup._secure_file`. Plan note: "T1's `_atomic_write_state` uses the existing `_secure_file` pattern (chmod after rename)."

### F9 [MEDIUM]
**File:** plan T6's SKILL.md frontmatter.
**Plan ships frontmatter `metadata.hermes.tags`.** Hermes' skill discovery (`~/.hermes/hermes-agent/optional-skills/`) reads `name:` and `description:` only — `metadata.hermes.tags` is not a recognized field anywhere in the Hermes codebase I checked. Harmless but the test `test_skill_md_frontmatter_valid` asserts "tags contains coordination" — that test passes against fictional schema.
**Mitigation:** Drop the metadata block OR verify against an actual Hermes skill loader. Either way the test is testing self-fulfilling content, not real schema conformance.

### F10 [MEDIUM]
**File:** plan T4 + selectables.py L72-75.
**Plan adds `TextField(id="warroom.label", ...)` AND keeps `warroom.board`.** But selectables already has `warroom.board` and `warroom.min_confidence` — adding `warroom.label` between them silently changes the prompt ORDER experienced by every existing operator running `warroom setup`. Re-running setup after a template update would inject a new prompt mid-flow.
**Mitigation:** Place `warroom.label` AFTER `warroom.min_confidence` so prompt order for legacy fields is preserved. Add task note.

### F11 [MEDIUM — TwelveLabs-leak risk]
**File:** `~/.hermes/profiles/aahil-sh/.skills_prompt_snapshot.json:372-408` shows `twelvelabs/tl-*` skills loaded into aahil-sh.
**Plan's manual smoke section §5 uses `aahil-sh` as a sample handle.** If anyone follows the manual smoke against the *real* aahil-sh profile (the dev's actual profile, not a fresh template install), the agent loads `twelvelabs/tl-architect`, `tl-perf` etc., and those skill bodies may end up in mailbox `send` payloads or in CI test logs. The plan does call this out generically ("redact sample handles") but proposes `aahil-sh` IN THE PLAN TEXT — exactly the handle that has TwelveLabs skills loaded locally.
**Mitigation:** Replace `aahil-sh` everywhere in plan text + tests + READMEs with two neutral placeholder handles (e.g. `alpha-sh` and `beta-sh`). The `skills/<org>/**` sanitization rule from PR #2 protects the template tree but does not protect plan documentation or test fixtures referencing real installed-profile names.

### F12 [MEDIUM]
**File:** plan T2, `patch_mailbox_block` extension to setup.py.
**Plan adds a new sentinel pair `# >>> warroom-mailbox >>>` / `# <<< warroom-mailbox <<<`** distinct from `_WR_BEGIN`/`_WR_END`. setup.py already manages a `# >>> warroom-toolsets >>>` block (config.yaml:57) — three coexisting sentinel pairs in one file. The existing replace-in-place logic (setup.py:155-161) uses `text.split(_WR_BEGIN, 1)` — if any begin/end sentinel substring accidentally appears inside another's body (e.g. inside a YAML comment), the split corrupts the file.
**Mitigation:** Add task T2.5: "Audit sentinel-replace logic to handle multiple sentinel-managed blocks safely. Switch from string-split to regex with anchored line boundaries (`^# >>> warroom-mailbox >>>$ ... ^# <<< warroom-mailbox <<<$` with `re.DOTALL`)." Same hardening needed for `patch_war_room_block`.

### F13 [LOW]
**File:** plan T1's dev-fallback discovery walking up from `__file__`.
**`<repo_root>/coordination/bin/mailbox` discovery via "walking up from `__file__`"** assumes the test runs from a checkout. When a template is installed under `~/.hermes/profiles/<handle>/warroom_setup/enroll.py`, walking up hits `~/.hermes/profiles/<handle>/` then `~/.hermes/profiles/` — no `coordination/bin/mailbox` there. Discovery falls through to `shutil.which`. Fine, but the plan text says this fallback applies "when running from repo checkout" — be explicit that it never applies in installed profiles.
**Mitigation:** Plan note clarifying the dev-fallback is checkout-only.

### F14 [LOW]
**File:** plan F2 mitigation suggests "surface a warning if `os.environ['MAILBOX_BOARD']` differs from config value."
**`warroom enroll --status` runs from the operator's shell** where `MAILBOX_BOARD` is almost certainly unset (it's only written into `CLAUDE_ENV_FILE` by the template hook DURING a Claude session). The warning will fire spuriously every status check.
**Mitigation:** Drop the env-vs-config diff check, or only emit it when running inside a Claude session (detect via `MAILBOX_SESSION_ID` presence).

### F15 [LOW]
**File:** plan §6 F8 says "we DO NOT export `MAILBOX_HOME` (locked decision)."
**But plan §2 step 8a says** "writes `export MAILBOX_HOME=<path>` (plus optional...)". Internal contradiction.
**Mitigation:** Pick one. Recommended: only export `MAILBOX_HOME` if the config value is **non-empty AND differs from the default** (`~/.claude/mailbox`). Otherwise omit to keep shared-daemon default behavior.

### F16 [LOW]
**File:** plan T8 fixture.
**`pytest.importorskip("mailbox")` collides with the stdlib `mailbox` module** (yes, Python's stdlib has a `mailbox` package for mbox/Maildir). On systems where `coordination/src` is NOT on `PYTHONPATH`, `import mailbox` succeeds (stdlib) — `importorskip` does NOT skip, and the test attempts to use stdlib mailbox's API. Crash, not skip.
**Mitigation:** Use `importlib.util.find_spec("mailbox.client")` (the submodule unique to our package) for the skip-condition. OR `try: from mailbox import client; from mailbox.engine import MailboxEngine; except ImportError: pytest.skip(...)`.

### F17 [LOW]
**File:** plan §10 pre-flight #3 says "confirm `client.ensure_running` does not race with itself when called from two subtests / two `client.request` invocations interleaved."
**This pre-flight passes trivially** (mailbox's `_socket_responsive` is the gate, and `Popen` itself is atomic) but the deeper race is: pre-flight #1 + #2 (Hermes hooks list-form, Claude Code env_file visibility) are the BLOCKING ones. Plan ranks them L1/H1/L3, but they should all be HIGH and gated BEFORE T1.
**Mitigation:** Re-order §10. Promote items 1 and 2 to "must resolve BEFORE plan is approved." Item 3 is a sanity check, not a blocker.

---

## What I checked
- `coordination/src/mailbox/{client,config,engine,server,daemon,protocol,boards,cli}.py` — all ops claimed in plan exist; lane CLI is patched correctly (`cli.py:108-116`); `ensure_running` cwd uses `CLAUDE_PROJECT_DIR`; daemon does not shutdown via `leave`.
- `coordination/hooks/session_start.py` + `coordination/install.py` — registers into `~/.claude/settings.json`, not into Hermes config.yaml.
- `template/hooks/first_run.sh` + `template/warroom_setup/{setup,schema,selectables,state,cli}.py` — `state.save_state` does not exist; `schema.MAILBOX_KEYS` and `MAILBOX_DEFAULTS` exist (PR #2 landed those); `selectables` has no `warroom.label` field yet.
- `~/.hermes/hermes-agent/agent/shell_hooks.py:242-340` — Hermes `hooks:` config requires list-of-mappings; scalar form silently dropped.
- `~/.hermes/profiles/aahil-sh/config.yaml:448` — `hooks: {}`, confirming no AWR profile is actually wired through the assumed code path today.

## Top three plan-blocking items (must add tasks before T1)
1. **F1 + F4**: Hermes hook syntax is broken AND Hermes vs Claude Code hook taxonomy is conflated. T0/T0.5/T0.6 must rewire to list-of-mappings under Hermes config.yaml for first_run.sh, and patch `~/.claude/settings.json` (not config.yaml) for the template's `session_start.py`.
2. **F5**: `CLAUDE_ENV_FILE`-write-visibility-between-hooks is unverified and load-bearing. Must be empirically tested before T3 is designed.
3. **F2**: `state.save_state` is fabricated; T2 must include its implementation or use a different helper.
