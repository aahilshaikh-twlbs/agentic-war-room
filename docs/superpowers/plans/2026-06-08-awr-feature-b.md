# AWR Feature B — Interactive Installer (TUI): Implementation Plan

Date: 2026-06-08. Status: planning complete, ready to build. Final plan below; reviews preserved for audit.

---

## Final plan (post-refutation, ready to execute)

> NOTE: The synthesizer originally wrote a longer final-plan section directly to disk during the workflow; that text was lost when the harness persisted the workflow's truncated return value. This section was regenerated via a follow-up Agent call from the surviving base plan + 3 reviews below.

# AWR Feature B — Interactive Installer (TUI): Final Implementation Plan (post-refutation)

Date: 2026-06-08. Status: build-ready. Synthesized from base plan + Correctness (C1–C23), Completeness (K1–K25), Feasibility (F1–F20) reviews.

---

## Section 0 — Changes from base plan after adversarial review

### Disposition of every finding

**Correctness review (C1–C23):**
- C1 **TAKEN** — `warroom setup --yes` cannot replay an empty profile. Replaced by in-process orchestration (A1).
- C2 **OBSOLETE** — wrong answers filename moot after A1 (no bridge file).
- C3 **TAKEN** — drop `-y` from `hermes plugins enable`; profile-scoped form `hermes -p <name> plugins enable warroom-gate`.
- C4 **TAKEN** — default source resolves via `parents[2]`, not `parents[3]`.
- C5 **TAKEN** — `install.sh` is a real bash file inside `template/`, plus a real (non-symlink) shim at repo root.
- C6 **TAKEN** — drop the keyword-only star from any plan-text reference to `enroll.bootstrap`.
- C7 **TAKEN** — `InstallerAnswers` gains `agent_name`, `display_name`, `handle`, `discord_allowed_users`, `min_confidence`.
- C8 **TAKEN** — model picker is dual-toggle (allow both `model.opus` and `model.sonnet`); precedence follows `setup.py:385`.
- C9 **TAKEN** — `sync_substrate.sh` is wired as a pre-test hook in `template/Makefile`; CONTRIBUTING.md documents it; drift test stays byte-exact.
- C10 **TAKEN** — rollback hard-invariant: never `rmtree` a path with user data (A9).
- C11 **TAKEN** — module-global termios attrs captured at raw-mode entry; SIGINT handler reads them.
- C12 **TAKEN** — installer calls `run_wizard`; reserves `--headless` for explicit non-interactive.
- C13 **TAKEN** — walkthrough adapter fully specified (retry-up-to-3, cooked-mode, optional-step UX).
- C14 **TAKEN** — `write_env(profile_root, env_values, filename=".env")` positional; corrected throughout.
- C15 **TAKEN** — no-op confirmation only.
- C16 **TAKEN** — T9 README rewrite preserves the existing planned-mention pattern.
- C17 **TAKEN** — Stage 5 is explicitly an in-process display step (post-A1).
- C18 **OBSOLETE** — sidecar moves to `~/.awr/install-state.json` (F12).
- C19 **TAKEN** — launcher exports `PYTHONPATH="<installer-abs>:${PYTHONPATH:-}"`.
- C20 **TAKEN** — per-subprocess env construction documented; only one subprocess remains.
- C21 **TAKEN** — added `test_substrate_slack_walkthrough_imports_step_from_substrate`.
- C22 **TAKEN** — substrate manifest excludes `daemon_probe.py`.
- C23 **TAKEN** — collision picker uses three single-toggle entries with first-match-wins precedence.

**Completeness review (K1–K25):**
- K1 **TAKEN** — substrate import contract spelled out (launcher `cd`s into installer dir, exports `PYTHONPATH`).
- K2 **OBSOLETE** — secret-replay moot under A1.
- K3 **TAKEN** — walkthrough adapter spec adopted.
- K4 **TAKEN** — plugin-enable fallback is an advisory print, not format-guessing.
- K5 **TAKEN** — per-stage key bindings table adopted.
- K6 **TAKEN** — resume policy re-runs walkthroughs whose secrets weren't persistable.
- K7 **TAKEN** — `test_two_step_path_still_works` added.
- K8 **TAKEN** — T11 (uninstall) added.
- K9 **TAKEN** — curl-pipe claim DROPPED.
- K10 **OBSOLETE** — only one subprocess remains.
- K11 **TAKEN** — confirm screen prints "Will modify ~/.claude/settings.json (mailbox hooks)".
- K12 **TAKEN** — T0 precheck includes `posix_terminal_supported`.
- K13 **TAKEN** — `stderr=STDOUT` merges streams at kernel level; ordering clarified.
- K14 **TAKEN** — `install.log` truncated at start of each install; 1MB line cap.
- K15 **TAKEN** — `hermes --version` parsed via robust regex; unparseable → warn-and-proceed.
- K16 **TAKEN** — `--verbose` tees subprocess output to stderr.
- K17 **TAKEN** — sanitize check tokens expanded; installer import dependency check enforced.
- K18 **TAKEN** — optional-step UX in walkthrough adapter.
- K19 **TAKEN** — `install.sh` is a real file shim, no symlink.
- K20 **TAKEN** — exit codes 0/1/2/3 from `enroll --status` treated as informational.
- K21 **TAKEN** — sanitize_check default walk already covers installer; T9 adds regression only.
- K22 **TAKEN** — sidecar parent dir created with mode 0700.
- K23 **TAKEN** — `git` precheck conditional on source-is-URL.
- K24 **OBSOLETE** — no bridge file under A1.
- K25 **TAKEN** — success summary prints `Total time: Ts`.

**Feasibility review (F1–F20):**
- F1 **TAKEN** — T0 verifies plugin-enable mechanism; T6 stage 4 advisory fallback.
- F2 **TAKEN** — profile detection uses `config.yaml` presence as Hermes-managed signal.
- F3 **TAKEN** — A1 in-process orchestration replaces subprocess `warroom setup`.
- F4 **TAKEN** — T2 spells out import shape and `__init__.py` placement.
- F5 **TAKEN** — curl-pipe dropped.
- F6 **TAKEN** — module-global termios attrs for emergency restore.
- F7 **TAKEN** — installer-local raw-tty masked prompt (~30 LoC) replaces `getpass`.
- F8 **TAKEN** — `--force` semantics + alias-collision warning documented.
- F9 **TAKEN** — `stderr=STDOUT` kernel-level merge.
- F10 **TAKEN** — headless aborts early when required secret env var missing.
- F11 **OBSOLETE** — A1 collapses `enroll --status` into in-process call.
- F12 **TAKEN** — sidecar at `~/.awr/install-state.json`.
- F13 **TAKEN** — git URLs validated via `git ls-remote --exit-code`.
- F14 **REJECTED** — byte-exact drift policy retained; Makefile pre-test hook keeps it cheap.
- F15 **TAKEN** — `--stage-timeout` default 300s.
- F16 **TAKEN** — T0 platform check enforces POSIX-only.
- F17 **TAKEN** — T9 grep includes token patterns and scans `install.log` schema.
- F18 **TAKEN** — Reconfigure verifies `<profile>/warroom_setup/__init__.py` exists.
- F19 **TAKEN** — masked-prompt uses stdout only.
- F20 **TAKEN** — `--*-token-file` alternative added alongside `--*-token-env`.

### Architecture-level reversals (A1–A9)

1. **A1 — Drop subprocess `warroom setup --yes` replay → IN-PROCESS orchestration.** After `hermes profile install` lands the template, the installer adds `<profile>` to `sys.path` and directly calls `setup.write_env`, `agent_model.save`, `setup.patch_war_room_block`, `setup.patch_mailbox_block`, `enroll.bootstrap`, `enroll.enroll_status`. No subprocess to `warroom setup`; no `installer-answers.json` bridge. (Fixes F3, C1, C2, K2, K10, K24, F11.)
2. **A2 — Drop curl-pipe distribution.** Only `git clone && bash install.sh`. (F5, K9.)
3. **A3 — Sidecar at `~/.awr/install-state.json`.** Out of Hermes namespace. (F12, C18.)
4. **A4 — Real-file `install.sh` at both `template/` and repo root.** No symlinks. (C5, K19.)
5. **A5 — Single merged subprocess stream (`stderr=STDOUT`).** Kernel-preserved ordering. (F9.)
6. **A6 — Profile detection switches from `distribution.yaml` to `config.yaml`.** Catches legacy Hermes profiles. (F2.)
7. **A7 — Installer-local masked prompt (not `getpass`).** ~30 LoC raw-tty asterisks; integrates with TUI screen buffer. (F7, F19.)
8. **A8 — Plugin enable: `hermes -p <name> plugins enable warroom-gate`, no `-y`.** T0 validates. (C3, F1.)
9. **A9 — Rollback is HARD-INVARIANT-protected.** Re-inspect via `inspect_profile`; refuse `rmtree` if `has_user_data`. Unconditional. (C10.)

Net effect: thin TUI wrapper around an in-process orchestrator that calls existing `warroom_setup` public APIs. One subprocess (`hermes profile install`), zero bridge files, one sidecar in its own namespace.

---

## Section 1 — Architecture

Self-contained at start-up (no `warroom_setup` import dependency) but transitions to in-process orchestration after `hermes profile install` lands the template. Pre-install phase uses a vendored `_substrate/` package (byte-exact copies of `render.py`, `prompts.py`, `state.py`, `selectables.py`, `validators.py`, `discord_walkthrough.py`, `slack_walkthrough.py`). Post-install phase adds `<profile>` to `sys.path[0]` and imports `warroom_setup.setup`, `agent_model`, `enroll` to drive the rest in-process. All identity, env, and YAML mutations atomic via `setup._atomic_write_text`.

Drift guarded by `template/tests/test_installer_substrate_no_drift.py` (filecmp byte-equality). `template/Makefile` adds a `pre-test` target that runs `sync_substrate.sh --check` before pytest.

---

## Section 2 — Invocation surface

```
<repo>/install.sh                              # real two-line shim → template/install.sh
<repo>/template/install.sh                     # real launcher (lives in distribution)
<repo>/template/scripts/installer/
    __init__.py
    awr_install.py                             # main TUI + in-process post-install
    masked_prompt.py                           # raw-tty masked input (~30 LoC)
    subprocess_runner.py                       # single-stream Popen wrapper
    progress.py                                # in-place ANSI progress lines
    precheck.py                                # T0 capability validation
    profile_detect.py                          # config.yaml-based profile classification
    sidecar_state.py                           # ~/.awr/install-state.json
    rollback.py                                # has-user-data-guarded
    in_process_orchestrator.py                 # post-install in-process work
    _substrate/                                # vendored byte-equal copies
        render.py prompts.py state.py
        selectables.py validators.py
        discord_walkthrough.py slack_walkthrough.py
    sync_substrate.sh                          # maintainer rsync
```

Supported invocations:
```sh
bash install.sh                                   # interactive, source = template/ (parents[2])
bash install.sh --source /path/to/template
bash install.sh --headless --name alpha-sh --board shared \
    --discord-token-env DISCORD_TOKEN --anthropic-key-env ANTHROPIC_KEY \
    --agent-name alpha-sh --display-name "Alpha"
bash install.sh --uninstall alpha-sh              # T11
bash install.sh --resume                          # resume sidecar
bash install.sh --verbose                         # tee subprocess to stderr
```

`template/install.sh` exports `PYTHONPATH="<installer-abs>:${PYTHONPATH:-}"`, `cd`s into the installer dir, then `exec python3 -m awr_install "$@"`.

---

## Section 3 — TUI flow

Cooked mode everywhere except raw-mode togglers (channels + model). Steps:

1. Title screen.
2. Pre-flight panel (T0; see §12).
3. Source path prompt. Default = `Path(__file__).resolve().parents[2]`. Validator: dir exists + `distribution.yaml` present. Git URL: `git ls-remote --exit-code` (F13).
4. Profile name prompt. `valid_slug`. Collision check via `profile_detect.inspect_profile` → 3-strategy picker (§8).
5. Channels stage. `[x] discord [ ] slack [ ] neither`.
6. Discord walkthrough (if selected). Adapter loops up to 3 retries on validator failure (C13/K3); optional steps skippable with empty input (K18).
7. Slack walkthrough.
8. Anthropic API key. `masked_prompt.prompt_secret`. Validator: `startswith("sk-ant-")` + `len >= 40`.
9. Identity stage (C7): `agent_name`, `display_name`, `handle`, `discord_allowed_users` (optional), `min_confidence` (default 75).
10. Model stage. Dual-toggle (C8) — both selectable; precedence follows `setup.py:385`.
11. Board + label. `valid_board_name`, default `shared`; `valid_handle`, default profile name.
12. Confirmation screen. Lists "Will modify ~/.claude/settings.json (mailbox hooks)" (K11).
13. Execute phase. Cooked mode. Progress lines:
    ```
    [1/5] hermes profile install ............................. ok (2.3s)
    [2/5] write .env and identity (in-process) ............... ok
    [3/5] patch war_room + mailbox blocks .................... ok
    [4/5] hermes -p <name> plugins enable warroom-gate ....... ok (0.4s)
    [5/5] cross-agent enroll bootstrap ....................... ok
    ```
14. Success summary. Includes `Total time: Xs` (K25).

Per-stage key bindings (K5):

| Stage | Esc | Ctrl-C | Empty | EOF |
|---|---|---|---|---|
| source | back-to-start | abort+sidecar | retry | abort+sidecar |
| name | back to source | abort+sidecar | retry | abort+sidecar |
| channels picker | back | abort+sidecar | n/a | abort+sidecar |
| walkthrough step | skip-channel (confirm) | abort+sidecar | "press enter again to skip" | abort+sidecar |
| identity prompts | back | abort+sidecar | retry (required) / accept (optional) | abort+sidecar |
| confirm | back to source | abort (no sidecar) | n/a | abort |

---

## Section 4 — Subprocess management

`subprocess_runner.run_capturing(cmd, *, cwd=None, env=None, timeout=300.0) -> CommandResult`:
- `Popen(cmd, stdout=PIPE, stderr=STDOUT, stdin=DEVNULL, env=env, cwd=cwd)` — kernel-level merge.
- Single reader thread → `collections.deque(maxlen=400)`.
- Timeout 300s. SIGTERM, 5s wait, SIGKILL on timeout.
- `tail_for_error_line(lines, patterns=("DistributionError", "ValueError", "error:"))`.

Hermes install: `hermes profile install <SRC> --name <N> --alias --force -y`. Env: copy of `os.environ`, strip `PYTHONPATH`, set `PYTHONUNBUFFERED=1`.

Plugin enable (A8): `hermes -p <name> plugins enable warroom-gate`. Timeout 30s. Non-zero → warn + advisory print (F1/K4). No `-y`.

Cursor + terminal restored before each subprocess (C11/F6).

---

## Section 5 — Task breakdown (T0..T11)

**Total: 97 unit tests + 7 integration = 104.**

### T0 — Hermes capability validation (PRE-FLIGHT, BLOCKS T1+) — new

**Create:** `template/scripts/installer/precheck.py`, `template/docs/installer-preflight.md`.

Functions: `run_prechecks(env=None, *, source=None) -> list[PrecheckResult]`; `assert_all_pass(results) -> None`.

**Tests** (`test_installer_precheck.py`, 8): python_version, hermes_missing, version_parse_robustness, posix_terminal, plugin_enable_no_yes_flag, git_check_skipped_for_local_dir, writes_outcome, substrate_imports_under_pythonpath.

**Deps:** none. **Blocks:** T1+.

### T1 — Launcher + module skeleton

**Create:** `template/install.sh`, `<repo>/install.sh` shim, `template/scripts/installer/__init__.py`, `awr_install.py` argparse skeleton.

**Tests** (`test_installer_launcher.py`, 5): resolves_python3_and_pythonpath, preserves_existing_pythonpath, help_exits_zero, repo_root_shim_invokes_template_launcher, argparse_accepts_all_flags.

**Deps:** T0.

### T2 — Vendor substrate + drift guard

**Create:** `_substrate/`, `_substrate/__init__.py`, `template/Makefile` pre-test target, `template/CONTRIBUTING.md`.

**Tests** (`test_installer_substrate_no_drift.py`, 4): byte_identical, imports_cleanly, slack_walkthrough_imports_step, imports_under_random_cwd.

**Deps:** T1.

### T3 — Subprocess runner + progress + masked prompt

**Create:** `subprocess_runner.py`, `progress.py`, `masked_prompt.py`.

**Tests** (`test_installer_subprocess.py`, 10): merges_streams_in_kernel_order, returns_nonzero_on_failure, terminates_on_timeout, strips_pythonpath, tail_finds_error, tail_returns_none_when_clean, stage_runner_ok, stage_runner_fail, masked_prompt_returns_value, masked_prompt_restores_terminal.

**Deps:** T1.

### T4 — Existing-profile detection + collision UI

**Create:** `profile_detect.py`. `inspect_profile`, `collision_strategy`.

**Tests** (`test_installer_profile_detect.py`, 10): reports_missing, detects_hermes_via_config_yaml, detects_legacy_hermes, detects_user_data, reports_warroom_setup_presence, strategy_proceeds, strategy_reconfigures, strategy_demands_confirm, strategy_aborts_without_force, reconfigure_aborts_without_warroom_package.

**Deps:** T0.

### T5 — TUI orchestration

**Modify:** `awr_install.py` — `run_tui(args) -> InstallerAnswers` and `_stage_*` functions; walkthrough adapter with retry/optional/cooked-mode spec.

```python
@dataclass
class InstallerAnswers:
    source: str
    profile_name: str
    channels: set[str]
    discord_creds: DiscordCreds | None
    slack_creds: SlackCreds | None
    anthropic_key: str | None
    agent_name: str
    display_name: str
    handle: str
    discord_allowed_users: list[str]
    min_confidence: int
    model: Literal["opus", "sonnet"]
    board: str
    label: str
```

**Tests** (`test_installer_tui.py`, 13): source_validates_distribution_yaml, source_validates_git_url, name_rejects_invalid_slug, channels_returns_selected_set, identity_collects_all_fields, model_dual_toggle_precedence, confirm_lists_settings_json_modification, confirm_back_returns_to_source, headless_skips_prompts, esc_returns_to_predecessor, ctrl_c_writes_sidecar_restores_terminal, walkthrough_retries_on_validator_failure, walkthrough_optional_skippable.

**Deps:** T2, T3, T4.

### T6 — Execute phase: in-process orchestration

**Create:** `in_process_orchestrator.py`. Five-stage `execute(answers, *, dry_run, verbose, stage_timeout) -> int` (hermes install → in-process .env/identity → in-process YAML patches → plugin enable → in-process enroll bootstrap).

**Tests** (`test_installer_execute.py`, 13): dry_run_no_subprocesses, stage1_correct_hermes_args, stage2_writes_env_with_secrets, stage2_writes_identity, stage3_patches_war_room, stage3_patches_mailbox, stage4_profile_scoped_no_yes, stage4_failure_does_not_abort, stage5_calls_bootstrap_in_process, stage5_handles_enroll_status_codes, install_log_truncated, total_time_in_summary, verbose_tees_to_stderr.

**Deps:** T3, T4, T5.

### T7 — Sidecar state + resume

**Create:** `sidecar_state.py`. `~/.awr/install-state.json`, 0700 dir, 0600 file, atomic write, 24h TTL. Schema: `{started_at, profile_name, stage, answers_non_secret, completed_stages}` — secrets NEVER persisted.

**Tests** (`test_installer_sidecar.py`, 8): persists_non_secret_only, dotawr_namespace, creates_parent_with_0700, records_stage, resume_skips_completed, resume_after_walkthrough_re_prompts_secrets, expired_after_24h_ignored, cleanup_on_success.

**Deps:** T5.

### T8 — Rollback (has-user-data invariant)

**Create:** `rollback.py`. `rollback(profile_path, *, stages_completed) -> RollbackResult` — re-inspects via `inspect_profile` and refuses if `has_user_data`.

**Tests** (`test_installer_rollback.py`, 6): removes_on_clean_failure, refuses_when_user_data, refuses_on_confirm_overwrite, noop_when_stage1_incomplete, logs_decision, atomic_on_partial_rmtree_failure.

**Deps:** T4, T6.

### T9 — Headless mode

`--headless` requires `--name`, `--source`, `--board`, identity flags, and secrets via `--*-env VAR` or `--*-token-file PATH` (F20).

**Tests** (`test_installer_headless.py`, 7): requires_name_and_identity, reads_from_env_vars, reads_from_token_file, aborts_when_required_env_missing, aborts_on_collision_without_force, skips_walkthrough_when_tokens_provided, runs_no_prompts_with_stdin_devnull.

**Deps:** T6.

### T10 — README + smoke + sanitization

**Modify:** `template/README.md` (new "Interactive install (recommended)" section), `template/SANITIZATION.md`.
**Create:** `template/scripts/installer/SMOKE.md` (6-step manual recipe; `alpha-sh`/`beta-sh`/`shared`).

**Tests** (`test_installer_sanitization.py`, 5): no_employer_strings, smoke_uses_neutral_handles, install_log_redacts_secrets, sanitize_check_walks_installer, imports_only_substrate_and_stdlib.

**Deps:** T1–T9.

### T11 — Uninstall subcommand — new

**Modify:** `awr_install.py` — `--uninstall <name>` mode. Confirms when `has_user_data`; cleans sidecar; warns that `~/.claude/settings.json` mailbox hooks are NOT removed.

**Tests** (`test_installer_uninstall.py`, 5): invokes_hermes_profile_delete, prompts_confirm_on_user_data, cleans_sidecar, warns_about_settings_json, exits_nonzero_when_profile_missing.

**Deps:** T4.

### Integration (`@pytest.mark.integration`, 7 tests, in `test_installer_e2e.py`)

happy_path_neutral_profile, rollback_on_simulated_hermes_failure, resume_after_simulated_sigint, two_step_path_still_works, uninstall_round_trip, collision_reconfigure_preserves_user_data, headless_full_install_with_env_secrets.

**Unit total: 8+5+4+10+10+13+13+8+6+7+5+5 = 94 + 3 buffer = 97. Integration: 7. = 104.**

---

## Section 6 — State + idempotency

Mid-flow state:
- `~/.awr/install-state.json` — non-secret sidecar, 0700/0600, atomic write, 24h TTL.
- `<profile>/local/install.log` — truncated at start, 1MB cap.
- `<profile>/local/agent.json` + `.warroom-setup.json` — Hermes canonical files; written in-process via `agent_model.save` (and `setup.run_setup` on reconfigure).

`--force` semantics: Hermes' `--force` overwrites distribution-managed file set; does NOT touch `<profile>/local/`. Safe IF user wants `local/` preserved. Installer never passes `--force` on `confirm-overwrite` until operator confirms.

Resume from partial install:
- Stage <1: re-prompt from recorded stage.
- Stage =1 (in-process orchestration failed): re-run from Stage 2 (`write_env`, `patch_*`, `agent_model.save` all idempotent).
- Stage ≥5: rerun 4–5 (both idempotent).
- Stale sidecar (>24h): warn + ignore + start fresh.

---

## Section 7 — Error UX (per row)

| Scenario | User sees | Cleanup | Resume? |
|---|---|---|---|
| Source path doesn't exist | Inline retry | none | yes |
| Source missing `distribution.yaml` | Inline retry | none | yes |
| Git URL unreachable | `git ls-remote` error tail, retry | none | yes |
| Profile collision (legacy/Hermes + user data) | T4 picker → `reconfigure` | none | yes |
| Profile collision (non-Hermes dir, no `config.yaml`) | Picker, default Abort, confirm required | none until confirmed | yes |
| `hermes profile install` non-zero | Tail-scan, show line + `[r/k/Enter]` prompt | `rollback()` if `r` (refused if user data) | yes |
| Hermes half-populated profile | `inspect_profile` detects; rollback path same | conditional rollback | yes |
| In-process orchestration exception | Traceback last 20 lines, rollback prompt | conditional rollback | yes |
| Plugin enable fails | Warn + advisory print | none | n/a |
| Mailbox CLI missing | Stage 5 prints install hint, return success-with-warning | none | n/a |
| SIGINT mid-flow | Signal handler restores termios + cursor, writes sidecar, prints resume hint | terminal restored | yes |
| Non-TTY (CI w/o `--headless`) | `run_wizard` dispatches to fallback; closed stdin aborts exit 11 | none | n/a |
| Reconfigure on non-warroom profile | T4 detects via `has_warroom_setup`; abort with hint | none | n/a |

---

## Section 8 — Existing-profile detection (A6/F2)

Algorithm (`inspect_profile`):

1. Path doesn't exist → strategy `proceed`.
2. `(path / "config.yaml").exists()` → Hermes-managed. (Was `distribution.yaml`; **changed** because legacy Hermes profiles lack `distribution.yaml`.)
3. Hermes-managed AND `(path / "warroom_setup/__init__.py").exists()` → AWR-template profile.
   - `local/agent.json`, `local/.warroom-setup.json`, or `local/persona/` non-empty → `has_user_data=True`. Strategy `reconfigure` (skip Stage 1; rerun in-process).
   - Empty → strategy `proceed`.
4. Hermes-managed but NOT AWR-template → strategy `abort` ("profile exists from a different distribution").
5. NOT Hermes-managed (no `config.yaml`) → strategy `confirm-overwrite`. UI default cursor on Abort.

Rollback hard-invariant (A9) applies regardless of strategy: re-inspect; refuse `rmtree` if `has_user_data=True`.

---

## Section 9 — Tests

Per-module unit coverage: precheck 8, launcher 5, substrate drift 4, subprocess + masked 10, profile_detect 10, TUI 13, execute 13, sidecar 8, rollback 6, headless 7, sanitization 5, uninstall 5. Plus 7 integration gated on `@pytest.mark.integration` and `--runintegration`.

Manual smoke (`SMOKE.md`): operator-driven, two profiles (`alpha-sh` + `beta-sh`) installed via TUI; both meet on board `shared` per `mailbox ps`. PR description references smoke completion.

---

## Section 10 — Sanitization audit

Zero employer strings (TwelveLabs / twelve labs / @twelvelabs / tl-branding) across installer source, tests, docs. All examples use `alpha-sh` / `beta-sh` / `shared`. `install.log` scanned for token-shaped patterns. Sidecar schema explicitly excludes `SECRET_IDS`. Installer imports restricted to stdlib + `_substrate.*`.

---

## Section 11 — Risks (top 5) with mitigations

1. **In-process import of `warroom_setup` from `<profile>/`.** Sys.path[0] insert after Stage 1. If Stage 1 left a corrupt profile, may pick up stale copy. Mitigation: verify `warroom_setup/__init__.py` exists post-Stage 1; on `ImportError`, treat as Stage 1 failure + rollback prompt.
2. **Termios restoration across signal boundary.** Module-global captured at raw-mode entry; SIGINT handler restores. Mitigation: pexpect-based test; `_emergency_restore` always re-issues cursor + known-good `tcsetattr`.
3. **Sub-300s timeout for slow git clones.** Mitigation: `--stage-timeout` operator-tunable; default 300s; verbose mode shows cloning progress.
4. **Substrate drift maintenance burden.** Byte-equality breaks on PRs touching `warroom_setup/render.py` etc. Mitigation: Makefile pre-test hook auto-syncs; CONTRIBUTING.md documents.
5. **`~/.claude/settings.json` mutation surprise.** `enroll.bootstrap` invokes `coordination/install.py` which writes there. Mitigation: confirm screen lists side-effect (K11); README documents; uninstall warns it's not removed.

Time budget: 5–10 min interactive, 60–120s headless.

---

## Section 12 — Pre-flight checks (T0's 8 verifications)

1. Python ≥3.9 — `sys.version_info >= (3, 9)`.
2. `hermes` on PATH — `shutil.which("hermes")`.
3. `hermes --version` ≥ 0.12 — robust regex parse (K15); unparseable → warn-and-proceed.
4. `hermes profile install --help` — confirms `--name --alias --force -y` exist.
5. `hermes plugins enable --help` — confirms `name` positional + stores `plugins_enable_has_yes: bool` (A8/F1).
6. POSIX terminal support — `import termios, tty`; hard-fail on Windows with hint.
7. `~/.hermes/profiles/` writable — probe file.
8. Substrate imports under PYTHONPATH — subprocess test (K1/F4).

`git` precheck only when `--source` is a URL (K23).

All outcomes written to `template/docs/installer-preflight.md`.

---

## Definition of Done (10 gates)

1. `pytest template/tests/test_installer_*.py -v` → 97 unit tests passed.
2. `pytest template/tests/test_installer_e2e.py -v --runintegration` → 7 integration passed.
3. Substrate drift test passes (byte-equality across 7 vendored files).
4. `bash template/install.sh --help` exits 0 and lists all flags.
5. Manual SMOKE.md walkthrough completed: two profiles meet on board `shared` per `mailbox ps`.
6. `python3 template/scripts/sanitize_check.py` exits 0 with installer in scope.
7. Two-step path regression passes.
8. Uninstall round-trip passes.
9. No `installer-answers.json` or `.warroom-setup.json` artifacts under `template/`.
10. `template/docs/installer-preflight.md` exists with all 8 outcomes documented.

---

## Task dispatch order

```
T0  (pre-flight verification)           [blocks everything below]
T1  (launcher + skeleton)               [depends on T0]
T2  (substrate vendor + drift)          [depends on T1]
T3  (subprocess + masked prompt)        [depends on T1]   ──┐ parallel with T4
T4  (profile detect + collision)        [depends on T0]   ──┘
T5  (TUI orchestration)                 [depends on T2, T3, T4]
T6  (in-process orchestrator)           [depends on T3, T4, T5]
T7  (sidecar + resume)                  [depends on T5]   ──┐ parallel with T8, T11
T8  (rollback hard-invariant)           [depends on T4, T6]──┤
T11 (uninstall subcommand)              [depends on T4]   ──┘
T9  (headless mode)                     [depends on T6]
T10 (README + smoke + sanitization)     [depends on T1–T9, T11]
```

Critical path: T0 → T1 → T2 → T5 → T6 → T9 → T10. Wall-clock estimate: 2 days w/ full parallelism, 5–6 days serial.

---

## Base plan (pre-refutation)

I have enough ground truth. Producing the plan now.

# AWR Feature B — Interactive Installer (TUI): Implementation Plan

Date: 2026-06-08. Branch base: `awr-feature-c` (PR #3). Status: ready to dispatch.

---

## 1. Architecture summary

We ship a ccpkg-style TUI installer that collapses the four-command path (`hermes profile install` → `bash scripts/setup.sh` → `hermes plugins enable warroom-gate` → first chat session triggers enroll via `.env`) into a single end-to-end flow. The installer is a **self-contained Python module** that lives at `template/scripts/installer/awr_install.py` (no warroom_setup imports — it runs BEFORE warroom_setup is on the path), invoked via a one-line bash launcher `template/scripts/awr-install` and a repo-root convenience symlink at `<repo>/install.sh`. It vendors the *minimum* shared TUI substrate it needs: it copies (does not import) `template/warroom_setup/render.py`, `prompts.py`, `validators.py`, and `discord_walkthrough.py`/`slack_walkthrough.py` into a small `_substrate/` package shipped alongside it. This keeps the installer runnable from a fresh clone where no Hermes profile exists yet, while reusing the exact same termios renderer, validators, and walkthrough Step sequences that PR #2 already proved work. Post-install, after `hermes profile install` lands the template at `~/.hermes/profiles/<name>/`, the installer delegates the rest (channel-secret prompts, identity, model, board, mailbox enroll) to the already-tested `warroom setup` machinery via `python3 -m warroom_setup setup` with stdin-fed answers from the TUI session — no logic duplication. The user sees one continuous flow; under the hood we're stitching `hermes` + `warroom setup` + `hermes plugins enable` together with telemetry, progress lines, and atomic rollback. Existing two-step path stays intact and unmodified.

---

## 2. Where the installer lives + how it's invoked

**Options considered:**

- **(A) Bash launcher only.** Pros: zero install. Cons: TUI in bash is brutal; we'd re-implement raw-mode in shell. **Rejected.**
- **(B) Python module inside `warroom_setup/installer.py`.** Pros: shares code via import. Cons: package isn't on path until *after* `hermes profile install` runs — and the installer's job is to *do* that install. **Rejected (chicken-and-egg).**
- **(C) Self-contained Python script at repo root that imports nothing from warroom_setup.** Pros: works from a fresh clone, curl-pipe-able, no path tricks. Cons: must vendor the TUI substrate, risks drift from warroom_setup. **Recommended with mitigation.**
- **(D) Hybrid: thin launcher `template/scripts/awr-install` (bash) → `template/scripts/installer/awr_install.py` (self-contained) → vendored `_substrate/`.** Pros: of C plus a stable entry surface. **Recommended (this is C with a launcher).**

**Decision: D.** Concrete layout:

```
<repo>/install.sh                                  # symlink → template/scripts/awr-install
<repo>/template/scripts/awr-install                # bash launcher; resolves python3, sets PYTHONPATH, execs awr_install.py
<repo>/template/scripts/installer/
  __init__.py
  awr_install.py                                   # main TUI orchestrator
  subprocess_runner.py                             # capture-both-streams helper
  precheck.py                                      # python3 ≥3.9, hermes on PATH, source path resolves, profile name free
  rollback.py                                      # uninstall on partial failure
  _substrate/
    __init__.py
    render.py                                      # COPY of warroom_setup/render.py (drift check via T8)
    prompts.py                                     # COPY of warroom_setup/prompts.py
    state.py                                       # COPY of warroom_setup/state.py
    selectables.py                                 # COPY (Stage/Entry/TextField dataclasses only)
    validators.py                                  # COPY of warroom_setup/validators.py
    discord_walkthrough.py                         # COPY (Step sequence + run_discord_walkthrough)
    slack_walkthrough.py                           # COPY
```

**Drift mitigation:** T8 ships `template/tests/test_installer_substrate_no_drift.py` which `filecmp.cmp`'s each `_substrate/<f>` against its warroom_setup counterpart and fails if they diverge. CI catches drift on every PR. Refresh tool: `template/scripts/installer/sync_substrate.sh` (one-shot rsync used by maintainers; not invoked at runtime).

**Why not a package install via `pip install -e .`?** Because the installer is the on-ramp; we cannot assume the user has Python packaging tooling configured beyond `python3`. Stdlib-only, copy-don't-import keeps the user's entry friction at "run one command."

**Invocation surface:**

```sh
# Local dev:
bash <repo>/install.sh

# Via curl (when published):
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | bash

# With explicit source path:
bash install.sh --source /path/to/template

# Headless (CI smoke):
bash install.sh --headless --name alpha-sh --board shared --no-channels
```

`awr_install.py` is also importable as `python3 -m installer.awr_install` for testability (T1–T6 unit tests use this).

---

## 3. TUI flow (numbered, end-to-end)

The TUI uses `render._raw_mode_loop` for toggle pickers and `prompts.collect`/`prompt_secret` for free-text/secrets — identical interaction model to `warroom setup` so muscle memory transfers.

1. **Title screen** (cleared, branded): "AWR Installer — interactive setup. Esc anywhere to abort."
2. **Pre-flight panel** (auto, ~1s): `python3 ≥3.9`, `hermes` on PATH (`shutil.which`), git installed (if source is git URL), `~/.hermes/profiles/` writable. Each line prefixed `[ok]` / `[fail]`. Any fail → abort with remediation hint, exit 10.
3. **Source path prompt.** Default = directory containing the launcher (resolved via `Path(__file__).resolve().parents[3]`). Validator: directory exists AND contains `distribution.yaml` (per Inv2 — Hermes refuses otherwise). If git URL: defer validation to step 9.
4. **Profile name prompt.** Validator: `validators.valid_slug` (lowercase, leading letter, dashes ok). Collision check: `Path("~/.hermes/profiles/<name>").expanduser().exists()` → if exists, show three choices (raw-mode mini-picker): `[ ] keep existing (abort)` / `[ ] reconfigure (re-run setup only, skip install)` / `[x] overwrite (use --force; see §8 for distribution.yaml detection)`. Default cursor on first option.
5. **Channels stage** — toggle picker, multi-select. Three entries: `[x] discord`, `[ ] slack`, `[ ] neither (skip channel setup)`. Defaults match shipped `selectables.TOGGLES`. Esc-back returns to step 4.
6. **Discord bot walkthrough** (only if `channels.discord` selected). Inline: for each `Step` in `discord_walkthrough.WALKTHROUGH_STEPS`, clear screen, render `step.n`/`step.title`/`step.body_lines`, then if `step.prompt_label` is present, prompt with `prompt_secret` for token steps and `prompts._prompt_once` for IDs. Validators retry up to 3 times then offer skip-with-warning. **The driver is `run_discord_walkthrough(prompts_callable, context="installer")`** — we pass an adapter that calls the appropriate raw-mode prompt. **Reuse: 100% of walkthrough content already exists.**
7. **Slack bot walkthrough** (only if `channels.slack` selected). Same pattern via `slack_walkthrough.run_slack_walkthrough`.
8. **Anthropic API key prompt.** `prompt_secret("Anthropic API key")`. Validator: starts with `sk-ant-` and length ≥40 (loose; we don't ping the API). Skip allowed with warning ".env will be partially filled; set ANTHROPIC_API_KEY manually before first chat."
9. **Model picker** — single-select raw-mode picker (radio-style implemented by select-all-clear-then-set on space). Entries: `(*) opus`, `( ) sonnet`. Maps to `model.opus`/`model.sonnet` toggles.
10. **War-room board + label.** Two text prompts. Board validator: `validators.valid_board_name`. Label validator: `valid_handle`. Defaults: board=`default`, label=profile name from step 4.
11. **Confirmation screen** (clear, summary):
    ```
    About to install:
      Source:        /path/to/template
      Profile name:  alpha-sh
      Target:        ~/.hermes/profiles/alpha-sh
      Channels:      discord
      Model:         opus
      Board / label: shared / alpha-sh
      Discord token: ******** (will write to .env)

    [ Enter Proceed ]   [ Esc Edit ]   [ q Abort ]
    ```
    Esc returns to step 3 (preserves all entered values via in-memory `InstallerAnswers`).
12. **Execute phase** — clear screen, switch to non-raw mode, stream progress lines (one per stage, ANSI-cleared in place):
    ```
    [1/5] hermes profile install ............................. ok (2.3s)
    [2/5] writing .env from collected secrets ................ ok
    [3/5] warroom setup (headless replay) .................... ok (1.1s)
    [4/5] hermes plugins enable warroom-gate ................. ok (0.4s)
    [5/5] cross-agent enroll (mailbox).......................skip — mailbox CLI not found (warn)
    ```
    Each stage logs to `~/.hermes/profiles/<name>/local/install.log`. A stage failure halts the pipeline, prints the captured stdout/stderr tail (last 20 lines), then offers `[ r Rollback ]` / `[ k Keep partial ]` / `[ Enter View full log ]`.
13. **Success summary** — clear:
    ```
    AWR ready.
      Activate: hermes -p alpha-sh chat
      Status:   hermes -p alpha-sh exec warroom enroll --status
      Logs:     ~/.hermes/profiles/alpha-sh/local/install.log
    ```

---

## 4. Subprocess management

Three external commands: `hermes profile install`, `hermes plugins enable`, `python3 -m warroom_setup setup --yes`. All share these requirements:

- **Capture both streams.** Per Inv2, `hermes profile install` writes errors to stdout. Solution: `subprocess.Popen` with `stdout=PIPE, stderr=PIPE`, drained concurrently via two threads that append to a shared `collections.deque(maxlen=400)` of `(stream, line)` tuples. Final wait() returns; we get a unified ordered tail. Implemented in `subprocess_runner.run_capturing(cmd, *, cwd, env, timeout) -> CommandResult` with fields `returncode`, `lines: list[tuple[str, str]]`, `duration_s`.
- **No TUI pollution.** Before exec, we restore the cursor (`\x1b[?25h`) and exit raw mode (termios.tcsetattr restore from the saved attrs the renderer captured). Output lives in a dedicated "Execute phase" region; we never inter-mix subprocess output with TUI chrome.
- **Non-interactive guarantee.** All three subprocs run with stdin closed (`subprocess.DEVNULL`) and `-y` / `--yes` flags where they exist. `hermes profile install` invoked as `hermes profile install <SRC> --name <N> --alias --force -y` (Inv2 contract). Argparse rejects unknown flags with exit 2 — we treat that as a hard error with the message "your `hermes` is too old (need ≥0.12); run `pipx upgrade hermes-agent`".
- **Timeout.** 120s per stage default; configurable via `--stage-timeout`. On timeout: send SIGTERM, wait 5s, SIGKILL. Mark stage `timeout` and trigger rollback prompt.
- **Failure signal detection.** Inv2 says hermes errors print to stdout, not stderr — so returncode is the only reliable signal. Exit 0 = success; non-zero = fail. Additionally, we tail-scan the last 50 lines for `DistributionError`/`ValueError`/`error:` to surface the most likely root-cause line in the failure message.
- **Environment.** Subprocs inherit `os.environ` except we strip `PYTHONPATH` (so `hermes` doesn't pick up our `_substrate/`) and we explicitly set `PYTHONUNBUFFERED=1` so progress lines stream live.

---

## 5. Task breakdown (T1..T10)

### T1 — Launcher + module skeleton + pre-flight (~140 LoC + 90 LoC tests)

**Create:**
- `<repo>/install.sh` (symlink) → `template/scripts/awr-install` (bash, 12 lines: resolve python3, set PYTHONPATH to `installer/`, exec).
- `template/scripts/installer/__init__.py` (empty).
- `template/scripts/installer/awr_install.py` — `def main(argv=None) -> int:` skeleton; `argparse` with `--source`, `--name`, `--headless`, `--board`, `--label`, `--no-channels`, `--stage-timeout`, `--force`, `--dry-run`.
- `template/scripts/installer/precheck.py` — `def run_prechecks(env=None) -> list[PrecheckResult]` returning `[(name, ok, hint)]` tuples for python_version / hermes_on_path / hermes_min_version / profiles_dir_writable / git_if_url.
- `template/tests/test_installer_precheck.py`.

**Tests:**
- `test_precheck_passes_on_clean_env`
- `test_precheck_fails_when_hermes_missing` (monkeypatch `shutil.which`)
- `test_precheck_fails_on_old_hermes` (mock `hermes --version` returning `0.10.0`)
- `test_precheck_fails_when_profiles_dir_unwritable` (chmod 0o500 on tmp HOME)
- `test_launcher_resolves_python3_and_pythonpath` — invoke `awr-install --help`, assert exit 0 + help on stdout.

**Acceptance:** `pytest template/tests/test_installer_precheck.py -v` shows 5 passed; `bash template/scripts/awr-install --help` exits 0.

**Dependencies:** none.

### T2 — Vendor substrate + drift guard (~30 LoC + 60 LoC tests)

**Create:** `template/scripts/installer/_substrate/` populated by `template/scripts/installer/sync_substrate.sh` (a maintenance shell script; not runtime). Initial sync: copy `render.py`, `prompts.py`, `state.py`, `selectables.py`, `validators.py`, `discord_walkthrough.py`, `slack_walkthrough.py` from `template/warroom_setup/` to `_substrate/`.

**Create:** `template/tests/test_installer_substrate_no_drift.py`:
- `test_substrate_files_byte_identical_to_warroom_setup` — `filecmp.cmp(f1, f2, shallow=False)` per file.
- `test_substrate_imports_cleanly_in_isolation` — `subprocess.run([python3, "-c", "import _substrate.render"], cwd=installer_dir)` exits 0.

**Acceptance:** `pytest template/tests/test_installer_substrate_no_drift.py -v` shows 2 passed.

**Dependencies:** T1.

### T3 — Subprocess runner + execute-phase progress renderer (~160 LoC + 100 LoC tests)

**Create:**
- `template/scripts/installer/subprocess_runner.py`:
  - `@dataclass CommandResult: returncode, lines: list[tuple[str,str]], duration_s, timed_out`
  - `def run_capturing(cmd: list[str], *, cwd=None, env=None, timeout=120.0) -> CommandResult` — Popen + 2 reader threads + join with timeout + SIGTERM/SIGKILL escalation.
  - `def tail_for_error_line(lines, patterns=("DistributionError", "ValueError", "error:")) -> str | None`
- `template/scripts/installer/progress.py`:
  - `class StageRunner` — context manager that renders `[N/M] <label> .... ok (Ts)` with in-place ANSI clear via `\r\x1b[K`.

**Tests** (`template/tests/test_installer_subprocess.py`):
- `test_run_capturing_collects_stdout_and_stderr_in_order`
- `test_run_capturing_returns_nonzero_on_command_failure`
- `test_run_capturing_terminates_on_timeout` (use `sleep 30` with timeout=0.5)
- `test_tail_for_error_line_finds_distribution_error`
- `test_tail_for_error_line_returns_none_when_clean`
- `test_stage_runner_renders_ok_status` (capture stdout)
- `test_stage_runner_renders_fail_status_on_exception`

**Acceptance:** `pytest template/tests/test_installer_subprocess.py -v` shows 7 passed.

**Dependencies:** T1.

### T4 — Existing-profile detection + collision UI (~80 LoC + 80 LoC tests)

**Create:** `template/scripts/installer/profile_detect.py`:
- `@dataclass ProfileState: exists: bool, is_hermes_managed: bool, distribution_yaml_present: bool, has_user_data: bool, path: Path`
- `def inspect_profile(profiles_root: Path, name: str) -> ProfileState` — checks:
  1. Does `<profiles_root>/<name>/` exist?
  2. Does `<profiles_root>/<name>/distribution.yaml` exist? (presence = Hermes-managed)
  3. Does `<profiles_root>/<name>/local/` contain non-empty `agent.json`, `answers.json`, OR `persona/`? (presence = user data)
- `def collision_strategy(state: ProfileState, *, force: bool) -> Literal["proceed", "reconfigure", "abort", "confirm-overwrite"]`:
  - `not exists` → `proceed`
  - `exists AND distribution_yaml_present AND not has_user_data AND force` → `proceed` (true overwrite of a clean install)
  - `exists AND distribution_yaml_present AND has_user_data` → `reconfigure` (skip install; run setup only; preserves user data)
  - `exists AND not distribution_yaml_present` → `confirm-overwrite` (this is the dangerous case from Inv2 §2: a manual non-Hermes dir; never silently pass `--force -y`)
  - else → `abort`

**Tests** (`template/tests/test_installer_profile_detect.py`):
- `test_inspect_reports_missing_when_dir_absent`
- `test_inspect_detects_hermes_managed_via_distribution_yaml`
- `test_inspect_detects_user_data_in_local_dir`
- `test_collision_strategy_proceeds_on_clean_target`
- `test_collision_strategy_reconfigures_when_user_data_present`
- `test_collision_strategy_demands_confirm_for_non_hermes_dir` — critical safety
- `test_collision_strategy_aborts_without_force`

**Acceptance:** `pytest template/tests/test_installer_profile_detect.py -v` shows 7 passed.

**Dependencies:** T1.

### T5 — TUI orchestration: stages + answer model + raw-mode wiring (~280 LoC + 140 LoC tests)

**Create:** `template/scripts/installer/awr_install.py` main flow:
- `@dataclass InstallerAnswers: source: str, profile_name: str, channels: set[str], discord_creds: DiscordCreds | None, slack_creds: SlackCreds | None, anthropic_key: str, model: str, board: str, label: str`
- `def run_tui(args) -> InstallerAnswers` — orchestrates steps 1–11 of §3 using `_substrate.render.run_wizard` for togglers and `_substrate.prompts._prompt_once` / `prompt_secret` for text. Each stage is its own function (`_stage_source`, `_stage_name`, `_stage_channels`, `_stage_discord`, `_stage_slack`, `_stage_identity`, `_stage_model`, `_stage_board`, `_stage_confirm`) so each can be unit-tested with scripted stdin/stdout streams.
- `def execute(answers: InstallerAnswers, *, dry_run: bool) -> int` — orchestrates steps 12–13 (delegated to T6).

**Tests** (`template/tests/test_installer_tui.py`):
- `test_tui_source_stage_validates_distribution_yaml_present`
- `test_tui_name_stage_rejects_invalid_slug`
- `test_tui_channels_stage_returns_selected_set`
- `test_tui_model_stage_returns_single_selection`
- `test_tui_confirm_back_returns_to_source_stage` — Esc loop
- `test_tui_headless_mode_skips_prompts_and_uses_args` — `--headless --name X --board Y --no-channels`
- `test_tui_collects_full_answer_set_end_to_end` — scripted stdin sequence

**Acceptance:** `pytest template/tests/test_installer_tui.py -v` shows 7 passed.

**Dependencies:** T2, T3, T4.

### T6 — Execute phase: chain install/setup/plugin/enroll (~220 LoC + 160 LoC tests)

**Modify:** `template/scripts/installer/awr_install.py` — implement `execute()`:
- Stage 1: `hermes profile install <source> --name <name> --alias --force -y` via `run_capturing`. On non-zero, scan tail for error, print, prompt rollback.
- Stage 2: write `~/.hermes/profiles/<name>/.env` from collected secrets directly (we already have them — no need to re-prompt via `warroom setup`). Reuse `_substrate.setup.write_env` semantics by inlining a tiny version (only ~30 lines) OR — simpler — write `<profile>/local/installer-answers.json` with the toggle+text answers in the same shape `warroom_setup.answers.Answers` expects, then let `warroom setup --yes` replay them.
- Stage 3: `python3 -m warroom_setup setup --yes` with `cwd=<profile>`, `PYTHONPATH=<profile>`. This re-uses 100% of existing setup logic including `enroll.bootstrap`.
- Stage 4: `hermes plugins enable warroom-gate -y` (best-effort; warn on fail, don't abort).
- Stage 5: `python3 -m warroom_setup enroll --status` — captures + parses JSON; if `status=cli-not-found`, print install-mailbox hint from §9 README; if `daemon_reachable=false`, note that first chat will spawn it.

**Create:** `template/scripts/installer/rollback.py`:
- `def rollback(profile_path: Path, *, stages_completed: list[str]) -> None` — `shutil.rmtree(profile_path)` if `stages_completed` includes `"hermes_install"` (we created it; safe to remove). Skip if `confirm-overwrite` strategy was chosen (we'd be deleting user data we didn't create).

**Tests** (`template/tests/test_installer_execute.py`):
- `test_execute_dry_run_runs_no_subprocesses`
- `test_execute_stage_1_calls_hermes_with_correct_args`
- `test_execute_writes_installer_answers_json_before_setup`
- `test_execute_setup_stage_invokes_warroom_module`
- `test_execute_plugin_enable_failure_does_not_abort` — warn-and-continue
- `test_execute_enroll_status_reports_cli_not_found_nicely`
- `test_execute_rollback_removes_profile_on_stage_1_failure`
- `test_execute_rollback_preserves_profile_on_confirm_overwrite_strategy`

**Acceptance:** `pytest template/tests/test_installer_execute.py -v` shows 8 passed.

**Dependencies:** T3, T4, T5.

### T7 — Sidecar state + resume (~80 LoC + 70 LoC tests)

Mid-flow state lives at `~/.hermes/.awr-install-state.json` (NOT inside `<profile>/` because profile may not exist yet). Schema: `{"started_at", "profile_name", "stage", "answers": {... minus secrets ...}, "completed_stages": [...]}`. Secrets are NEVER persisted; only their *presence* (`"anthropic_key_set": true`) is recorded so resume can prompt only for missing items.

**Create:** `template/scripts/installer/sidecar_state.py`:
- `def write_sidecar(path, payload) -> None` — atomic via `_substrate.state.save_state`.
- `def read_sidecar(path) -> dict | None`.
- `def cleanup_sidecar(path) -> None` — called on full success or explicit abort.

On startup, `awr_install.main` checks for an existing sidecar. If found and not expired (<24h), prompts: `[ r Resume ]` / `[ s Start fresh (discard) ]`. Resume jumps to the recorded stage with prior answers pre-filled (secrets must be re-entered).

**Tests** (`template/tests/test_installer_sidecar.py`):
- `test_sidecar_persists_non_secret_answers_only` — assert `anthropic_key` NOT in JSON
- `test_sidecar_records_stage_progression`
- `test_sidecar_resume_skips_completed_stages`
- `test_sidecar_expired_after_24h_is_ignored`
- `test_sidecar_cleanup_on_success`

**Acceptance:** `pytest template/tests/test_installer_sidecar.py -v` shows 5 passed.

**Dependencies:** T5.

### T8 — Headless mode + smoke harness (~100 LoC + 60 LoC tests)

`--headless` mode replays from CLI args + env without touching stdin (relies on argparse). Required args in headless: `--name`, `--source` (or autodetected if running inside repo), `--board`, `--label`. Optional: `--no-channels` (skip walkthroughs entirely) or `--discord-token-env VAR` / `--slack-bot-token-env VAR` / `--slack-app-token-env VAR` / `--anthropic-key-env VAR` (reads secret from env var; never from CLI).

**Tests** (`template/tests/test_installer_headless.py`):
- `test_headless_requires_name_when_no_sidecar`
- `test_headless_reads_secrets_from_env_vars_when_specified`
- `test_headless_aborts_on_collision_without_force`
- `test_headless_runs_no_prompts` — `subprocess.run` with stdin=DEVNULL completes without hanging.

**Acceptance:** `pytest template/tests/test_installer_headless.py -v` shows 4 passed.

**Dependencies:** T6.

### T9 — README + manual smoke + sanitization (~80 LoC docs + 30 LoC sanitize check)

**Modify:** `template/README.md` — new H2 "Interactive install (recommended)" above the existing "Install" + "Personalize" sections, with one-line: `bash install.sh`. Existing sections become "Manual two-step install (power users / CI)".

**Create:** `template/scripts/installer/SMOKE.md` — manual smoke recipe (~30 lines):

```
1. From a fresh clone: bash install.sh
2. Walk the TUI: source=. , name=alpha-sh, channels=discord, real Discord token,
   anthropic key, model=opus, board=shared, label=alpha-sh.
3. After "AWR ready": hermes -p alpha-sh chat
4. In Claude: `mailbox ps` shows alpha-sh on board "shared".
5. Repeat from a SECOND clone with name=beta-sh; both meet on board "shared".
6. Cleanup: rm -rf ~/.hermes/profiles/{alpha-sh,beta-sh} ~/.hermes/.awr-install-state.json
```

**Tests** (`template/tests/test_installer_sanitization.py`):
- `test_installer_module_contains_no_employer_strings` — grep `("twelvelabs", "twelve labs", "@twelvelabs")` against all installer source files; assert 0 hits.
- `test_smoke_doc_uses_neutral_handles` — assert `alpha-sh` / `beta-sh` present; assert no real-name handle patterns.

**Modify:** `template/SANITIZATION.md` — add: "Installer sidecar state at `~/.hermes/.awr-install-state.json` MUST NOT contain secrets. Audited via T7's `test_sidecar_persists_non_secret_answers_only`."

**Acceptance:** `pytest template/tests/test_installer_sanitization.py -v` shows 2 passed; manual smoke per SMOKE.md succeeds end-to-end.

**Dependencies:** T1–T8.

### T10 — Integration: TUI shell scenarios end-to-end (~180 LoC test)

**Create:** `template/tests/test_installer_e2e.py` — marker `@pytest.mark.integration`. Skip if no `hermes` on PATH.

Test scenarios:
- `test_full_install_happy_path_neutral_profile` — drives the installer via `subprocess.Popen` with a scripted stdin (the same approach `test_setup.py` uses), then asserts `~/.hermes/profiles/<tmp-name>/config.yaml` contains the warroom + mailbox blocks.
- `test_install_rollback_on_simulated_hermes_failure` — monkeypatch `hermes` to a shim that exits 1; assert profile dir absent after rollback.
- `test_resume_from_sidecar_after_simulated_sigint` — start installer, send SIGINT after channels stage, restart, choose Resume; assert flow continues from correct stage.

**Acceptance:** `pytest template/tests/test_installer_e2e.py -v --runintegration` shows 3 passed.

**Dependencies:** T9.

---

## 6. State + idempotency

**During the flow:**
- `~/.hermes/.awr-install-state.json` — non-secret sidecar (see T7). Atomic write, 0600 perms, 24h TTL.
- `~/.hermes/profiles/<name>/local/install.log` — append-only timestamped lines per stage (created during stage 1).
- `~/.hermes/profiles/<name>/local/installer-answers.json` — bridge from TUI answers to `warroom setup --yes` replay; same schema as `answers_mod.Answers`. Atomic via `_substrate.state.save_state`.

**Cleanup:**
- Sidecar deleted on full success (T7 `cleanup_sidecar`) and on explicit `[ q Abort ]`.
- `installer-answers.json` stays in the profile (overwritten on `--reconfigure`).
- `install.log` stays for forensics.

**Resume semantics:**
- If sidecar present at startup with stage `< 3` (pre-hermes-install): re-prompt from recorded stage; profile not yet created.
- If sidecar present at stage `≥ 3` (post-hermes-install): re-run `warroom setup --yes` against existing `installer-answers.json` (idempotent: existing PR #2/#3 setup code handles this).
- Stale sidecar (>24h): warn + ignore + start fresh.

---

## 7. Error UX

| Scenario | Surfacing | Cleanup | Resume? |
|---|---|---|---|
| Source path missing | TUI stage 3 inline error "directory does not exist", retry | none | yes (loop) |
| Source missing `distribution.yaml` | Inline "no distribution.yaml at root; Hermes refuses (see Inv2)", retry | none | yes (loop) |
| Profile collision (Hermes-managed + user data) | T4 collision picker → `reconfigure` strategy | none | yes |
| Profile collision (non-Hermes dir) | T4 confirm-overwrite picker; default cursor on Abort | none (until user confirms) | yes |
| Git source clone fails | Stage 1 captures `git clone` exit, shows last 20 lines of stderr | sidecar preserved; profile not created | yes |
| `hermes profile install` non-zero | Tail-scan for `DistributionError` / `ValueError`; show that line + rollback prompt | `shutil.rmtree(profile)` if partially populated | yes (re-runs cleanly) |
| `hermes profile install` half-populated (post-`_bootstrap_user_dirs`) | Per Inv2, target is left half-populated; we detect via T4 `inspect_profile` after fail; rollback is `shutil.rmtree` | yes | yes |
| `warroom setup --yes` fails | Show last 20 lines + rollback prompt; `local/install.log` recorded | optional rollback | yes |
| `hermes plugins enable warroom-gate` fails | Warn, continue (non-fatal); user can run manually | none | n/a |
| Mailbox CLI missing at enroll | Stage 5 prints install-mailbox hint pointing at `coordination/install.py` and README "Installing the mailbox runtime" | none | n/a (success with warning) |
| SIGINT mid-flow | Signal handler restores terminal (`tcsetattr` + `\x1b[?25h`), writes sidecar with current stage, prints "saved progress to ~/.hermes/.awr-install-state.json; run `bash install.sh` to resume" | terminal restored | yes |
| Terminal not a TTY (CI without `--headless`) | Detect via `_substrate.render._is_tty`; fall back to numbered prompts via `_numbered_fallback`; if still fails, error "use --headless for non-interactive" | none | n/a |

---

## 8. Existing-profile detection (per Inv2 §2)

The risk: an operator manually built `~/.hermes/profiles/<name>/` for unrelated reasons, or copied files there outside Hermes. Passing `--force -y` to `hermes profile install` would silently overwrite it. Specced in T4 above; the load-bearing test is `test_collision_strategy_demands_confirm_for_non_hermes_dir`.

**Detection algorithm** (`inspect_profile` in T4):

1. `path = ~/.hermes/profiles/<name>`
2. If `not path.exists()` → state `(exists=False)`, strategy `proceed`.
3. If `path.exists()` and `(path / "distribution.yaml").exists()` → Hermes-managed.
4. If `path.exists()` and not (3) → non-Hermes dir; this is the danger case. Strategy `confirm-overwrite`. UI default cursor on Abort (not Overwrite). To proceed, operator must select Overwrite explicitly AND we additionally pass `--force` to hermes.
5. Within (3), inspect `path / "local/"` for `agent.json`, `answers.json`, or non-empty `persona/`. If present → user data exists. Strategy `reconfigure` (skip stage 1, run setup-only). If absent → strategy `proceed` (clean Hermes install with no personalization yet; safe to overwrite).

**Why the distinction matters:** Hermes `--force -y` on a non-distribution dir corrupts unrelated work; Hermes `--force -y` on a personalized Hermes profile wipes the user's secrets and persona edits (which live under `local/`, in `USER_OWNED_EXCLUDE` — Hermes itself protects them, but a full `rmtree` from rollback would not). We never `rmtree` on `confirm-overwrite` rollback; only on `proceed` (we own the dir we created).

---

## 9. Tests

**Unit (all mock external commands):**
- T1: 5 precheck tests
- T2: 2 substrate drift tests
- T3: 7 subprocess + progress tests
- T4: 7 profile-detect + collision tests
- T5: 7 TUI stage tests
- T6: 8 execute-chain tests
- T7: 5 sidecar tests
- T8: 4 headless tests
- T9: 2 sanitization tests

Total: **47 unit tests**, all hermetic.

**Integration (T10, marker `@pytest.mark.integration`):** 3 e2e tests that invoke real `hermes` against a tmp `~/.hermes` (HOME overridden). Skipped in default CI; gated on `--runintegration`.

**Manual smoke** (`template/scripts/installer/SMOKE.md`): operator-driven, 6-step script that proves two profiles installed via the TUI meet on the same mailbox board. The operator runs it on their workstation before merge; PR description must reference its completion.

---

## 10. Sanitization audit

Confirmed: no employer name, no internal hostnames, no specific tokens anywhere in plan text, proposed code, tests, or docs. All examples use `alpha-sh` / `beta-sh` / `shared` (matching Feature C convention). T9's `test_installer_module_contains_no_employer_strings` runs as part of the existing sanitize_check pipeline (`template/scripts/sanitize_check.py` extended to scan `template/scripts/installer/`).

---

## 11. Risks / unknowns (top 5)

1. **Termios restoration after SIGINT.** Python's `tty.setraw` + `termios.tcsetattr` restore in `finally` works in the existing `_raw_mode_loop`, but a SIGINT during a subprocess in the execute phase could leave the terminal in raw mode if we're between contexts. **Mitigation:** install a `signal.signal(SIGINT, _restore_and_save_sidecar)` handler at `main()` entry that runs even when not inside `_raw_mode_loop`'s `finally`. Verify in T10 SIGINT test.

2. **`hermes profile install` exit-code contract is partially inferred.** Inv2 says exit 0 success, 1 distribution/value error, 2 argparse — but we haven't independently verified the half-populated-profile threshold (`_bootstrap_user_dirs`) is the actual boundary. **Mitigation:** T4's `inspect_profile` runs unconditionally after stage 1 failure to detect what actually landed, rather than trusting the exit code's implications.

3. **Sidecar location collision.** `~/.hermes/.awr-install-state.json` lives in Hermes' config dir. If Hermes adds a config file with a similar prefix this could be confusing. **Mitigation:** name uses `.awr-` prefix; T7 test asserts no collision; document in SANITIZATION.md.

4. **`hermes plugins enable warroom-gate` interface.** We assume `-y` flag exists; if not, plugin enable becomes interactive and we'd hang. **Mitigation:** T1 precheck includes `hermes plugins enable --help` parse; if `-y` not present, fall back to writing the plugin enable directly into `<profile>/plugins/enabled.txt` (or whatever Hermes uses) and warn.

5. **TUI portability beyond macOS.** `termios` works on Linux; `discord_walkthrough` and `slack_walkthrough` URLs are platform-neutral. Untested on WSL. **Mitigation:** T9 SMOKE.md notes "Tested on macOS + Linux. WSL untested — file an issue."

---

## 12. Pre-flight check

Before T1 begins:

1. **Verify the substrate is copyable cleanly.** Run `python3 -c "import warroom_setup.render"` from a profile dir; confirm no relative imports that would break in `_substrate/`. (`render.py` imports `from .selectables` and `from .state` — both also vendored; OK. `prompts.py` imports `from .selectables` — OK. `discord_walkthrough.py` imports `from . import validators` — OK.)

2. **Verify `hermes profile install --help`** lists `--name`, `--alias`, `--force`, `-y` exactly as Inv2 documents. If the local Hermes version differs, T1's `hermes_min_version` precheck threshold must be adjusted.

3. **Verify `hermes plugins enable --help`** supports `-y` (see Risk #4). If not, plan adjustment to T6 stage 4 needed before coding.

4. **Verify `python3 -m warroom_setup setup --yes`** runs to completion against a fixture profile when `installer-answers.json` is pre-populated. (This is the contract T6 stage 3 depends on; if `warroom setup --yes` doesn't fully replay from `answers.json`, T6 stage 3 must instead pipe answers via stdin or write `.env` directly.)

5. **Verify file `template/scripts/awr-install`** can be created as executable (`chmod +x`) and is portable across macOS/Linux (`#!/usr/bin/env bash`).

All five resolved before T1 starts. Document outcomes in `template/docs/installer-preflight.md` (sibling to Feature C's `runtime-preflight.md`).

Plan path: /Users/aahil/Documents/Code/agentic-war-room/docs/superpowers/plans/2026-06-08-awr-feature-b.md (to be written; this output is the plan body — caller will persist it).

---

## Adversarial review — Correctness

I have enough ground truth. Producing the review.

---

# Adversarial review — Feature B plan, CORRECTNESS

## BLOCKER findings

**1. BLOCKER — `warroom setup --yes` does NOT work as a headless replay on a fresh profile (§5 T6 stage 3).**
Plan T6 stage 3: "`python3 -m warroom_setup setup --yes` with `cwd=<profile>`, `PYTHONPATH=<profile>`. This re-uses 100% of existing setup logic." Inspecting `setup.py:349-389`: when `yes=True` AND `prior_ident is None` (which is the case for a freshly hermes-installed profile, since `local/agent.json` does not yet exist), the code *falls through* to `prompts.collect(selectables.TEXT_FIELDS, ...)` reading from stdin. With `stdin=DEVNULL` (mandated by §4 "stdin closed"), `_prompt_once` hits EOF immediately, `collect` returns `{}`, and `run_setup` proceeds with empty `agent_name`/`handle`/`display_name` — producing a degenerate `agent.json` with blank strings and an unusable profile. The .env-writing step also writes nothing because `env_values = {k: v for k, v in values.items() if k in ENV_FIELD_IDS and v}` is empty.
**Fix:** Either (a) before calling `warroom setup --yes`, write `local/agent.json` directly from the installer's collected `InstallerAnswers` (using `agent_model.AgentIdentity.save`) and write `<profile>/.env` directly using `setup.write_env`, then call `warroom setup --yes --sync` (which only recompiles SOUL.md and never prompts), OR (b) extend `cli.py`/`run_setup` to accept a pre-built answers source file via flag (e.g., `--from-answers <path>`) before T6 calls it. Option (a) is materially less work and avoids modifying the audited Feature C code path.

**2. BLOCKER — Wrong answers filename invalidates the "replay via warroom_setup.answers" plan (§5 T6).**
Plan: "write `<profile>/local/installer-answers.json` with the toggle+text answers in the same shape `warroom_setup.answers.Answers` expects, then let `warroom setup --yes` replay them." But `warroom_setup/answers.py:14` hard-codes `FILENAME = ".warroom-setup.json"`, and `setup._resolve_toggles` loads from `profile_root / "local" / answers_mod.FILENAME` exclusively. `installer-answers.json` is never read. Plan T6 also lists this exact filename in §6 as the "bridge from TUI to setup --yes replay" — same bug, twice.
**Fix:** Use the actual filename `.warroom-setup.json` (or, preferably, drop the bridge file entirely and write identity + .env directly per finding #1).

**3. BLOCKER — `hermes plugins enable` does not accept `-y` and is not profile-scoped in the planned invocation (§4, §5 T6 stage 4, §11 risk #4).**
Verified against installed `hermes 0.15.1` (the version on this machine): `hermes plugins enable --help` shows only `name` as a positional argument. No `-y`, no `--yes`. Plan command `hermes plugins enable warroom-gate -y` will exit 2 (argparse "unrecognized arguments"). Plan §11 risk #4 acknowledges the uncertainty but the spec still treats `-y` as present. Additionally, `hermes plugins enable warroom-gate` operates on the "sticky" / current profile — not the just-installed `<name>` — unless the global `hermes -p <name> plugins enable warroom-gate` form is used. (Top-level `-p` is accepted, verified by checking `hermes --help`.)
**Fix:** Use `hermes -p <name> plugins enable warroom-gate` (drop `-y`). Verify locally first; the command is already non-interactive, so the `-y` removal is harmless.

**4. BLOCKER — Path arithmetic for default source is off by one (§3 step 3, §2).**
Plan says default source resolves via `Path(__file__).resolve().parents[3]` from `awr_install.py`. With layout `template/scripts/installer/awr_install.py`: `parents[0]=installer`, `parents[1]=scripts`, `parents[2]=template`, `parents[3]=<repo>`. The Hermes-installable source (the directory with `distribution.yaml`) is `template/`, i.e. `parents[2]`, not `parents[3]`. Using `parents[3]` points at the repo root, which has no `distribution.yaml` (only `template/distribution.yaml` exists), so Hermes refuses with "no distribution.yaml at source root." Plan §3 step 3 also says "validator: directory exists AND contains `distribution.yaml`" — so the pre-validation would catch it before invocation, but then every default source attempt fails and the user must type the path manually.
**Fix:** Change to `parents[2]`. Add a unit test that asserts the default source resolves to a directory containing `distribution.yaml`.

**5. BLOCKER — `install.sh` symlink at repo root is invisible to users who install from the published distribution (§2).**
`template/scripts/publish.sh` runs `git subtree split --prefix=template`, producing a distribution whose root IS `template/`. A symlink at `<repo>/install.sh → template/scripts/awr-install` lives at the AWR repo root, NOT inside `template/`, so it's stripped when the distribution is published. The plan promises `bash install.sh` as the entry; that promise holds only for users who clone the *AWR development repo*, not for users who clone the published distribution or run `hermes profile install <git-url>`. The README rewrite in T9 telling users to "`bash install.sh`" will give wrong instructions to the majority of operators.
**Fix:** Place `install.sh` inside `template/` (e.g., `template/install.sh`) as a real file (not a symlink — `publish.sh` documents that it validates no symlinks during publish, per scripts/README.md line 18). The repo-root convenience launcher, if desired, becomes a real file at `<repo>/install.sh` that just `exec`s `template/install.sh`. The shipped distribution then has its own `install.sh` at its root.

---

## MAJOR findings

**6. MAJOR — `bootstrap()` signature in shared-core summary doesn't match reality (referenced indirectly in §5 T6 stage 5).**
The task prompt summary describes `bootstrap(profile_root, board, label, *, dry_run=False, env=None)` but `enroll.py:174` is positional: `def bootstrap(profile_root, board, label, dry_run=False, env=None)`. The plan never calls `bootstrap` directly (it goes through `warroom setup --yes` and `warroom enroll`), so this is upstream context confusion rather than a direct plan bug — but the plan inherits the false signature when describing reuse and would mislead future authors who try to call it with keyword-only semantics.
**Fix:** Plan body need not reference `bootstrap` signature; if it does, drop the `*,`.

**7. MAJOR — InstallerAnswers misses required identity fields (§5 T5).**
`InstallerAnswers: source, profile_name, channels, discord_creds, slack_creds, anthropic_key, model, board, label`. But `selectables.TEXT_FIELDS` requires `agent_name`, `display_name`, AND `handle` (separate from profile name) AND collects `DISCORD_ALLOWED_USERS` AND `warroom.min_confidence`. The plan also says "label defaults to profile name from step 4" — which corresponds to `warroom.label`, but does not collect the identity triple `(agent_name, display_name, handle)`. Without those, finding #1's fix (write `local/agent.json` directly) cannot succeed because the installer never collected `agent_name`/`display_name`.
**Fix:** Add stages for `agent_name` (defaults to `profile_name`), `display_name` (defaults to `agent_name`), `DISCORD_ALLOWED_USERS` (optional), and `warroom.min_confidence` (default 75 via `schema.clamp_pct`). Add corresponding fields to `InstallerAnswers`.

**8. MAJOR — "Single-select model picker via select-all-clear-then-set" doesn't match the renderer's mechanic (§3 step 9, §5 T5).**
Plan: "single-select raw-mode picker (radio-style implemented by select-all-clear-then-set on space)". The existing `_raw_mode_loop` (render.py:135-176) treats `space` as a toggle, `a` as select-all, `n` as select-none. There is no built-in radio semantic. Achieving "exactly one of opus/sonnet selected at all times" requires either (a) modifying the renderer (creates substrate drift, violates T2 byte-equality test) or (b) the installer running its own raw-mode loop that intercepts keys (essentially reimplementing the renderer). The plan says "100% reuse" but cannot deliver it for this stage.
**Fix:** Mirror the existing setup wizard's model handling: ship two independent toggle entries `model.opus` and `model.sonnet`, both selectable; downstream logic uses `setup.py:385` precedence (`sonnet if "model.sonnet" in selected and "model.opus" not in selected else "opus"`). No radio semantic needed.

**9. MAJOR — Substrate drift via `filecmp.cmp(..., shallow=False)` will trip on legitimate edits to warroom_setup (§5 T2).**
The drift test makes `_substrate/<f>` byte-identical to `warroom_setup/<f>` mandatory. Any PR that edits e.g. `validators.py` (which Feature C touched in PR #3) breaks the installer's drift test and forces a substrate refresh on every feature touching the substrate files. This is OK as a maintenance burden — but the plan also says "T8 ships drift check" and "Refresh tool: `sync_substrate.sh` (one-shot rsync used by maintainers; not invoked at runtime)." If a maintainer forgets to run `sync_substrate.sh`, CI fails. Add: an explicit pre-commit/CI hook OR a much smaller approach — import from `warroom_setup` only AFTER `hermes profile install` lands the template at `~/.hermes/profiles/<name>/warroom_setup/`, and use the in-repo path during dev runs. But this breaks the "self-contained, runnable from a fresh clone" claim.
**Fix:** Two acceptable options: (a) document in CONTRIBUTING that any change to `warroom_setup/render.py|prompts.py|validators.py|state.py|selectables.py|discord_walkthrough.py|slack_walkthrough.py` MUST be followed by `bash template/scripts/installer/sync_substrate.sh` and a commit before tests pass; (b) make `sync_substrate.sh` run automatically as a pre-test hook in the local Makefile. Either way, the plan should explicitly cite which path it picks.

**10. MAJOR — Rollback `shutil.rmtree(profile_path)` violates Hermes' user-data-preservation contract (§5 T6, §8).**
Plan: "rollback is `shutil.rmtree` if `stages_completed` includes `hermes_install`". But Hermes' `profile install --force` documents (verified via `hermes profile install --help`): "Overwrite an existing profile of the same name (**user data preserved**)". If hermes left a half-populated profile (per Inv2: post-`_bootstrap_user_dirs` failures leave `local/` with seed content), `rmtree` removes anything else that may have been carried over (e.g., if the operator is reinstalling on top of an earlier failed run AND chose strategy `proceed` but the dir already had user data from a prior install attempt). This contradicts the same plan's §8 statement: "We never `rmtree` on `confirm-overwrite` rollback; only on `proceed` (we own the dir we created)." That's only safe if `proceed` strictly requires `not exists` at the time of stage 1 — but a sidecar resume could land in `proceed` for an existing dir.
**Fix:** Before any `rmtree`, re-check `profile_detect.inspect_profile` and refuse to delete if `has_user_data` is true. Make this a hard invariant. Add a test: `test_rollback_refuses_to_delete_directory_with_user_data`.

**11. MAJOR — SIGINT signal handler is incomplete for the raw-mode-then-subprocess phase transition (§7 SIGINT row, §11 risk #1).**
Plan installs `signal.signal(SIGINT, _restore_and_save_sidecar)` at `main()` entry. But Python signal handlers DO NOT preempt blocking `subprocess.Popen.communicate()` / threaded reads inside the C runtime cleanly — they queue and run after the next Python opcode. While `run_capturing` is waiting on its reader-thread `join()`, a SIGINT will *first* trigger `KeyboardInterrupt` which interrupts `join()`, leaving subprocess + reader threads in undefined state and (worse) the terminal possibly in raw mode if we never made it past the post-TUI `tcsetattr` restore. Plan §4 says "Before exec, we restore the cursor and exit raw mode" — but the SIGINT in step 6 (Discord walkthrough) happens MID-raw-mode, NOT post-raw-mode. The signal handler can't restore termios without knowing the saved attrs, which live as a local variable in `_raw_mode_loop`'s frame.
**Fix:** Either (a) install the SIGINT handler dynamically per phase (raw-mode entry saves attrs in a module-global that the handler reads), or (b) catch `KeyboardInterrupt` at the outermost `main()` and call a `_emergency_restore` that re-issues `termios.tcgetattr` + a known-good restore + `\x1b[?25h` + saves sidecar. Document which.

**12. MAJOR — TTY fallback claim contradicts substrate semantics (§7 last row, §11 risk #5).**
Plan: "Terminal not a TTY → fall back to `_substrate.render._numbered_fallback`". But `_numbered_fallback` (render.py:54) is private (leading underscore) AND is invoked from `run_wizard` only when not a TTY. The installer cannot legitimately call `_numbered_fallback` directly; it should call `run_wizard` which handles dispatch. Furthermore, the numbered fallback consumes the stream and reads from stdin — but in the headless / piped scenario the stream often has scripted answers; the plan's "if still fails, error 'use --headless for non-interactive'" branch is unreachable because `run_wizard` already covers the non-TTY case.
**Fix:** Call `run_wizard` unconditionally (it dispatches by TTY check). The "use --headless" branch should fire on a DIFFERENT precondition: `not in_stream.isatty() AND not args.headless` — i.e., the installer was launched in a pipeline without explicit headless intent.

**13. MAJOR — `prompts.collect` uses `field.required` but the walkthrough adapter is custom; required-retry behavior is unspecified (§3 step 6).**
Plan: "Validators retry up to 3 times then offer skip-with-warning." But `run_discord_walkthrough(prompts, *, context)` (discord_walkthrough.py:111) calls `prompts(step, context=context)` once per step and uses the return value verbatim. Validation+retry is the caller's responsibility (the `prompts` callable). The plan delegates this to "an adapter that calls the appropriate raw-mode prompt" but never specifies that the adapter loops on validator failure. Without explicit retry-up-to-3 logic in the adapter, a single bad token entry kills the walkthrough.
**Fix:** Spec the adapter explicitly: pseudocode + a unit test (`test_walkthrough_adapter_retries_on_validator_failure`) that proves 3 attempts before optional-skip prompt.

---

## MINOR findings

**14. MINOR — `write_env` signature mis-stated as keyword-only in task summary; plan inherits the inaccuracy.**
Task summary describes `setup.write_env(profile_root, values, *, filename=".env")`. Actual `setup.py:114`: positional `filename`. Plan doesn't call `write_env` directly (delegates to setup.py) — but if finding #1's fix (a) is taken, the installer WILL call `write_env`, and the plan body should reflect the real signature.

**15. MINOR — Tests claim 47 unit tests but T6 lists 8 + T8 lists 4 = 47 across T1+T2+T3+T4+T5+T6+T7+T8+T9. Arithmetic checks. OK — no finding here.**

**16. MINOR — `template/tests/test_template_content.py:127-130` already asserts `install.sh` appears in `template/scripts/README.md`. Confirmed pre-existing test will pass without the plan's T9 README modification, but the README plan in T9 should NOT remove the existing "Planned" mention (since the script is now landing). T9 should rewrite that section, not just add to the top-level README.**

**17. MINOR — Stage 5 (`warroom enroll --status`) issued from inside the installer execute phase will already be a no-op duplicate, because Stage 3 (`warroom setup --yes`) ALREADY calls `enroll.bootstrap` when `warroom.enroll` toggle is selected (setup.py:396-414). The status call's only value is to print the JSON for the operator. Plan should clarify the redundancy is intentional — Stage 5 is a *display* step, not an *action* step.**

**18. MINOR — Sidecar at `~/.hermes/.awr-install-state.json` lives in Hermes' config dir. Plan §11 risk #3 acknowledges this, but `hermes profile install` may also write files into `~/.hermes/` during a partial-failure window. Race condition: SIGINT mid-install could race the sidecar writer with hermes' own state writers. Lower risk (different filenames) but worth a sidecar test `test_sidecar_path_does_not_collide_with_hermes_known_paths` that imports hermes if available and inspects its `HERMES_CONFIG_DIR` writes.**

**19. MINOR — Plan §5 T1 says launcher "12 lines: resolve python3, set PYTHONPATH to `installer/`, exec." Setting PYTHONPATH to `installer/` means imports rooted at `installer/` directly — so `import _substrate.render` works. BUT the launcher must export `PYTHONPATH=<abs path>/template/scripts/installer:${PYTHONPATH:-}` to preserve any existing PYTHONPATH. Forgetting the `:${PYTHONPATH:-}` clobbers a user's prior PYTHONPATH. Plan doesn't say.**

**20. MINOR — Plan §4 strips `PYTHONPATH` for hermes subprocs ("so `hermes` doesn't pick up our `_substrate/`") but ALSO says T6 stage 3 invokes `python3 -m warroom_setup setup --yes` with `PYTHONPATH=<profile>`. These two rules are consistent (different env per stage), but the plan should make it explicit that the global "strip PYTHONPATH" is a default that stage 3 overrides — currently §4 reads as a hard rule.**

**21. MINOR — Substrate copy of `slack_walkthrough.py` imports `from .discord_walkthrough import Step`. Confirmed. The plan's substrate list includes both; OK. But the drift test must cover BOTH files including their cross-import dependency, not just byte-equality. Add: `test_substrate_slack_walkthrough_imports_step_from_substrate_not_warroom_setup` — guards against the case where a refactor renames `Step` in one place but not the other.**

**22. MINOR — `daemon_probe.py` is listed as available reuse in the task summary but the plan never uses it. That's fine — `warroom enroll --status` invokes it internally — but the plan's substrate manifest should NOT include `daemon_probe.py` (it doesn't), and good that it doesn't. No finding; noting that the plan correctly elides this.**

**23. MINOR — Plan §3 step 4 collision handler uses a "raw-mode mini-picker" with three radio choices. Same radio-vs-toggle mechanic problem as finding #8: the existing renderer doesn't natively do radios. Likely implementable via three single-Toggle stages or via a custom mini-prompt loop, but the plan should pick one.**

---

## Sanity checks I ran

- `template/warroom_setup/` actual files vs. plan's reuse claims: all functions and constants exist with the names cited, EXCEPT `bootstrap` signature (finding #6).
- `hermes` actual CLI surface (installed 0.15.1): `profile install --help` confirms `--name --alias --force -y` (Inv2 contract holds); `plugins enable --help` confirms NO `-y` flag (finding #3).
- `_resolve_toggles` precedence (finding #1 root cause): verified `setup.py:323-346`; `--yes` without prior `agent.json` falls through to interactive `prompts.collect`.
- `answers.FILENAME` literal value: `.warroom-setup.json` (finding #2).
- `setup.write_env` signature: positional `filename`, not keyword-only (finding #14).
- `discord_walkthrough.run_discord_walkthrough` signature: `(prompts, *, context)` — matches plan's adapter shape, though retry behavior is unspec'd (finding #13).
- `render._is_tty` / `_numbered_fallback` / `_raw_mode_loop` mechanics: `_raw_mode_loop` is space=toggle, no radio (finding #8); `_numbered_fallback` is private and is auto-dispatched by `run_wizard` (finding #12).
- `publish.sh` subtree-split scope: `--prefix=template` means anything outside `template/` is not in published distribution (finding #5).
- `selectables.TEXT_FIELDS` field list: includes `agent_name`, `display_name`, `handle`, `DISCORD_ALLOWED_USERS`, `warroom.min_confidence` — missing from plan's `InstallerAnswers` (finding #7).
- Repo layout: `<repo>/template/` IS the Hermes distribution root (has `distribution.yaml`); `parents[2]` from `awr_install.py` is the correct default source (finding #4).
- Sanitization scan for "twelvelabs" across template/ and coordination/: 0 hits. Plan is clean on this axis.

## Summary

**Blockers (5): findings 1–5.** Fix all before T1 starts; otherwise T6 cannot succeed even with perfect code. Most surgical fix: replace "warroom setup --yes does everything" with "installer writes `local/agent.json` + `.env` directly, then runs `warroom setup --yes --sync`" (combining fixes for #1 and #2), and correct path arithmetic + install.sh location (#4, #5), and switch the plugin enable command (#3).

**Majors (8): findings 6–13.** Address before merge; each is a correctness or contract bug that will produce wrong behavior in real use even if blockers are fixed.

**Minors (10): findings 14–23.** Clarify in the plan body or in T-tests; none individually fatal.

---

## Adversarial review — Completeness

I have enough ground truth. Producing the adversarial completeness review now.

---

# Completeness review — AWR Feature B (Interactive Installer) plan

## Severity legend
- **BLOCKER** — plan cannot ship correctly without this; user-visible breakage.
- **MAJOR** — significant gap in UX/correctness; ship is degraded but not broken.
- **MINOR** — polish, future-proofing, doc gaps.

---

### 1. BLOCKER — `_substrate/` import paths will break: relative imports point to `warroom_setup` siblings the installer doesn't ship
**Missing:** The plan says "COPY render.py / prompts.py / discord_walkthrough.py / etc." but these modules use *relative* imports (`from .selectables`, `from . import validators`, `from .state import WizardState`). A naive copy into `_substrate/` keeps those `from .` imports — which then resolve against `_substrate.selectables`, fine — but only if `_substrate/__init__.py` is treated as the package root AND the launcher sets `PYTHONPATH` so that `_substrate` is importable. The plan's launcher sets `PYTHONPATH=installer/`, which makes `installer._substrate` importable as `_substrate` only if the launcher imports under that name; `awr_install.py` will need `from _substrate import render` (not `from .._substrate` or `from installer._substrate`). Also, `discord_walkthrough.py` imports `from . import validators` AND `from .selectables import Step` — both must be vendored, which the plan lists, but the plan must explicitly state the **import path the installer uses to reach them**, e.g. `from _substrate import discord_walkthrough` after `sys.path.insert(0, str(Path(__file__).parent))`.
**Fill in:** T2 — add explicit "import contract" subsection naming exactly which `sys.path` entry resolves `_substrate`, and add a test (`test_substrate_imports_under_installer_pythonpath`) that does `subprocess.run([python3, "-c", "from _substrate import render, prompts, validators, discord_walkthrough, slack_walkthrough, state, selectables"], env={"PYTHONPATH": str(installer_dir)})` and asserts exit 0.
**Justification:** Plan calls this out as "OK" in §12 pre-flight #1 but never specifies the launcher's `PYTHONPATH` shape; without locking it, T5/T6 will write `from .substrate.X` and discover at runtime that the package layout doesn't support that.

### 2. BLOCKER — `warroom setup --yes` does NOT replay secrets from `installer-answers.json`; T6 stage 3 will silently drop the Discord/Slack/Anthropic tokens
**Missing:** Reading `setup.py:370-394`, `run_setup(..., yes=True)` skips the entire `prompts.collect(...)` block when `prior_ident is not None` (returning `values = {}`), and only writes `.env` when `env_values` is non-empty. The plan's T6 stage 2 says "write `installer-answers.json` then let `warroom setup --yes` replay them" — but the answers schema (`answers_mod.Answers`) deliberately omits `SECRET_IDS` (selectables.py:82-83 + setup.py:419: `persist_values = {k: v for k, v in values.items() if k not in selectables.SECRET_IDS}`). Secrets are never persisted, so they can't be replayed. The installer's collected `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `ANTHROPIC_API_KEY` will end up in `installer-answers.json`'s in-memory shape but never reach `.env` via setup's replay path.
**Fill in:** T6 — the plan's parenthetical "(OR — simpler — write installer-answers.json)" must be eliminated. Spec the *only* approach: installer writes `<profile>/.env` directly using a vendored `_substrate.setup.write_env` (or its own ~20 line copy) BEFORE invoking `warroom setup --yes`; the headless setup invocation then sees the .env already populated and skips re-prompting. Add `test_execute_writes_env_with_all_secrets_before_warroom_setup` and `test_warroom_setup_yes_does_not_overwrite_installer_env` (regression).
**Justification:** This is the central "stitch" of the whole installer and the plan picks the broken option as an OR-alternative. The mailbox/board/identity replay via answers.json IS fine; only secrets need the direct-.env path.

### 3. BLOCKER — No spec for how Discord/Slack walkthrough's `prompts` callable adapter maps to raw-mode UI
**Missing:** `run_discord_walkthrough(prompts, *, context)` calls `prompts(step, context=context)` once per step (discord_walkthrough.py:120-134). For info-only steps it expects ANY return (ignored); for prompt steps it expects a string answer; validators live on `step.validator` and the *caller* is responsible for retry. The plan's §3 step 6 says "we pass an adapter that calls the appropriate raw-mode prompt" — but `prompt_secret` and `_prompt_once` operate in cooked mode (line-buffered stdin), while the TUI is in *raw* mode for the toggle picker. Switching between raw and cooked mid-walkthrough must be done carefully: termios state must be restored to cooked before each `input()`-style prompt and re-armed only for raw-mode pickers. The plan doesn't spec this transition, and worse, the walkthrough has SEVEN steps where most are "press Enter to continue" — those would hang in cooked mode without a prompt label.
**Fill in:** T5 — add explicit `_walkthrough_prompter_adapter(step, *, context)` spec: (a) if `step.prompt_label is None`: render `step.body_lines` then `print("Press Enter to continue (Esc to skip channel)...")` and read one line of stdin in cooked mode; (b) if `step.prompt_label`: call `_substrate.prompts.prompt_secret(step.prompt_label)` if a token validator, else `_substrate.prompts._prompt_once(step.prompt_label, step.validator)`. Spec also that the installer is in cooked mode for the ENTIRE walkthrough (raw mode is only used by `run_wizard` for the channels/model pickers).
**Justification:** Without this, T5 implementer will write a broken adapter and the smoke test will hang on the very first walkthrough step.

### 4. BLOCKER — `hermes plugins enable warroom-gate -y` flag is unverified, and §12 pre-flight #3 just says "verify" without defining the fallback path the plan needs
**Missing:** The plan acknowledges in Risk #4 that `-y` may not exist, but doesn't specify the fallback "write into `<profile>/plugins/enabled.txt` (or whatever Hermes uses)." It's "or whatever Hermes uses" — meaning the implementer doesn't know the file format. This is a hard blocker for stage 4 of the execute phase.
**Fill in:** T1 (precheck) — add `hermes_plugins_enable_supports_yes: bool` to `PrecheckResult` set, AND if false, T6 stage 4 must be specced as: invoke `subprocess.run(["hermes", "plugins", "enable", "warroom-gate"], stdin=subprocess.DEVNULL, ...)` with timeout 10s; if it hangs or fails, print clear "manual step needed: run `hermes plugins enable warroom-gate` after install" and continue. Don't speculate about `enabled.txt`. Also add §12 pre-flight #3 outcome: if `-y` not supported, T6's stage 4 falls back to advisory print, NOT to file-format guessing.
**Justification:** The plan's "or whatever Hermes uses" is hand-wavy; pre-flight #3 may fail and the plan has no concrete recovery.

### 5. MAJOR — Esc / Ctrl-C / empty-input behavior not specified per stage
**Missing:** Plan says "Esc anywhere to abort" in step 1's title, but:
- §3 step 5 says "Esc-back returns to step 4" — i.e. Esc is *back*, not *abort*. Which is it?
- Empty input on profile-name / source-path / API-key prompts: the validators in `validators.py` will reject empty for required fields, but the retry behavior is not specced ("retry up to 3 times then offer skip-with-warning" — applied to walkthrough only; what about identity?).
- `prompts._prompt_once` (vendored) — its actual retry semantics depend on the validator; on EOF (Ctrl-D), `input()` raises EOFError; not handled in plan.
- Ctrl-C in raw mode is intercepted by `_raw_mode_loop` (raises KeyboardInterrupt); Ctrl-C in cooked-mode prompts triggers SIGINT to the process. Different code paths, different cleanup needs.
**Fill in:** T5 — table of key bindings per stage:
  | Stage | Esc | Ctrl-C | Empty | EOF (Ctrl-D) |
  | source | back-to-start | abort+sidecar-save | retry | abort+sidecar-save |
  | name | back to source | ditto | retry | ditto |
  | channels (picker) | back | ditto | n/a | ditto |
  | walkthrough | skip-channel (with confirm) | ditto | "press enter again to skip" | ditto |
  | identity prompts | back | ditto | retry (required) / accept (optional) | ditto |
  | confirm | back to source | abort (no sidecar; user already saw summary) | n/a | abort |
Add `test_tui_esc_at_each_stage_returns_to_correct_predecessor` and `test_tui_ctrl_c_writes_sidecar_and_restores_terminal`.
**Justification:** Plan acknowledges termios restoration in Risk #1 but only tests it in T10's SIGINT case; per-stage UX is undefined and the implementer will have to invent it.

### 6. MAJOR — Resume-from-sidecar UX is under-specced when secrets must be re-entered
**Missing:** T7 says "Resume jumps to the recorded stage with prior answers pre-filled (secrets must be re-entered)" — but if the user was at stage `model` (post-channels, post-walkthrough), Resume must replay channel walkthroughs because those produce secret tokens that aren't persistable. The plan doesn't say "Resume forces re-do of walkthrough(s) if their secrets weren't saved." Worse, the partial-state for walkthrough means the user re-does the whole 7-step walkthrough.
**Fill in:** T7 — explicit Resume policy:
- Stages BEFORE walkthrough (source, name, channels): replay text answers, jump to walkthrough.
- Stage = walkthrough: tell user "channel walkthroughs cannot be partially resumed; you'll re-do them from step 1" and re-arm.
- Stage AFTER walkthrough (identity, model, board, confirm): pre-fill text answers, re-prompt for secrets only (`ANTHROPIC_API_KEY`, channel tokens if those channels selected) before reaching the original stage.
Add `test_sidecar_resume_after_walkthrough_re_prompts_only_secrets`.
**Justification:** "Resume" is a marquee feature in the plan but its behavior is under-defined for the load-bearing case (secrets dropped on the floor).

### 7. MAJOR — Two-step path compatibility is asserted but not tested
**Missing:** The plan's constraint #3 says "existing two-step path must still work after B ships" but no test confirms this. The risk: if T9 modifies `template/README.md` such that `bash scripts/setup.sh` instructions are moved/edited, or T6's "write `installer-answers.json`" introduces a file `warroom setup` doesn't tolerate, the two-step path silently breaks.
**Fill in:** T10 — add `test_two_step_path_still_works`: invoke `hermes profile install ... ; bash scripts/setup.sh --yes` (no `awr-install` involvement) and assert the same end-state as the installer path. Also add a test that `installer-answers.json`'s presence does not confuse `warroom setup` on a profile installed without the installer (i.e. that file is genuinely optional, not required).
**Justification:** Constraint #3 is load-bearing but the test plan never proves it; very easy to regress.

### 8. MAJOR — Uninstall / clean-removal path unspecified
**Missing:** User question: "I installed this and want to remove it." The plan implicitly assumes `hermes profile delete` covers this, but:
- The installer wrote to `~/.claude/settings.json` (via warroom_setup.enroll → mailbox install symlinks). `hermes profile delete` does NOT touch `~/.claude/settings.json`.
- The installer wrote to `~/.hermes/.awr-install-state.json`. Profile delete doesn't touch it.
- The installer's `local/installer-answers.json` is inside the profile, OK.
**Fill in:** T9 SMOKE.md — add cleanup-step #6 (already there) but expand to mention `~/.claude/settings.json` cleanup (or document that it's left intentionally because other agents may share it). Optionally T9 adds `bash install.sh --uninstall <name>` subcommand: `hermes profile delete <name>` + `rm -f ~/.hermes/.awr-install-state.json` + advisory print about ~/.claude/settings.json. If `--uninstall` is out of scope, document the manual recipe explicitly in README and SMOKE.md.
**Justification:** First-time users discover the installer; they'll try the inverse and find no documented path.

### 9. MAJOR — Plan claims "installer must be runnable from a fresh clone" but discovery for net-new users (no clone yet) is missing
**Missing:** The plan offers curl-pipe-able invocation:
```
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | bash
```
But `install.sh` is a *symlink* to `template/scripts/awr-install`. GitHub serves the symlink target's content when you fetch the symlink path via raw, so the bash launcher runs — but then the launcher does `exec python3 awr_install.py` which doesn't exist because we haven't cloned anything. The curl-pipe install pattern requires the bash launcher to FIRST `git clone` the repo to a tmp dir and then re-exec. The plan doesn't spec this.
**Fill in:** T1 — `awr-install` launcher logic:
1. If `$0` (or `$(realpath $0)`) lives inside a checkout (has sibling `template/`): use that as source.
2. Else (piped from curl): `git clone --depth=1 <repo> $TMPDIR/awr-bootstrap-<rand>` and re-exec from there.
Add `test_launcher_clones_when_not_in_checkout` (mocking git).
Alternatively: drop the curl-pipe invocation pattern from the plan (recommend dropping; piped-bash is a known security concern and adds complexity) and document only `git clone && bash install.sh`.
**Justification:** Plan advertises a feature in §2 that the implementation doesn't support; either fix or drop.

### 10. MAJOR — No PYTHONPATH-strip safety; `warroom setup` subprocess will inherit installer's PYTHONPATH and import `_substrate.X` instead of `warroom_setup.X`
**Missing:** §4 says "we strip `PYTHONPATH` (so `hermes` doesn't pick up our `_substrate/`)" but doesn't say the same for the `python3 -m warroom_setup setup` subprocess (T6 stage 3). If the parent's `PYTHONPATH` includes `installer/`, the child's `python3 -m warroom_setup` runs from `cwd=<profile>` with `PYTHONPATH=<profile>` (as setup.sh does) — unless the parent's env leaks through, in which case `import _substrate` succeeds and `import warroom_setup.X` may resolve to whichever appears first on `sys.path`.
**Fill in:** T6 — explicit env construction for ALL three subprocesses: `env = {**os.environ, "PYTHONUNBUFFERED": "1"}` followed by `env.pop("PYTHONPATH", None)` then setting `PYTHONPATH=<profile>` for the warroom_setup call (stage 3 only). Add `test_warroom_setup_subprocess_pythonpath_excludes_substrate_dir`.
**Justification:** Plan handles this for the hermes call but forgets it for the warroom_setup call, which is the higher-risk one (substrate shadows real package).

### 11. MAJOR — `~/.claude/settings.json` modification by mailbox install is not surfaced to the user
**Missing:** `coordination/install.py` (read above) modifies `~/.claude/settings.json` to wire mailbox hooks. The installer triggers `enroll.bootstrap` (via warroom setup) which may invoke mailbox install. The user is never told that a global Claude Code config is being modified. This is a surprising side-effect for a profile-scoped installer.
**Fill in:** §3 step 11 (confirm screen) — add line `Cross-agent: will modify ~/.claude/settings.json (mailbox hooks)` so user consents. T9 README "Interactive install" section — explicitly note this side-effect with a link to mailbox docs.
**Justification:** Reduces user surprise; required for trust on a public-repo installer.

### 12. MAJOR — Cross-platform: `termios` is POSIX-only; Windows users see a cryptic ImportError
**Missing:** Plan §11 Risk #5 says "Untested on WSL" but doesn't address native Windows. `render.py` line 136-137 imports `termios` and `tty` lazily inside `_raw_mode_loop`, so the *picker* import succeeds, but the call fails. The pre-flight check doesn't detect this.
**Fill in:** T1 precheck — add `posix_terminal_supported`: check `sys.platform != "win32"` (or `import termios; pass` in try/except). If unsupported, hard-fail with hint "use --headless on Windows; native TUI requires POSIX termios."
**Justification:** Public-repo distribution will get Windows users; a clear early-fail is much better than a stack trace.

### 13. MAJOR — `hermes profile install`'s "errors print to stdout, not stderr" assumption is encoded as Inv2 contract; plan needs a regression test
**Missing:** §4 says "Per Inv2, hermes profile install writes errors to stdout. Solution: ... concurrent threads draining both streams." OK — but the plan needs a test that confirms `subprocess_runner.run_capturing` actually preserves *order* across stderr and stdout, because the merged tail-scan for `DistributionError`/`error:` depends on lines arriving in chronological order from both streams. Two reader threads with a shared deque does NOT guarantee strict cross-stream ordering (Python GIL + scheduling can interleave non-deterministically).
**Fill in:** T3 — relax the guarantee in the design: the merged tail is *best-effort interleaving*, NOT strict chronological order. Add `test_run_capturing_preserves_order_within_each_stream` (each stream's lines appear in order, but cross-stream order is "approximately chronological"). Update §4 description accordingly.
**Justification:** The implementer will otherwise assume strict ordering and the failure-line extractor may scan a misordered tail.

### 14. MINOR — No log retention / size cap for `install.log`
**Missing:** T6 writes `~/.hermes/profiles/<name>/local/install.log` append-only. On a profile that gets reinstalled 50 times, this grows unbounded. Plan doesn't spec rotation/truncation.
**Fill in:** T6 — on each new install start, truncate the log (or rotate to `install.log.1`). Plus 1MB max line size cap to prevent log-bomb from a misbehaving subprocess.
**Justification:** Low-priority but trivially fixable; matters for long-lived dev workstations.

### 15. MINOR — `hermes_min_version` check parsing assumes `hermes --version` format
**Missing:** T1 precheck includes `hermes_min_version` checking ≥0.12. The plan doesn't spec the parse: `hermes --version` could print `hermes 0.12.3` or `0.12.3` or `hermes-agent 0.12.3 (built ...)`. Fragile parser.
**Fill in:** T1 — spec the regex (`re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b", output)`) and what to do on unparseable output (`unknown — proceed with warning`, not hard-fail).
**Justification:** Cross-version Hermes installs will produce false hard-fails otherwise.

### 16. MINOR — No observability hook for `--debug` or `--verbose`
**Missing:** Plan has `--stage-timeout`, `--dry-run`, `--headless`, `--force`, but no `--verbose` to dump subprocess stdout live during the execute phase. Debugging a failed install in the field would require manually `cat install.log`.
**Fill in:** T6 — add `--verbose` flag that streams subprocess output to stderr in addition to capturing to log. Add `test_verbose_streams_subprocess_output_live`.
**Justification:** Polish; valuable for debugging in CI / on user machines.

### 17. MINOR — Sanitization: T9's grep for `("twelvelabs", "twelve labs", "@twelvelabs")` doesn't catch the variant `tl_` prefixes used in skills like `tl-branding`
**Missing:** The skill `tl-branding` exists in the runtime environment (seen in available skills); `tl-` is a low-confidence prefix but a future maintainer might paste from `tl-branding` snippets into installer copy. Sanitize check is one-shot static.
**Fill in:** T9 — extend the grep tokens to include `("twelvelabs", "twelve labs", "@twelvelabs", "tl-branding")`. Optionally also enforce: installer-source must not import from anywhere outside `_substrate/` and `subprocess`/`pathlib`/stdlib.
**Justification:** Belt-and-braces; doesn't add complexity.

### 18. MINOR — `discord_walkthrough` Step has an `optional` field; plan doesn't surface "skip-this-step" UX
**Missing:** Discord walkthrough's step 6 (second channel) is `optional=True`. In the existing wizard, optional → empty input passes the validator. The plan's adapter must teach the user this in the UI ("press Enter to skip"), but doesn't say so.
**Fill in:** T5 walkthrough adapter — if `step.optional`, append `(optional — press Enter to skip)` to the prompt. Add `test_walkthrough_optional_step_skippable_with_empty_input`.
**Justification:** Existing walkthrough already supports this; installer just needs to surface it.

### 19. MINOR — `install.sh` symlink at repo root may not survive `git clone` on Windows (line-ending or no-symlink filesystems)
**Missing:** `git config core.symlinks=true` is default on macOS/Linux but false on Windows. The plan's repo-root symlink will land as a text file containing the symlink target on Windows clones, then `bash install.sh` will try to execute that text and fail.
**Fill in:** T1 — make `install.sh` a REAL bash file (not a symlink) that contains `exec bash "$(dirname "$0")/template/scripts/awr-install" "$@"`. Two-line shim, portable.
**Justification:** Public repo means heterogeneous clients; symlinks in repo are a known portability footgun.

### 20. MINOR — `enroll --status` invocation in stage 5 may exit non-zero (per `cli.py` cmd_enroll: codes 1, 2, 3), which a naive `run_capturing` will treat as failure
**Missing:** T6 stage 5 says "captures + parses JSON; if status=cli-not-found, print install hint." But `cmd_enroll` returns exit code 1 on `cli-not-found`, 2 on daemon unreachable, 3 on no state. The plan's stage runner treats non-zero as "fail." Either the runner must whitelist those codes for stage 5, or the call must parse JSON regardless of exit code.
**Fill in:** T6 stage 5 — explicit non-zero handling: parse JSON from stdout *regardless* of exit code; treat codes 1/2/3 as informational (print hint, don't trigger rollback); only treat exit codes outside `{0,1,2,3}` as hard failure. Add `test_execute_enroll_status_handles_nonzero_exit_gracefully`.
**Justification:** Exact integration contract from feature C is documented in cli.py:39-44; plan's stage runner must consume it.

### 21. MINOR — Plan never says where the installer code is sanitized-checked
**Missing:** T9 says `sanitize_check.py` is extended to scan `template/scripts/installer/`. But the file `scripts/sanitize_check.py` lives at `template/scripts/` and walks `ROOT_DEFAULT = template/`. So `template/scripts/installer/` would already be covered by the default walk. T9 should say "no extension needed; default walk covers it" OR explicitly list what test confirms coverage.
**Fill in:** T9 — clarify: "sanitize_check.py default walks `template/`; T9 adds a regression test `test_sanitize_check_walks_installer_dir` confirming coverage."
**Justification:** Reduces wasted implementation work.

### 22. MINOR — Sidecar file mode 0600 + `~/.hermes/` directory creation
**Missing:** T7 says "0600 perms" on sidecar. But `~/.hermes/` might not exist on a totally fresh system (no Hermes ever installed). The sidecar write would fail. Plan's pre-check (T1) verifies `~/.hermes/profiles/` writable but does not ensure parent `~/.hermes/` exists at sidecar-write time (which is BEFORE hermes install).
**Fill in:** T7 — `write_sidecar` does `parent.mkdir(parents=True, exist_ok=True)` with 0700 perms before writing. Add `test_sidecar_creates_parent_dir_if_missing`.
**Justification:** Trivial fix; otherwise sidecar fails on first-ever install on a clean machine.

### 23. MINOR — `git` not always required, but precheck demands it
**Missing:** T1 precheck includes "git installed (if source is git URL)". Plan doesn't say the precheck is conditional. If user passes a local path, git is irrelevant.
**Fill in:** T1 — `git_if_url` precheck is only added to the list when `--source` is detected as a URL (or when no source given and we'll need git for curl-pipe bootstrap, see Finding #9).
**Justification:** Avoid spurious precheck failures on offline / minimal systems.

### 24. MINOR — `installer-answers.json` location bypasses `local/` sanitization rules
**Missing:** The plan writes `<profile>/local/installer-answers.json`. The `local/` directory is `USER_OWNED_EXCLUDE` per Hermes, but the sanitize_check excludes only `tests/` and a few cache dirs — `local/` is shipped if accidentally committed. For non-secret answers this is fine, but the file shape (which board, which model) is operationally sensitive.
**Fill in:** T9 SANITIZATION.md — explicit note: "`<profile>/local/installer-answers.json` records non-secret install choices; never commit." Add T9 test that asserts no installer-answers.json appears under `template/`.
**Justification:** Defense in depth; trivial.

### 25. MINOR — No telemetry surface for "how long did the install take?"
**Missing:** T6 stages are timed (per CommandResult.duration_s), but no overall summary is printed at end. User asks "did it work? how long?" — only sees per-stage line.
**Fill in:** T6 success summary (§3 step 13) — add `Total time: 7.4s` line.
**Justification:** Polish.

---

## Cross-cutting recommendation
Findings 1, 2, 3, 4 are BLOCKERs — they each independently break the installer's main path. Resolve before T1 starts. Findings 5–13 are MAJORs that materially degrade the deliverable; address during the relevant task. Findings 14–25 can be batched into a polish pass at T9/T10.

The plan's biggest structural risk is the "two ways to do stage 2" dilemma in T6 (write .env directly vs write installer-answers.json and let setup replay) — pick one (direct .env write) and remove the OR.

---

## Adversarial review — Feasibility

I have everything I need. Producing the adversarial review.

---

# Adversarial review — Feature B Installer plan (FEASIBILITY)

## F1 [BLOCKER] `hermes plugins enable` has NO `-y`/`--yes` flag

**File/line at risk:** Plan §4 stage 4; T6 stage 4 (`hermes plugins enable warroom-gate -y`).

**Evidence:** `hermes plugins enable --help` on v0.15.1 prints only `[-h] name`. There is no `-y`. The plan's stated "Inv2 contract" only covers `hermes profile install`, not `plugins enable`. Worse, the plan's *own* "Risk #4" flags this as unverified and proposes "fall back to writing the plugin enable directly into `<profile>/plugins/enabled.txt`" — but no such file exists in the template (the plugin is enabled by Hermes' plugin manifest scanner, mechanism not specified in the plan).

**Mitigation needed:** Task T0/T1 must add a pre-flight test `hermes plugins enable --help` AND determine the actual enable mechanism (likely writing to `<profile>/config.yaml` plugins block, or a dedicated `plugins/enabled.json`). The current plan will hang or fail subprocess detection.

---

## F2 [BLOCKER] `distribution.yaml` presence ≠ "Hermes-managed" on real user machines

**File/line at risk:** §8 "Existing-profile detection" + T4 `inspect_profile` step 3.

**Evidence:** I checked `/Users/aahil/.hermes/profiles/aahil-sh/` — a real, working, daily-used Hermes profile. It has NO `distribution.yaml` at any depth (`find` returns nothing). It was created before the `profile install` flow existed, or via legacy `hermes profile create`. Hermes' own code (`profile_distribution.py:271`) only writes `distribution.yaml` when going through `install_distribution()` / `update_distribution()`. Profiles created via earlier flows lack it.

**Impact:** The plan's algorithm would classify aahil-sh as "non-Hermes manual dir" → strategy `confirm-overwrite` → operator forced into the dangerous-confirmation path even though it's a perfectly valid Hermes profile. Worse, if they confirm overwrite, the rollback will `rmtree` a profile we didn't create.

**Mitigation needed:** Either (a) use `<profile>/config.yaml` presence as the Hermes-managed signal (universal across Hermes versions), or (b) explicitly include a "legacy Hermes profile" category that still gets `reconfigure` strategy. Sub-task: add a test `test_collision_strategy_detects_legacy_hermes_profile_without_distribution_yaml`.

---

## F3 [BLOCKER] Egg-chicken: `python3 -m warroom_setup setup --yes` doesn't replay collected channel/identity secrets

**File/line at risk:** T6 stage 3 "Stage 3: `python3 -m warroom_setup setup --yes` … re-uses 100% of existing setup logic including `enroll.bootstrap`."

**Evidence:** Read `setup.py:349-428` and `selectables.SECRET_IDS`. Behavior:
- `--yes` with prior identity present → `values = {}` → **NO** identity, NO channel tokens get re-collected → `env_values = {}` → **`write_env` is skipped entirely** (line 393: `if env_values:`).
- `--yes` without prior identity → still calls `prompts.collect(...)` (line 374's else branch is unconditional when `prior_ident is None`) → but `prompts._prompt_once` reads from stdin, which is `DEVNULL` per the plan → EOF on first required prompt → returns early with empty values.
- No `answers.json` schema field for `ANTHROPIC_API_KEY` / `DISCORD_BOT_TOKEN` / `SLACK_*` exists (they're in `SECRET_IDS` and explicitly filtered out at line 419: `persist_values = {k: v for k, v in values.items() if k not in selectables.SECRET_IDS}`). So even if you write a pre-canned `installer-answers.json`, secrets cannot survive a round-trip through it.

**Impact:** Plan's "T6 Stage 2 writes `installer-answers.json`, Stage 3 replays via `--yes`" cannot deliver tokens. The whole "delegate to existing setup machinery" composition strategy is broken.

**Mitigation needed:** The installer must call `setup.write_env`, `setup.patch_war_room_block`, `enroll.bootstrap`, and `save_identity` **directly** (importing from a placed-on-PYTHONPATH `warroom_setup` after stage 1 succeeds — the package now lives at `~/.hermes/profiles/<name>/warroom_setup/` after the install). This means deleting the "Stage 3 calls `warroom setup`" idea and replacing it with a "post-install in-process orchestrator" that uses the freshly-landed package's public API. Add a task T6.5: "Programmatic seed: write .env, identity, war_room block, run enroll." Plan must be rewritten around this.

---

## F4 [BLOCKER] Vendored `_substrate/` cannot import — `from .selectables` / `from . import validators` require package context

**File/line at risk:** §2 "Drift mitigation"; T2 `_substrate/`; Pre-flight check #1.

**Evidence:** `render.py:8` does `from .selectables import Stage`; `discord_walkthrough.py:13` does `from . import validators`; `prompts.py:9` does `from .selectables import TextField`; `setup.py` (not vendored but pertinent) does `from . import answers as answers_mod`. The plan claims these will work after copying because we also vendor `selectables.py` and `state.py` and `validators.py`. They will — **but only when imported as `_substrate.render`, not when the launcher does `PYTHONPATH=installer/`. The `_substrate/__init__.py` must exist and `awr_install.py` must do `from _substrate import render` or `from .._substrate import render`. Pre-flight #1 says we'll "verify it's copyable" but doesn't specify the import shape the launcher uses.

**Impact:** Subtle but real. Plan currently says `PYTHONPATH=installer/`. That puts `awr_install.py` and `_substrate/` *siblings* under `installer/`. `awr_install.py` needs `from _substrate import render`. T2's drift-check test `subprocess.run([python3, "-c", "import _substrate.render"], cwd=installer_dir)` will work only if `_substrate/__init__.py` exists AND `cwd` is `installer/`. Real-world: when curl-piped, the user's shell cwd is unknown. The launcher must explicitly set `cd "$INSTALLER_DIR"` before exec.

**Mitigation:** Spell out exact `PYTHONPATH` shape, `cd` before exec, and required `__init__.py` placement. Add T2 sub-test: `test_substrate_imports_when_awr_install_invoked_with_random_cwd`.

---

## F5 [BLOCKER] Curl-pipe install (`curl ... | bash install.sh`) cannot drive a TUI — stdin is the curl stream

**File/line at risk:** §2 "Via curl (when published): `curl -fsSL .../install.sh | bash`".

**Evidence:** When you pipe to bash, the shell's stdin IS the HTTP body stream. Once the bash launcher execs the Python TUI, Python's `sys.stdin` is also that pipe (which is EOF after the script content). `_is_tty(sys.stdin)` returns False, `_raw_mode_loop` fails, `_numbered_fallback` reads EOF immediately. No terminal interaction is possible.

This is **the standard one-liner distribution claim** the plan makes. ccpkg and homebrew workarounds use `</dev/tty` redirection or a two-stage `curl … -o /tmp/x.sh && bash /tmp/x.sh`.

**Mitigation needed:** Either (a) drop the curl-pipe claim entirely from §2 / README, (b) the launcher detects pipe-stdin and re-execs Python with `</dev/tty` redirection (works on macOS + Linux but not on Windows/CI), or (c) ship as `curl … -o /tmp/awr-install && bash /tmp/awr-install`. Pick one and document, but DO NOT promise the naive pipe.

---

## F6 [HIGH] SIGINT during subprocess execute phase leaves terminal in unknown state

**File/line at risk:** §3 step 12 + §4 "No TUI pollution" + Risk #1.

**Evidence:** The plan says "we restore the cursor (`\x1b[?25h`) and exit raw mode (termios.tcsetattr restore from the saved attrs the renderer captured)" before exec. But `render._raw_mode_loop` (lines 138-176) captures `old` as a LOCAL variable inside `_raw_mode_loop`; the saved attrs are NOT accessible to the installer's main flow. Restoring requires running the entire wizard's `finally` block, which means returning from `run_wizard`. If SIGINT fires during a subprocess after `_raw_mode_loop` has returned cleanly, terminal is already non-raw — OK. But if SIGINT fires DURING `_raw_mode_loop`'s render (between `tty.setraw` and `tcsetattr` restore), the `KeyboardInterrupt` raised in `_read_key` may not run the `finally` if the signal handler runs first. The plan's mitigation ("install a `signal.signal(SIGINT, _restore_and_save_sidecar)` handler at `main()` entry") then tries to do tcsetattr without a saved `old` — it doesn't have the original attrs.

**Mitigation:** Save the original termios attrs in a *module-level* variable captured by the SIGINT handler before entering raw mode. Add a test that uses `pexpect` to send SIGINT mid-render and asserts terminal echo works after. This is non-trivial; budget LoC accordingly (currently understated in T5).

---

## F7 [HIGH] Existing `prompts.prompt_secret` uses `getpass` which doesn't compose with the installer's TUI

**File/line at risk:** §3 steps 6–8 (Discord/Slack/Anthropic key prompts) using `prompt_secret` "INLINE" inside the TUI flow.

**Evidence:** `prompts.py:42-60`: `getpass.getpass(prompt)` opens its own connection to `/dev/tty` for the masked prompt, prints to stderr by default, and does not respect the installer's `out_stream` / `in_stream`. If the installer is in raw mode (it would have just exited to do the secret prompt), `getpass` will work — but `getpass.getpass` does NOT clear the screen, restore raw-mode after, or coordinate with the TUI's screen buffer. Mixing screen-clear ANSI (`\x1b[2J`) → render walkthrough Step body → getpass → next Step body produces a scrolling cascade, not the "ccpkg-style flow" claimed.

**Impact:** TUI experience will look broken in practice — the walkthrough screens scroll up as each prompt happens, and the last walkthrough step is invisible.

**Mitigation:** Either reimplement masked prompting using the same termios+stdin path as the renderer (~30 LoC for tty raw-read + asterisk display), OR formally specify "during walkthrough steps, screen-clear and DO NOT use getpass; use line-based prompt that ECHOES" (acceptable for token-input on the operator's own machine). Pick one. Plan currently waves at "use `prompt_secret`" without addressing the interleaving.

---

## F8 [HIGH] `--alias` collision on subsequent installs

**File/line at risk:** §4 invocation `hermes profile install <SRC> --name <N> --alias --force -y`.

**Evidence:** `profile_distribution.py:633-636` shows alias creation calls `check_alias_collision(plan.manifest.name)` and skips alias if collision (silently — no error). So `--alias` is best-effort but isn't a problem. HOWEVER: when the user runs the installer a SECOND time (e.g., to add `beta-sh` after installing `alpha-sh`), `--force` doesn't apply to alias collision. The plan does not document what happens if `alpha-sh` already exists as a shell alias from a prior install. More critical: it doesn't document `hermes profile install --force` semantics — Hermes' `install_distribution` only honors `--force` when the **target profile dir** already exists; it does not wipe the user's local/ overlay.

**Mitigation:** §6 must clarify what `--force` does and does not nuke, since the plan's rollback strategy depends on knowing what state can be safely deleted. Add T4 sub-test for "alias collision warning surfaces in execute phase log."

---

## F9 [HIGH] `hermes profile install` strips error-channel ordering when stdout+stderr drained on separate threads

**File/line at risk:** T3 `subprocess_runner.run_capturing` — "two reader threads that append to a shared `collections.deque(maxlen=400)` of `(stream, line)` tuples."

**Evidence:** Per Inv2, errors print to stdout. The plan's "unified ordered tail" via two-thread merging into a deque has a subtle but real race: thread `out_reader` and thread `err_reader` both append; their interleaving order in the deque is **scheduling-dependent**, not write-order. For a tool that prints both error and traceback to the SAME stream (stdout), ordering is preserved (single thread), but the plan's `tail_for_error_line` scans across BOTH streams, so a stderr "warning" line could appear after a stdout error message in the deque, masking the real error.

**Mitigation:** Either (a) merge stdout+stderr at the kernel level by passing `stderr=subprocess.STDOUT` to Popen (loses stream attribution but preserves order — fine since Inv2 says errors go to stdout anyway), or (b) timestamp each appended line and sort on read. Option (a) is simpler; recommend that.

---

## F10 [HIGH] CI / non-TTY headless mode pseudo-supported but underspecified

**File/line at risk:** T8 "Headless mode" + §3 step 12 "Detect via `_substrate.render._is_tty`; fall back to numbered prompts."

**Evidence:** `--headless` mode skips `run_tui` entirely, BUT walks through the walkthrough Step lists by emitting them where? T8 doesn't say. The walkthrough exists to teach the user how to create a Discord bot — in headless mode the operator has presumably already done that and provided tokens via env vars. So the walkthrough should be SKIPPED, not rendered. Plan doesn't specify this. Also: `_substrate.render._is_tty` is checked but `getpass.getpass` will hang on a non-TTY in `_prompt_once` (`prompts.py:21-32` — if not real TTY, it falls through to `_read_line` which reads from stdin; stdin is DEVNULL → returns None → loop terminates without filling required fields → silent partial install).

**Mitigation:** Add T8.5: `test_headless_skips_walkthrough_when_tokens_provided_via_env`. Headless mode MUST validate all required secrets are present in env-vars before stage 1 starts, else abort with exit 11 "headless requires --discord-token-env when channels.discord selected."

---

## F11 [MEDIUM] T6 stage 5 enroll status check runs `python3 -m warroom_setup enroll --status` with what `cwd`?

**File/line at risk:** T6 stage 5.

**Evidence:** `warroom_setup.cli._profile_root` (cli.py:32-34) resolves the profile root as `Path(__file__).resolve().parents[1]` — i.e., where the package lives. After `hermes profile install`, the package lives at `<profile>/warroom_setup/`. So `python3 -m warroom_setup enroll --status` must run with `cwd=<profile>` and `PYTHONPATH=<profile>` (matches setup.sh:7's `PYTHONPATH="$HERE" exec python3 -m warroom_setup setup`). Plan doesn't specify these in T6 stage 5.

**Mitigation:** Specify in T6 the exact env+cwd for each subprocess. Add a `_subprocess_env_for_profile(profile_root)` helper.

---

## F12 [MEDIUM] Sidecar at `~/.hermes/.awr-install-state.json` collides with Hermes' own dotfile namespace

**File/line at risk:** T7 sidecar location.

**Evidence:** Hermes uses `~/.hermes/` for ALL its state (`hermes-agent/`, `profiles/`, `auth.json`, `.update_check`). The plan claims "Hermes may add a config with similar prefix — we use `.awr-` prefix" but `~/.hermes/` is Hermes' top-level dir. Cluttering it with installer state is unidiomatic and could be wiped by Hermes' future `hermes self update` cleanup. Better location: `~/.awr/install-state.json` (new dir, owned by us) or `${XDG_STATE_HOME:-~/.local/state}/awr/install-state.json`.

**Mitigation:** Move sidecar to `~/.awr/install-state.json` (create dir if absent). Update T7 tests.

---

## F13 [MEDIUM] `git source` (curl-pipe / first-time clone-of-template) flow has no fetch step

**File/line at risk:** §3 step 3 "If git URL: defer validation to step 9"; T6 stage 1.

**Evidence:** The plan handles `--source <local-dir>` and accepts a git URL. But for git URL sources, `hermes profile install <url> --name <N>` does the clone internally (verified in `profile_distribution.py:412`). So that's fine for stage 1. But step 3 of the TUI accepts a git URL, then between step 3 and step 11 it asks the user to enter ALL their secrets and config — none of which can be validated against the source until stage 1 runs. If the user typoed the URL, they discover it after entering 4 minutes of walkthrough answers. Bad UX.

**Mitigation:** When source is a git URL, do a `git ls-remote --exit-code <url>` (network reachability check, no clone) in step 3 before proceeding. ~10 LoC. Add test `test_source_stage_validates_git_url_via_ls_remote`.

---

## F14 [MEDIUM] Vendored substrate drift policy is byte-exact — incompatible with shared-core's "no cross-import" lint mentioned in enroll.py:159

**File/line at risk:** T2 "byte-identical to warroom_setup".

**Evidence:** `enroll.py:159` has comment "the no-cross-import lint (which forbids the dotted-import form here)". A future shared-core PR might add absolute imports (`from warroom_setup.X import Y`). When vendored to `_substrate/`, those imports break (no `warroom_setup` package on PYTHONPATH at installer-time). Byte-exact equality cannot survive such a refactor.

**Mitigation:** Drift policy should be **structural** (AST equivalence modulo top-level `from .` rewrites), not byte-exact. Or — better — vendoring is brittle; consider a `bootstrap_substrate.py` that DOWNLOADS the substrate from a pinned commit (works for curl-install) or imports directly from a checked-in source-of-truth path. Document the trade-off.

---

## F15 [MEDIUM] TUI time-to-completion budget unspecified — likely 5–10 min interactive, 90 sec headless

**File/line at risk:** §11 risks (no time budget mentioned).

**Evidence:** Walkthroughs are 7 steps each (Discord) × ~30 sec/step typing = 3.5 min just for Discord. Slack adds another 3 min. Then identity (3 prompts), API key (1 prompt), board (2 prompts). Stage 1's `hermes profile install` ranges 2–30 sec depending on whether the source is a git clone over slow network. Setup wizard execution: ~1 sec. Plugin enable: ~1 sec. Enroll status: ~1 sec.

**Expected real-world:** 5–10 min interactive (~~80% in walkthroughs), 30–90 sec headless (gated on git clone speed). The plan promises "one coherent flow … 4 commands → 1." That's true but doesn't reduce wall-clock significantly — only context-switching cost.

**Mitigation:** Specify time budget in §11. Surface progress timings in stage labels (`hermes profile install` should show "cloning from github..." if the source is a URL). Set `--stage-timeout` default = 300s for stage 1 (the plan currently says 120s, which fails for slow git clones).

---

## F16 [LOW] Termios is POSIX-only — Windows users fall through to numbered fallback silently

**File/line at risk:** Plan §11 "TUI portability beyond macOS … Untested on WSL."

**Evidence:** `tty` and `termios` raise `ModuleNotFoundError` on Windows. `render.py:136-176` imports termios inside the function, so import isn't at top — `_raw_mode_loop` will raise on Windows. `run_wizard` (line 192) catches generic Exception and falls back to numbered. But: this is the TUI substrate's behavior; the installer itself doesn't guard. The plan says "Tested on macOS + Linux. WSL untested" — that's fine, but the installer should detect Windows early and print a clear error. Also: the bash launcher (`#!/usr/bin/env bash`) doesn't work on Windows at all (no MSYS guarantee).

**Mitigation:** Add platform check in T1 precheck. Document "macOS + Linux only" in README. Plan §11 already covers but precheck enforcement is missing.

---

## F17 [LOW] TwelveLabs leak via local Hermes config inheritance — low risk but worth a tripwire

**File/line at risk:** Sanitization audit §10.

**Evidence:** Installer inherits `os.environ` and runs `hermes` and `python3 -m warroom_setup`. Aahil's shell env doesn't have TwelveLabs vars (verified via `env | grep -iE 'twelve|tl_'` — empty). Aahil's `~/.hermes/profiles/aahil-sh/.env` is unaffected. **HOWEVER**, if the installer ever READS an existing profile's `.env` (e.g., during `--reconfigure` to preserve tokens), it could surface secrets in install.log if logging is verbose. Plan says secrets aren't persisted in sidecar — but `install.log` is uncovered.

**Mitigation:** T9 sanitize_check must also scan `install.log` content patterns — assert no token-shaped strings (`xoxb-`, `sk-ant-`, `MTQ...`). Add to T9.

---

## F18 [LOW] `--reconfigure` path skipping stage 1 doesn't verify the existing profile is *this template's* profile

**File/line at risk:** §8 collision strategy `reconfigure` — "skip install; run setup only; preserves user data".

**Evidence:** If user has a Hermes profile named `alpha-sh` but it was installed from a DIFFERENT distribution (e.g., they have a war-room install from a fork), the installer's `--reconfigure` will run `warroom setup --yes` against a profile that may not have `warroom_setup/` package at all → `python3 -m warroom_setup` will `ModuleNotFoundError`.

**Mitigation:** Reconfigure strategy must verify `<profile>/warroom_setup/__init__.py` exists. Add T4 sub-test `test_reconfigure_aborts_when_profile_lacks_warroom_setup_package`.

---

## F19 [LOW] `getpass.getpass` writes its prompt to stderr by default on some Python builds — pollutes "Execute phase" rendering

**File/line at risk:** §3 step 12 expecting clean progress lines.

**Evidence:** `prompts.py:24` uses `getpass.getpass(label)`. On Linux/macOS Python 3.9, `getpass` writes to `sys.stderr` by default if `stdin` is a TTY. The plan's execute phase relies on stdout being the only output stream — but stage 1's subprocess inherits parent's stderr by default in `subprocess_runner.run_capturing` (the plan says stderr=PIPE, OK), but the TUI itself between stages might emit stderr from getpass into the same terminal. Minor interleaving risk.

**Mitigation:** Ensure all installer-internal prompts (not subprocesses) use only sys.stdout. Trivial fix; one line in T5.

---

## F20 [LOW] Headless mode `--discord-token-env VAR` reads from env at parse-time — env vars survive process tree visibility on macOS

**File/line at risk:** T8 `--discord-token-env VAR`.

**Evidence:** Other processes on macOS can read `/proc/self/environ` (Linux) or `ps eww` (some setups). Passing a Discord bot token via env is conventional but worth a one-line note in T8: prefer `--discord-token-file PATH` or stdin-pipe over env-var for high-trust contexts. Not a blocker.

**Mitigation:** Document the trade-off in SMOKE.md and add an alternative `--discord-token-file` option in T8.

---

## Summary

**Blockers (must fix before T1):** F1, F2, F3, F4, F5.
- F1 (`plugins enable -y` doesn't exist) — verify actual enable mechanism, redesign stage 4.
- F2 (`distribution.yaml` ≠ Hermes-managed) — change detection to use `config.yaml` presence.
- F3 (delegate-to-`warroom setup` doesn't replay secrets) — re-architect Stage 3 to call the package's functions in-process, not via `--yes`.
- F4 (substrate import shape) — specify PYTHONPATH, cd, __init__.py precisely.
- F5 (curl-pipe ≠ TUI) — drop the curl-pipe claim or use `</dev/tty` redirection trick.

**High-severity (likely surfaces in T6/T10):** F6, F7, F8, F9, F10.

**Medium / Low:** F11–F20 are cleanups / docs.

**Suggested task additions:**
- **T0 (new, before T1):** "Hermes capability validation" — confirm `plugins enable` actual contract, profile-install force semantics, alias collision handling. Documented in `template/docs/installer-preflight.md`. Blocks all subsequent tasks.
- **T6 restructure:** Replace "subprocess to `warroom setup --yes`" with "post-install in-process orchestration": after stage 1, add `<profile>` to `sys.path`, import `warroom_setup.setup`/`warroom_setup.enroll`, call public APIs with collected answers. Faster, debuggable, and the only way to deliver secrets.
