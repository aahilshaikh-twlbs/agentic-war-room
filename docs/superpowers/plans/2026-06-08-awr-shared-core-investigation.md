# AWR Shared-Core Investigation Findings

Date: 2026-06-08. Status: investigation complete. Pre-flight for the shared-core PR that unblocks features A/B/C.

All findings produced under strict TwelveLabs-redaction policy.

---

## Synthesis (decision aid)

# Synthesis: Pre-Flight Gap Decision Document

## 1. Verdicts on Pre-Flight Gaps

- **#1 Gateway env (mailbox routing)** — **GO**. `<HERMES_HOME>/.env` is auto-loaded into `os.environ` by every Hermes entrypoint; profile-active means `<profile>/.env` is loaded; no `local/*.env` glob exists, so don't invent one [Inv1].
- **#2 Hermes install CLI** — **GO (with wrapper hardening)**. `hermes profile install <src> --name <N> --alias --force -y` is the locked invocation; exit 0/1/2 only; errors print to **stdout** not stderr, so wrappers must capture both [Inv2].
- **#3 Mailbox lanes** — **NEEDS_TEST**. CLI has no `claim-lane`/`release-lane`/`list-lanes` subcommands; engine + protocol fully support lanes; `lane://` URIs are mangled by `os.path.abspath()` in `claim`/`seize`/`request-release` [Inv3]. Patch is straightforward but unmerged.
- **#4 aahil-sh audit** — **GO**. Complete sanitization map produced; blocklist + recipe table are actionable [Inv4]. One **NEEDS_TEST** sub-item: location of canonical MCP server registry (no `mcp.json` in profile root) [Inv4 §5].

## 2. Locked-In Decisions

1. **Mailbox routing config lives in `<profile>/config.yaml` as a top-level `mailbox:` block**, not in `.env`, not in `local/*.env` [Inv1]. Idiomatic — matches existing `discord`, `slack`, `kanban`, `skills` top-level keys.
2. **Tokens/secrets only** go in `<profile>/.env`. Reserve env for things that must override [Inv1].
3. **Lane CLI strategy: option (a) — patch upstream CLI** [Inv3]. ~30 LoC + ~40 LoC tests = ~70 LoC total in one file (`cli.py`). Lanes are a missing-surface bug, not a design change. Document `client.request(...)` as optional power-user fast-path; do not require it.
4. **Installer wrapper command (locked)**: `hermes profile install <SOURCE> --name <NAME> --alias --force -y`, capture stdout+stderr, surface last `Error:` line on nonzero [Inv2].
5. **Wrapper must detect pre-existing non-distribution profile dirs** (no `distribution.yaml` present) and prompt before passing `-y --force` to avoid silent overwrite [Inv2 §5].
6. **Default `warroom.label` → handle (operator string, not employer/peer)** — derives cleanly from sanitized persona; employer name is in the blocklist [Inv4].
7. **`skills/twelvelabs/**` is hard-excluded** from any auto-copy path; 27 generic categories survive sanitization [Inv4 §1].
8. **Template SOUL.md is human-edited directly** — no external vault-sync generator dependency [Inv4 §5].
9. **Personalities block trimmed** to 4-5 tasteful flavors (helpful/concise/technical/teacher/noir); drop kawaii/catgirl/uwu from public default [Inv4 §5].

## 3. Sanitization-Driven NEW Template Gaps (from Inv4)

These are gaps in our current `template/` that the shared-core PR must fill:

- **G-A. SOUL.md skeleton** — H1 + 6-8 H2 sections (Voice, How you talk, How you work, What you value, Communication, Writing Rules, Boundaries), all `<<FILL-IN>>` markers, no real persona content [Inv4 §3].
- **G-B. `memories/USER.md` + `memories/MEMORY.md`** — empty files with 1-line header documenting `§`-separator convention [Inv4 §3]. Convention was not in template plan.
- **G-C. `channel_directory.json`** — ship `{"updated_at": null, "platforms": {}}` skeleton [Inv4 §1, §3].
- **G-D. `slack-manifest.json`** — generic manifest with `<<APP_NAME>>` / `<<BOT_HANDLE>>` placeholders + one starter slash command [Inv4 §3].
- **G-E. `cron/jobs.json`** — `{"jobs": []}` or one commented-out sample [Inv4 §3].
- **G-F. `skills/.bundled_manifest`** starter — generic bundle only (writing-plans, TDD, dogfood) [Inv4 §3]. Schema unconfirmed → see G-J.
- **G-G. `skills/.hub/taps.json`** — `{"taps": []}` + official skills-hub tap pre-registered [Inv4 §3].
- **G-H. `.env.example`** — full key list with blank values [Inv4 §3].
- **G-I. `hooks/README.md` + `scripts/README.md`** — document contracts; dirs empty with `.gitkeep` [Inv4 §3].
- **G-J. `personalities:` block** in `config.yaml` (4-5 flavors) — preserve structure, trim contents [Inv4 §3, §5].
- **G-K. `platform_toolsets` declarations** — exact structure required or platform routing breaks; copy shape from aahil-sh [Inv4 §3].
- **G-L. Safe-default config keys** — `approvals.mode: manual`, `cron_mode: deny`, `security.tirith_enabled: true`, `redact_secrets: true` [Inv4 §3].
- **G-M. Sanitization blocklist** — ship as `template/SANITIZATION.md` (the regex + key list from Inv4 §4) so future contributors don't reintroduce org strings.

## 4. Updated Pre-Flight Gap List

Original 7 gaps → revised:

1. ~~Gateway env loading mechanism~~ **RESOLVED** [Inv1] — use `config.yaml: mailbox:` block.
2. ~~Hermes install CLI contract~~ **RESOLVED** [Inv2] — invocation locked; wrapper must handle stdout-as-error-channel.
3. **Mailbox lane CLI** — **OPEN, patch needed**. Sub-gaps:
   - 3a. Implement `claim-lane`/`release-lane`/`list-lanes` in `coordination/src/mailbox/cli.py` (~30 LoC) [Inv3 §4-5].
   - 3b. Test idempotent re-claim + `release-lane` no double-release vs. existing `release` selector path [Inv3 §6].
   - 3c. Decide naming: `claim-lane` (hyphenated, matches `request-release`) [Inv3 §6].
4. ~~aahil-sh audit~~ **RESOLVED** [Inv4] → expanded into G-A through G-M (§3 above).
5. **MCP server registry location** — **NEW, NEEDS_TEST** [Inv4 §5]. No `mcp.json` in profile root; template doc must accurately describe how MCP servers are added.
6. **Skill body spot-check** — **NEW, NEEDS_TEST**. Sample-only audit; full `SKILL.md` body read needed for `productivity/linear/`, `productivity/teams-meeting-pipeline/`, `mcp/native-mcp/`, `dogfood/` before copying [Inv4 §5].
7. **Installer pre-existing-non-distribution-profile detection** — **NEW, design only**. Wrapper must `stat <profiles>/<name>/distribution.yaml` before passing `--force -y` [Inv2 §5].
8. **`#<ref>` URL pinning in `hermes profile install`** — **NEEDS_TEST** [Inv2 §5]. Undocumented in `--help`, relies on `git clone` fragment handling.
9. **Gateway `gateway_state.json` empty-vs-`{}` semantics** — **NEEDS_TEST** [Inv4 §5]. 0-byte at idle may be expected or may be a bug.
10. **Bitwarden override risk** — **DOC-ONLY** [Inv1 §risks]. Template must warn: don't put `MAILBOX_BOARD` (or any non-secret routing config) in Bitwarden secrets.

## 5. Empirical Test Plan (for NEEDS_TEST items)

```bash
# Gap 3 (mailbox lanes) — confirm engine surface before patching CLI
python3 -c "from mailbox import client; import os; \
  print(client.request('list_lanes', {'session_id': os.environ['MAILBOX_SESSION_ID']}))"

# Gap 3 — reproduce abspath footgun for the patch test
mailbox claim 'lane://test-lane' ; mailbox claims | grep -i lane
# expect: a mangled '<cwd>/lane:/test-lane' entry, not a lane claim [Inv3 §2]

# Gap 5 (MCP registry location)
grep -RIn "mcp_servers\|mcp\.json\|register_mcp" /Users/aahil/.hermes/hermes-agent/hermes_cli/ | head -40
ls -la /Users/aahil/.hermes/profiles/aahil-sh/ | grep -i mcp

# Gap 8 (#<ref> pinning)
hermes profile install 'https://github.com/<test-org>/<test-dist>#v0.1.0' --name pin-test --force -y
hermes profile delete pin-test

# Gap 9 (gateway_state.json semantics)
grep -RIn "gateway_state" /Users/aahil/.hermes/hermes-agent/gateway/ | head -20

# Gap from Inv1 sanity check (optional confirm)
echo 'WAR_ROOM_TEST=ok' >> /Users/aahil/.hermes/profiles/aahil-sh/.env
hermes chat --profile aahil-sh -c 'import os; print(os.environ.get("WAR_ROOM_TEST"))'
# expect: "ok"
```

## 6. Top 3 Risks Remaining

1. **HIGH — Sanitization regression at copy time.** Manual spot-checks on `SKILL.md` bodies (Gap 6) and a `tl-*` namespace exclusion that lives only in convention, not code. If template is ever auto-rebuilt from a live profile without the blocklist (§3 G-M) wired into CI, org strings will leak [Inv4 §4, §5]. **Mitigation:** ship `SANITIZATION.md` + a CI regex check on the regex set in Inv4 §4.
2. **MEDIUM — Mailbox lane patch lands but `seize`/`request-release` still mangle `lane://` URIs.** Out of scope for this PR but a latent footgun any user will hit [Inv3 §6]. **Mitigation:** file follow-up issue; document the limit in lane CLI help text.
3. **MEDIUM — Installer error-channel mismatch (stdout vs. stderr) plus no `--json` mode.** Wrapper must scrape free-form Unicode-decorated text to detect failure; locale or TTY drift will break detection [Inv2 §5]. **Mitigation:** wrapper treats any nonzero exit as failure and surfaces the final stdout line verbatim; do not parse for specific error strings.

---

## Investigation 1 — Hermes gateway env propagation (Risk #1)

Hermes is the agent runtime in-process (Python). It calls Anthropic API directly. So any plugin/tool running inside Hermes can read `os.environ` populated from `<profile>/.env`. 

Now the synthesis:

# Verdict

**YES — with a critical caveat about WHERE the env var lives.**

`<HERMES_HOME>/.env` IS auto-loaded into `os.environ` at every Hermes entrypoint (CLI, gateway, run_agent). A profile dir (`<profiles>/aahil-sh/`) IS the `HERMES_HOME` for that profile. Plugins/tools running inside the agent runtime see those vars. **BUT** `local/mailbox.env` and any other `local/*.env` files are NOT scanned — only the canonical `<HERMES_HOME>/.env` and the project `.env` are.

# Mechanism

- Entry points (`gateway/run.py:852`, `run_agent.py:88`, `hermes_cli/main.py`) all call `load_hermes_dotenv(hermes_home=...)` from `hermes_cli/env_loader.py`.
- `load_hermes_dotenv` (env_loader.py:212-247) loads exactly two files:
  1. `<HERMES_HOME>/.env` (user, override=True — beats stale shell vars)
  2. `<project_root>/.env` (dev fallback)
- It then layers Bitwarden Secrets Manager on top (env_loader.py:250-323) if configured.
- No glob, no `local/` scan, no per-plugin env file convention.
- The agent runtime is **in-process Python**, not a Claude-Code subprocess. There is no spawn boundary between gateway and the agent loop — env propagation is just `os.environ` in the same process. Plugins and tools read `os.environ` directly.
- Profile name resolution: `profiles.py:299 get_profile_dir(name)` returns `<root>/profiles/<name>/`. That path IS passed as `hermes_home` to env_loader. So `/Users/aahil/.hermes/profiles/aahil-sh/.env` IS loaded when the aahil-sh profile is active.
- Subprocess child env, when Hermes DOES spawn one (e.g., `profiles.py:853`), uses `{**os.environ, "HERMES_HOME": str(profile_dir)}` — full parent env carried.

# Implication for war-room design

The profile-local `.env` IS a viable channel — but **do not invent a new file convention** like `local/mailbox.env`. Two clean options:

1. **Add `MAILBOX_BOARD=...` to `<profile>/.env`.** Zero gateway patching. Plugins read `os.environ["MAILBOX_BOARD"]` at startup. Profile-portable. Survives profile clone (`hermes profile create coder --clone` copies `.env`). Recommended.

2. **Add a top-level `mailbox:` block to `<profile>/config.yaml`** and have the war-room plugin parse it at load. config.yaml is the canonical place for non-secret runtime config — env vars are for secrets and shell overrides. This is more idiomatic given the existing schema (discord, slack, kanban, skills are all config.yaml top-level keys).

The plan should prefer **option 2** (config.yaml block) for board name, channel bindings, and similar non-secret routing config. Reserve `.env` for tokens.

# Risks / unknowns

- `.env` is override=True, so a stale shell-exported `MAILBOX_BOARD=foo` from a prior session WILL be overridden by the profile `.env` on every entrypoint — good for determinism, but means devs who export it from shell expecting precedence will be surprised.
- Bitwarden layer can override `.env` values if `override_existing: true` in `config.yaml:secrets.bitwarden`. Don't put board names in Bitwarden.
- ASCII sanitization (env_loader.py:102-143) only strips non-ASCII from vars ending in `_API_KEY`, `_TOKEN`, `_SECRET`, `_KEY`. `MAILBOX_BOARD` is unaffected — but if any war-room env var ends in `_KEY`, expect silent stripping of non-ASCII.
- If war-room ever spawns a child process (codex/external CLI), that child inherits `os.environ`, so the var travels — but no glob-of-local-envs convention exists, so a `local/*.env` design would require a new loader.
- Empirical confirmation not strictly needed given source clarity, but a 30-second sanity test: `echo 'WAR_ROOM_TEST=ok' >> <profile>/.env && hermes chat` then have a tool/plugin log `os.environ.get("WAR_ROOM_TEST")` — expect `"ok"`.

Relevant files (absolute):
- `/Users/aahil/.hermes/hermes-agent/hermes_cli/env_loader.py` (lines 212-247: the loader)
- `/Users/aahil/.hermes/hermes-agent/gateway/run.py` (lines 849-863: gateway invocation)
- `/Users/aahil/.hermes/hermes-agent/run_agent.py` (line 88: agent invocation)
- `/Users/aahil/.hermes/hermes-agent/hermes_cli/profiles.py` (line 299: profile→HERMES_HOME mapping, line 853: subprocess env propagation pattern)
- `/Users/aahil/.hermes/profiles/aahil-sh/.env` (exists, ~24 distinct keys; structure: tokens, channel/user IDs, debug flags, timeouts — no mailbox keys today)
- `/Users/aahil/.hermes/profiles/aahil-sh/config.yaml` (top-level keys include `discord`, `kanban`, `skills`, `gateway`, etc. — natural place for a `mailbox:` block)

---

## Investigation 2 — `hermes profile install` CLI contract (gap #2)

I have a complete picture. Producing the report.

---

# `hermes profile install` — CLI contract

## 1. Flag table

| Flag | Shorthand | Semantics | Default |
|---|---|---|---|
| `source` (positional) | — | Required. Git URL (`github.com/u/r`, `https://...`, `git@...`, `ssh://`, `git://`, optional `#<ref>`) **or** local directory containing `distribution.yaml` at its root. No tar.gz, no plain HTTP archive. | (required) |
| `--name NAME` | — | Override the profile name from the manifest. Normalized + validated; rejected if it resolves to `default`. | manifest `name:` |
| `--alias` | — | Create a shell wrapper alias for the new profile (skipped silently on alias-name collision). | off |
| `--force` | — | Overwrite an existing profile of the same name. User-owned paths (memories/, sessions/, auth.json, .env, state.db, logs/, plans/, workspace/, home/, *_cache/, local/, etc. — full set in `USER_OWNED_EXCLUDE`) are still preserved. Without `--force`, install aborts on name collision. | off |
| `-y`, `--yes` | `-y` | Skip the interactive manifest-preview confirmation prompt. | off |

No `--ref`/`--branch` flag; ref pinning rides in the URL as `#<ref>` (handled implicitly by `git clone`). No verbose/quiet flag.

## 2. Exit-code table

| Code | Meaning |
|---|---|
| 0 | Success, OR user declined the preview prompt ("Install cancelled." printed, then early return — *not* a failure). |
| 1 | Any `DistributionError` or `ValueError`: bad source, missing `distribution.yaml`, manifest parse failure, `hermes_requires` mismatch, symlinks in tree, name resolves to `default`, name collision without `--force`, `git clone` failure (incl. `git` not on PATH). |
| 2 | argparse usage error (unknown flag, missing positional). |

There is no distinct code for network vs. validation failures — the installer wrapper cannot tell them apart from exit code alone; it must scrape stderr.

## 3. Partial-failure behavior

Install is staged, not atomic. Flow: clone to a `tempfile.TemporaryDirectory` → validate manifest + reject symlinks → `_bootstrap_user_dirs` (creates `memories/`, `sessions/`, `skills/`, `skins/`, `logs/`, `plans/`, `workspace/`, `cron/`, `home/` on the target) → `_copy_dist_payload` iterates top-level entries with per-entry `rmtree` + `copytree`/`copy2`.

Failure windows:
- Failures **before** `_bootstrap_user_dirs` (clone, manifest parse, version check, symlink scan, name validation) leave the target untouched. Temp dir auto-cleans.
- Failures **after** `_bootstrap_user_dirs` starts (rare — disk full, permission error mid-copy) leave a half-populated profile directory: bootstrap dirs created, some distribution-owned entries copied, others missing, and `distribution.yaml` possibly not yet written (it is written last, inside `_copy_dist_payload`).

Recovery: re-run with `--force`. If that fails too, `hermes profile delete <name>` then re-install. There is no rollback and no "install lock" file.

## 4. Recommended invocation from the installer

```
hermes profile install <SOURCE> --name <NAME> --alias --force -y
```

- `-y` is required — the underlying command prompts on stdin via `input()` and will hang a non-interactive wrapper.
- `--force` is required when re-running over a previous attempt (idempotency).
- `--alias` is cheap (no-op on collision) and gives the user the `<NAME>` shell wrapper they likely want.
- `--name` lets the installer surface the chosen profile name in its own UI instead of leaking the manifest's `name:`.
- Capture both stdout and stderr; treat exit 0 as success. On nonzero, surface the last stderr line (it carries the `Error: ...` message).

## 5. Risks / unknowns

- **Stdout noise is heavy and unstructured.** On success the command prints ~10-20 lines: manifest preview block (name/version/desc/source/target/env-vars table with check-marks/Unicode bullets), cron warning if applicable, then a 4-line "Installed / Profile path / Next / Use with" footer. There is no `--json` or `--quiet`. A wrapper must either pipe-through or fully swallow + re-render.
- **Unicode in output**: the CLI emits `✓`, `•`, `⚠`, `→`. Wrapper TTY must be UTF-8 or these will mojibake.
- **Error channel**: all errors print to **stdout** via `print(f"Error: {e}")`, not stderr. Wrappers parsing stderr will see nothing on failure.
- **Git is a hard runtime dep** for URL installs; surfaced as a `DistributionError`, not a distinct exit code.
- **No dry-run flag**. The closest equivalent is the preview that prints before the `y/N` prompt — but it requires actually cloning to a temp dir, so it costs a network round-trip.
- **`--force` over a hand-built (non-distribution) profile is allowed** and silently overwrites SOUL.md, mcp.json, skills/, cron/. The interactive preview warns; with `-y` that warning is bypassed. The installer should detect this case itself (check for existing profile dir without `distribution.yaml`) and prompt before passing `-y --force`.
- **No lockfile**: two concurrent installs of the same name race on the target directory.
- **`#<ref>` pinning is undocumented in `--help`** and relies on `git clone` interpreting the fragment — worth a manual test before committing the installer to it.

Source file: `/Users/aahil/.hermes/hermes-agent/hermes_cli/profile_distribution.py`. CLI handler: `/Users/aahil/.hermes/hermes-agent/hermes_cli/main.py:11075-11125` (action) and `:14586-14614` (argparse).

---

## Investigation 3 — Mailbox CLI lane operations (Risk #2, gap #3)

Got everything I need. Producing the report now.

---

# Investigation 3 — Mailbox CLI lane operations

## 1. CLI subcommand inventory

CLI parser registers exactly these subcommands (verified by `--help`): `join`, `claim`, `release`, `seize`, `request-release`, `send`, `inbox`, `claims`, `ps`, `board`, `whoami`. **No `claim-lane`, `release-lane`, `list-lanes`, or `lane` subcommand exists.**

| Subcommand        | Works on lanes?       | Semantics                                                                                                                                                  |
| ----------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claim <globs>`   | No (with caveat)      | Maps each glob through `os.path.abspath()` then calls engine `claim` (explicit claim, single-writer, conflict-checked).                                    |
| `release <sel>`   | Partially — see below | Passes `selector` straight through to engine `release` **without abspath rewriting** (CLI doesn't normalize it).                                           |
| `seize <path>`    | No                    | `os.path.abspath()` then engine `seize` — would mangle `lane://x` into `<cwd>/lane:/x`.                                                                    |
| `request-release` | No                    | Same abspath mangling as `seize`.                                                                                                                          |
| join/send/inbox/claims/ps/board/whoami | n/a      | Generic plumbing.                                                                                                                                          |

The engine **does** implement lane semantics: `claim_lane`, `release_lane`, `list_lanes` (engine.py:289–377) and they're in `protocol.OPS` (protocol.py:18). So the daemon speaks lanes — the CLI just doesn't expose them.

## 2. `lane://` URI handling — Risk #2 confirmed

The footgun is real and lives in `cli.py:18` (`_abspath = os.path.abspath`) and lines 130, 144, 150. Any string passed to `claim`, `seize`, or `request-release` gets `os.path.abspath()`'d, which turns `lane://build-api` into something like `/Users/aahil/.../coordination/lane:/build-api` — a meaningless file path that won't match the engine's `lane://` prefix-keyed conflict scan.

`release` is the *only* shell-accessible verb that doesn't abspath its argument (it forwards the selector raw to the engine, which accepts globs/claim-ids/`all`), so `mailbox release lane://x` could partially work — but only because release accepts a selector, not because the CLI understands lanes. There is no shell path to `claim_lane` / `list_lanes` at all.

## 3. Python API surface (in-process)

`coordination/src/mailbox/client.py` exports `request(op, args, session=None, autospawn=True)` which auto-spawns the daemon, connects to the Unix socket at `config.socket_path()`, and returns `{ok, data|error}`. An in-process plugin calls:

```
from mailbox import client
client.request("claim_lane", {"session_id": sid, "lane": "build-api", "note": "..."})
client.request("release_lane", {"session_id": sid, "lane": "build-api"})
client.request("list_lanes", {"session_id": sid})
```

Hard prereq: `<repo>/coordination/src` must be on `sys.path`, AND the import name `mailbox` shadows the stdlib `mailbox` module — so the client itself sets `PYTHONPATH` defensively in `ensure_running` (client.py:61–63) by `realpath`-resolving its own location. A subprocess Python plugin without that path on `sys.path` cannot `import mailbox` at all.

Session id is read from `MAILBOX_SESSION_ID` env or `--session` flag (cli.py:9–15) — same contract applies in-process.

## 4. Recommended strategy: **(a) + thin (c)** — patch the CLI, recommend the import for power users

Add three subcommands (`claim-lane`, `release-lane`, `list-lanes`) to `cli.py` that do **not** route through `_abspath`. Forward args directly to the engine ops that already exist. This:

- Eliminates Risk #2 by construction (no abspath path for lane URIs).
- Keeps the war-room template completely shell-driven — no PYTHONPATH prereq, no stdlib `mailbox` shadow concerns in plugin code.
- Is upstream-correct: the engine already speaks lanes; the CLI just forgot to expose them. This is a missing-surface bug, not a design change.
- Cost is tiny vs. teaching every plugin author to bootstrap `sys.path` and avoid the stdlib collision.

The template can additionally document the `client.request(...)` path as an optional fast-path for in-process callers (option c, ~3 lines of docs), but it should not be required.

## 5. LoC estimate

- `cli.py`: ~30 LoC (three `sub.add_parser` blocks + three `elif cmd == ...` branches + a `_print_lanes` helper). Output-formatting follows the existing `_print_claims` pattern.
- Tests (parallel to existing CLI tests): ~40 LoC covering allow/deny/warn shapes for `claim-lane`, idempotent re-claim, `release-lane` round-trip, `list-lanes` filtering.
- Total: **~70 LoC**, single file plus tests, no engine/protocol/daemon changes needed.

## 6. Risks / unknowns

- **Selector ambiguity in existing `release`:** `release` already forwards strings to the engine, so `mailbox release lane://x` may "work by accident" today via the selector path. The new `release-lane` must be unambiguous and tested to not double-release.
- **Subcommand naming:** spec uses `claim <glob>` for files; whether to land `claim-lane` (matches spec doc tone) vs `lane claim` (a `lane` group) is a small bikeshed. Hyphenated form matches the existing `request-release` precedent.
- **`list_lanes` output format:** engine returns rich dicts (lane, claim_id, session_id, label, note, live); CLI needs a print helper. Low risk, mirrors `_print_claims`.
- **Stdlib `mailbox` shadowing:** if anyone ever recommends the in-process path, they must set `PYTHONPATH` before `import mailbox` or Python will import the stdlib email-mbox module. Argues further for keeping the template subprocess-only.
- **Unverified:** whether `seize`/`request-release` should also accept lane URIs without abspath rewriting. Engine `seize` takes `abs_path` and matches against claim paths literally, so a lane URI would silently fail to match. Out of scope here, but the same abspath-footgun lives in `seize` and `request-release` and is worth a follow-up.

Relevant files:
- `/Users/aahil/Documents/Code/agentic-war-room/coordination/bin/mailbox`
- `/Users/aahil/Documents/Code/agentic-war-room/coordination/src/mailbox/cli.py`
- `/Users/aahil/Documents/Code/agentic-war-room/coordination/src/mailbox/client.py`
- `/Users/aahil/Documents/Code/agentic-war-room/coordination/src/mailbox/engine.py` (lines 277–377)
- `/Users/aahil/Documents/Code/agentic-war-room/coordination/src/mailbox/protocol.py` (line 18)

---

## Investigation 4 — aahil-sh sanitized-porting audit

I have enough structural data. Compiling the final redacted report.

---

# Investigation 4 — aahil-sh Profile: Sanitization Map for Public Template Porting

Read-only inspection of `/Users/aahil/.hermes/profiles/aahil-sh`. ZERO raw org strings reproduced below; all org-specific values are categorized by shape only.

## 1. Directory inventory

| Path | Type | Tag | One-line description |
|---|---|---|---|
| `profile.yaml` | file (5 lines) | NEEDS-PARAM | Free-text `description` + `description_auto` bool; current value names the operator + employer + project codename. Template ships with placeholder + `description_auto: true`. |
| `config.yaml` | file (~590 lines) | REUSABLE (mostly) + NEEDS-PARAM (pockets) | Massive generic Hermes config. ~95% reusable as-is. Org-specific bits are scoped: `slack.extra.allow_admin_from` (raw user ID), `slack.extra.group_allow_admin_from` (raw user ID), and the `description`-flavored fields elsewhere. `personalities` block is generic templates (helpful/concise/pirate/etc.) — REUSABLE. |
| `mcp.json` | **ABSENT** | n/a | No `mcp.json` in profile root. MCP configuration appears to live elsewhere (likely runtime `auth.json` or per-skill plugin metadata). Template should ship one with 0 entries + a documented schema. |
| `auth.json` | file (~9KB) | TL-SPECIFIC (secrets) | OAuth tokens / API keys per provider. NEVER copy. Template ships empty `{}`. |
| `.env`, `.env.bak-*` | files | TL-SPECIFIC (secrets) | Raw secrets. NEVER copy. Template ships `.env.example` only. |
| `SOUL.md` | file (262 lines, auto-generated) | TL-SPECIFIC (entirely persona) | Top banner says "DO NOT EDIT. Generated from vault `self/` by `ops/scripts/<sync>.py`". Section structure: H1 persona title, H2 Voice / How you talk / How you work / What you value / Communication / Writing Rules / Table Formatting / etc. Contains operator's real name, employer, role, tenure, stack-percentages, manager handle, pod assignment, embedded agent fingerprint UUID, network peer names, internal Slack/Discord channel conventions. **The shape (H1 + ~8 H2s averaging 20-40 lines each) is reusable; every content line is org-specific.** |
| `channel_directory.json` | file (~400 lines) | TL-SPECIFIC (runtime cache) | Schema: `{updated_at, platforms: {discord: [...], slack: [...]}}`. Each entry: `{id, name, guild|workspace, type: channel|thread|dm|group, thread_id}`. All values are live IDs/names. **Runtime-generated** — template ships empty `{platforms: {}}` skeleton or omits entirely. |
| `gateway_state.json` | file (empty) | REUSABLE (shape) | 0-byte placeholder; runtime-managed. Template ships empty file. |
| `gateway/discord_command_sync_state.json` | file (~266 bytes) | REUSABLE (shape) | Runtime cache of slash-command sync. Template ships empty `{}`. |
| `gateway.lock`, `gateway.pid` | files | n/a | Runtime artifacts. Never copy. |
| `discord_threads.json` | file (empty 0-byte) | REUSABLE (shape) | Runtime thread cache. Template ships empty. |
| `slack-manifest.json` / `slack-manifest-current.json` / `slack-manifest-merged.json` / `slack-slashes.json` | files (~10-13KB each) | NEEDS-PARAM | Slack app manifest payloads. Structure (display info, bot scopes, event subscriptions, slash command list) is reusable; current values contain app name, workspace handle, command labels styled around the operator's persona name. Template ships a generic manifest with `<<APP_NAME>>` / `<<BOT_HANDLE>>` placeholders. |
| `state.db` (+ `-shm`, `-wal`) | sqlite files (~5MB) | TL-SPECIFIC (runtime) | Session/memory database. Never copy. Template ships nothing; created on first run. |
| `models_dev_cache.json` | file (~2MB) | REUSABLE (cache) | Generic model catalog cache. Runtime-regenerated; template can omit. |
| `.skills_prompt_snapshot.json` | file (~64KB) | TL-SPECIFIC (cached) | Compiled skills prompt snapshot. Runtime artifact. Skip. |
| `.update_check`, `context_length_cache.yaml` | small files | REUSABLE | Generic runtime metadata. |
| `cron/jobs.json` | file (~47 lines, 1 active job) | TL-SPECIFIC + REUSABLE shape | Schema: `{jobs: [{id, name, prompt, skills, script, no_agent, schedule:{kind,expr,display}, repeat, enabled, state, created_at, next_run_at, ...}]}`. Current single job has org-specific `name`, `prompt`, and `script` (references a sync script + downstream vault repo). **Schema is reusable**; ship a minimal sample job (e.g. "daily greeting") with placeholder `prompt`. |
| `cron/output/` | dir | n/a | Runtime logs. Skip. |
| `hooks/` | dir (empty) | REUSABLE | Empty in aahil-sh; template should ship empty too with a `README.md` documenting the hook contract. |
| `scripts/` | dir (empty) | REUSABLE shape | Empty. Template can ship empty with a README explaining script-discovery rules. |
| `plans/`, `workspace/`, `skins/`, `pairing/`, `image_cache/`, `audio_cache/` | empty dirs | REUSABLE | All empty in current profile; ship empty in template with `.gitkeep`. |
| `sandboxes/singularity/` | empty dir | REUSABLE | Empty subdir for singularity engine. Skip. |
| `cache/`, `logs/`, `lsp/` | runtime dirs | n/a | Runtime-generated. Skip / `.gitignore`. |
| `home/` | dir (`.cache`, `.npm`, `Library`) | TL-SPECIFIC (caches) | Per-runtime sandboxed `$HOME`. Skip; runtime creates it. |
| `memories/MEMORY.md` | file (~50 lines) | TL-SPECIFIC | Free-form Markdown of session-flavored memory entries separated by `§`. Each entry references vault paths, repo paths, retired services, internal nomenclature. **Shape reusable**: a Markdown file with `§`-separated entries. Template ships empty `MEMORY.md` with a 1-line header comment. |
| `memories/USER.md` | file (~30 lines) | TL-SPECIFIC | Same `§`-separated format. Contains operator name, employer, role, stack percentages, manager handle, network pod assignment, writing rules (e.g. "no em dashes"), workflow preferences (TDD, prototypes). **Shape reusable; every line org-specific.** Template ships empty. |
| `memories/*.lock` | 0-byte locks | n/a | Runtime. |
| `sessions/` | dir | n/a | Per-session work. Skip. |
| `skills/` | dir (32 entries) | mixed | See skill-bundle inventory below. |
| `skills/.bundled_manifest` | file (~4KB) | REUSABLE shape | Bundle declaration. Schema reusable; current bundles are operator's curated list. |
| `skills/.curator_state`, `skills/.usage.json` | runtime | REUSABLE shape | Empty / minimal in template. |
| `skills/.hub/` (audit.log, index-cache, lock.json, quarantine, taps.json) | dir | REUSABLE shape | The skills-hub plumbing (tap registry, quarantine for failed installs). `taps.json` schema reusable; current taps list is operator's. |
| `skills/<category>/` directories (28 of them) | dirs | mixed | See breakdown below. |

### Skill category breakdown

| Category dir | Tag | Notes |
|---|---|---|
| `twelvelabs/` (18 sub-skills: tl-analyst, tl-architect, tl-code-review, tl-cowork-experiments, tl-debugger, tl-drafter, tl-intel-scraping, tl-internal-tooling, tl-ops, tl-perf, tl-pm, tl-refactor, tl-researcher, tl-scribe, tl-security-audit, tl-slack-comms, tl-tester, tl-writer) | **TL-SPECIFIC — NEVER COPY** | Entire `twelvelabs/` namespace is org-specific. Each `SKILL.md` has YAML frontmatter (`name`, `description`, `metadata.hermes`) + freeform body. Naming convention `tl-*` itself encodes the employer. |
| `apple/`, `creative/`, `data-science/`, `devops/`, `diagramming/`, `domain/`, `email/`, `gaming/`, `gifs/`, `github/`, `inference-sh/`, `mcp/`, `media/`, `mlops/`, `note-taking/`, `productivity/` (airtable, google-workspace, linear, maps, nano-pdf, notion, ocr-and-documents, powerpoint, teams-meeting-pipeline), `red-teaming/`, `research/`, `smart-home/`, `social-media/`, `software-development/` (writing-plans, executing-plans, TDD, debugging, etc.), `yuanbao/` | REUSABLE | Generic, tool-and-domain skills. Reusable in template. Should be opt-in via wizard, not bundled-by-default. |
| `dogfood/` (SKILL.md + templates + references) | REUSABLE | Generic "dogfood your own agent" report skill. |
| `autonomous-ai-agents/` (claude-code, codex, hermes-agent, kanban-codex-lane, mailbox-coordination, opencode) | REUSABLE | Multi-agent coordination skills. Generic. |

**Total reusable skill categories**: 27. **TL-specific skill categories**: 1 (`twelvelabs/`, with 18 sub-skills).

## 2. TL-specific content categories — sanitization recipes

| Category | Where it appears | Sanitization recipe |
|---|---|---|
| **Employer-name string** | `profile.yaml.description`; `SOUL.md` (~10x); `memories/USER.md` (lead line); `memories/MEMORY.md` (~3x); `slack-manifest*.json` app `name`/`description` | Replace with `<<EMPLOYER>>` placeholder OR omit; wizard prompts for it (or accepts "(unset)"). |
| **Operator real name + role** | `profile.yaml`; `SOUL.md` H1 + Voice section; `USER.md` lead line | `<<OPERATOR_NAME>>`, `<<ROLE>>` placeholders. |
| **Internal Slack user IDs** (`U0xxxxxxx`) | `config.yaml: slack.extra.allow_admin_from`, `group_allow_admin_from` | Default empty string in template; wizard populates from `/whoami`-style flow. |
| **Discord channel/guild IDs + names** | `channel_directory.json` | Runtime-generated; template ships empty `{platforms: {}}`. |
| **Discord guild names + DM handles** | `channel_directory.json` | Same — empty-ship. |
| **Slack app manifest values** (app name, bot handle, slash command labels containing operator persona name) | `slack-manifest*.json`, `slack-slashes.json` | Template ships a manifest with `<<APP_NAME>>`, `<<BOT_HANDLE>>`, generic slash commands (`/ping`, `/status`, `/ask`). |
| **Agent fingerprint UUID** | `SOUL.md` H1 area ("Agent fingerprint: aahil-...") | Generated at profile-init; template uses `<<AGENT_FINGERPRINT>>` token replaced on first run. |
| **Network peer handles + pod names** | `SOUL.md` (multiple H2 sections like "With <peer>"); `USER.md`; `MEMORY.md` | Strip entirely. Template's persona has no peer-by-name sections; generic "How you collaborate" instead. |
| **Manager handle** | `USER.md` | Strip; wizard-optional. |
| **Internal repo paths** (operator's vault path under `~/Documents/Code/...`) | `MEMORY.md` (several) | Strip — no machine-local paths. |
| **Retired-service names + LaunchAgent labels** | `MEMORY.md` | Strip — no internal history. |
| **Cron job that syncs to a private vault repo** | `cron/jobs.json` first job (name/prompt/script reference) | Replace with a generic sample job, or ship empty `{jobs: []}`. |
| **Stack-percentage / workflow personal preferences** (`60% Python / 40% TypeScript`, TDD, "no em dashes") | `SOUL.md`, `USER.md` | These are reasonable defaults but presume the operator's profile. Move to a "personal preferences" wizard step with defaults blank. |
| **`tl-*` skill namespace** | `skills/twelvelabs/*` | **Do not ship.** Template provides equivalent generic skills under neutral category names (e.g. `software-development/`, `productivity/`) — these already exist in the same profile and ARE reusable. |
| **Bundled-manifest entries referencing `tl-*`** | `skills/.bundled_manifest` | Template ships a starter bundle of generic skills only. |
| **Provider auth tokens** | `auth.json`, `.env`, `.env.bak-*` | NEVER copy. Template ships `.env.example` only. |
| **Auto-generated SOUL marker** ("DO NOT EDIT. Generated from vault `self/` by `ops/scripts/<sync>.py`") | `SOUL.md` line 1 | Strip — template SOUL has no external generator dependency. |

## 3. Gaps in current `template/` (things aahil-sh has, template should also have, generically)

Concrete file paths assuming template root is `agentic-war-room/template/`:

- `template/profile/SOUL.md` — **MISSING in template? confirm**. Should ship a SKELETON persona with H1 + 6-8 H2 sections (Voice, How you talk, How you work, What you value, Communication, Writing Rules, Boundaries) — every line prefixed with `<<FILL-IN: ...>>` markers and NO real persona content.
- `template/profile/memories/MEMORY.md` — empty file with 1-line header comment explaining `§`-separator format.
- `template/profile/memories/USER.md` — empty file with same convention. (USER.md is operator-facts; MEMORY.md is session-flavored knowledge.)
- `template/profile/profile.yaml` — minimal `{description: "<<DESCRIBE YOUR AGENT>>", description_auto: true}`.
- `template/profile/config.yaml` — full default config (~590 lines), with org-specific keys neutralized:
  - `slack.extra.allow_admin_from: ""`, `group_allow_admin_from: ""`
  - `slack.allowed_channels: ""`, `discord.allowed_channels: ""`
  - `memory.memory_enabled: true` defaults kept
  - `personalities:` block kept (generic flavors are valuable demo content)
- `template/profile/channel_directory.json` — `{"updated_at": null, "platforms": {}}`.
- `template/profile/gateway_state.json` — empty file (0 bytes) or `{}`.
- `template/profile/gateway/discord_command_sync_state.json` — `{}`.
- `template/profile/discord_threads.json` — `{}`.
- `template/profile/slack-manifest.json` — generic manifest with `<<APP_NAME>>` placeholders; 1 starter slash command (`/ping` or `/status`).
- `template/profile/cron/jobs.json` — `{"jobs": []}` (empty list) OR one commented-out sample.
- `template/profile/hooks/README.md` — documents hook contract; dir is empty.
- `template/profile/scripts/README.md` — documents script discovery; dir is empty.
- `template/profile/skills/.bundled_manifest` — starter bundle (e.g. `software-development/writing-plans`, `software-development/test-driven-development`, `productivity/notion` (optional), `dogfood`).
- `template/profile/skills/.hub/taps.json` — empty `{taps: []}` plus the official skills-hub tap pre-registered.
- `template/profile/skills/<generic-categories>/` — copy of aahil-sh's REUSABLE categories (see section 1) minus `twelvelabs/`. Note: each individual `SKILL.md` in those categories should be re-read for stray org references before copying — most should be clean (they predate the `tl-*` work) but a spot-check is required.
- `template/profile/.env.example` — list of all expected env keys (DISCORD_TOKEN, SLACK_*, ANTHROPIC_API_KEY, etc.) with blank values.

**Patterns aahil-sh has that diverge from template's current approach (worth adopting):**

1. **The `§`-separator memory file convention** (USER.md, MEMORY.md) — template's plan currently references "agent memory" abstractly; this is the concrete on-disk shape.
2. **The `auto_thread`/`thread_require_mention`/`require_mention` Discord/Slack flags** in `config.yaml` — sane defaults are already encoded; template should preserve them.
3. **`personalities` block** with 12+ named flavors (kawaii/catgirl/pirate/etc.) — fun demo content that showcases the personality system without requiring operator input.
4. **`platform_toolsets` declarations** — these define which toolsets ship per platform (cli/slack/discord/telegram/...). Template needs this exact structure or platform routing breaks.
5. **`approvals.mode: manual` + `cron_mode: deny`** — safe defaults for public-facing template.
6. **`security.tirith_enabled: true` + `redact_secrets: true`** — safety defaults worth keeping.

## 4. "Must NEVER ship in template" blocklist

If we ever auto-copy from a profile, filter-out the following before landing:

**Files to drop entirely:**
- `auth.json`, `.env`, `.env.bak-*`, `.env.bak-*`
- `state.db`, `state.db-shm`, `state.db-wal`
- `sessions/**`
- `logs/**`, `cache/**`, `audio_cache/**`, `image_cache/**`, `home/**`, `lsp/**`
- `models_dev_cache.json`, `.skills_prompt_snapshot.json`
- `*.lock`, `*.pid`
- `cron/output/**`
- `skills/twelvelabs/**` (entire `tl-*` namespace)
- `skills/.usage.json`, `skills/.curator_state`
- `skills/.hub/audit.log`, `skills/.hub/index-cache/**`, `skills/.hub/quarantine/**`
- `slack-manifest-current.json`, `slack-manifest-merged.json` (keep `slack-manifest.json` template only)

**Key names to scrub before shipping (config.yaml & friends):**
- `slack.extra.allow_admin_from`, `slack.extra.group_allow_admin_from`
- `slack.allowed_channels`, `discord.allowed_channels`, `telegram.allowed_chats`, `matrix.allowed_rooms`, `mattermost.allowed_channels`
- `slack.channel_prompts`, `discord.channel_prompts`, `telegram.channel_prompts`, `mattermost.channel_prompts`
- `discord.dm_role_auth_guild`, `discord.server_actions`
- `dashboard.oauth.client_id`, `dashboard.oauth.portal_url`, `dashboard.public_url`
- `timezone`
- Any `*.api_key`, `*.base_url` value under `auxiliary.*`
- `kanban.orchestrator_profile`, `kanban.default_assignee`
- `delegation.api_key`, `delegation.base_url`

**Value patterns to flag** (regex):
- `U0[A-Z0-9]{9,}` (Slack user IDs)
- `T0[A-Z0-9]{9,}` (Slack team IDs)
- `\d{17,20}` in channel-directory-shaped JSON (Discord snowflakes)
- `aahil-[0-9a-f-]{36}` (agent-fingerprint format)
- Bare URLs to `*.internal`, `*.corp`, or any non-public domain
- Any reference to the employer brand name (string match — case-insensitive)
- Slack manifest `display_information.name` / `bot_user.display_name`
- Vault-style absolute paths (`/Users/<name>/Documents/...`)

**Persona content to strip on auto-copy:**
- SOUL.md sections matching `^## With ` (peer-by-name sections)
- SOUL.md "Agent fingerprint:" line
- The "DO NOT EDIT. Generated from vault..." banner
- USER.md and MEMORY.md contents entirely (they are operator-private)

## 5. Risks / unknowns

- **`mcp.json` is not in profile root.** The task brief assumed it exists; it does not. MCP servers appear to be wired via OAuth state in `auth.json` (which I did not deeply parse — it's secrets) and via plugin metadata under `skills/mcp/native-mcp/`. **Action needed:** confirm where the canonical "list of registered MCP servers" lives, because template needs an equivalent. If it's runtime-only (no on-disk static config), template doc should say "MCP servers are added via `hermes mcp add` not by editing a file."
- **Individual `SKILL.md` files in the REUSABLE category dirs were not exhaustively read** — only sampled. Spot-check before copying: any skill that mentions a vendor URL, employer name, or internal handle in its body must be sanitized. Particular candidates: `productivity/linear/`, `productivity/teams-meeting-pipeline/`, `mcp/native-mcp/`.
- **The `skills/dogfood/SKILL.md`** likely embeds operator workflow assumptions; needs a read pass before copy.
- **The `personalities:` block contents** in `config.yaml` are generic but include `kawaii`/`catgirl`/`uwu` flavors that may be considered unprofessional for a public template default. Consider trimming to 4-5 tasteful flavors (helpful/concise/technical/teacher/noir).
- **`SOUL.md` references a generator script** (`ops/scripts/<sync>.py`) outside the profile. Operator manages persona in an external vault. The template SHOULD NOT require this workflow — template's SOUL.md should be human-edited directly with no generator.
- **`gateway_state.json` is 0 bytes** in the live profile; unclear whether this is expected at idle or whether runtime writes JSON in. Worth checking the gateway source before deciding what template ships.
- **The `.bundled_manifest` schema was not read** (just file size noted). Before copying, confirm format and produce a sensible default bundle.
- **No `hooks/`, `scripts/`, `workspace/`, `plans/`, `pairing/` content exists** in aahil-sh, so the template has no example to mimic for these. Either ship empty + README, or research another profile that uses them.
- **Timezone field** in config.yaml is blank in aahil-sh (`timezone: ''`); template can ship blank too, but document that cron expressions depend on it.
- **`group_sessions_per_user: true`** is set in aahil-sh and probably reasonable as a template default — but confirm against the safety story (multi-user shared agent in Discord/Slack — do we want isolation by default?).

Source paths (all absolute): `/Users/aahil/.hermes/profiles/aahil-sh/` (root), `/Users/aahil/.hermes/profiles/aahil-sh/config.yaml`, `/Users/aahil/.hermes/profiles/aahil-sh/SOUL.md`, `/Users/aahil/.hermes/profiles/aahil-sh/profile.yaml`, `/Users/aahil/.hermes/profiles/aahil-sh/channel_directory.json`, `/Users/aahil/.hermes/profiles/aahil-sh/cron/jobs.json`, `/Users/aahil/.hermes/profiles/aahil-sh/memories/{MEMORY.md,USER.md}`, `/Users/aahil/.hermes/profiles/aahil-sh/skills/{twelvelabs/*, .bundled_manifest, .hub/}`.
