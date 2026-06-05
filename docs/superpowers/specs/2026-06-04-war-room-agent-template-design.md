# War-Room Agent Template — Design

- **Date:** 2026-06-04
- **Sub-project of:** Agentic War Room (AWR), layer **L4 / idea #1**
- **Status:** design approved, pre-implementation

## Context

AWR is the "problem-solver 9000": drop a problem into a war room and a swarm of
agents dogpiles it, coordinating so they never overlap. The coordination
substrate (L0) already exists in `coordination/` (file claims + lane claims on
one board, 168 tests). The README's open items are the Hermes integration layer
and an orchestrator (together: **L1**, "make one dogpile actually run").

This sub-project is **idea #1**, pulled ahead of L1 by owner choice: a
**fork-able template** so any person can stand up their own war-room agent.
It is designed to ship **standalone** — it does not hard-depend on L1 being
finished (see §7, the forward-compat stub).

### Key facts established during brainstorming

- **An agent is a Hermes agent.** Hermes (`Hermes Agent v0.15.1`) is an
  installed, git-based framework at `~/.hermes/hermes-agent` with its own
  `setup` wizard and `hermes update`. It is **not ours to distribute**, but it
  installs itself — the template only needs to say "install Hermes first, then
  drop in this profile."
- **Discord and Slack adapters ship with Hermes.** Bringing Discord up was "a
  credential + intent task, not a build" (per the aahil-sh `discord.md`
  playbook). The template wires credentials into existing adapters; it does not
  build integrations.
- **Hermes has a native profile-distribution mechanism.**
  `hermes profile install <git URL or local dir>` reads a `distribution.yaml`
  at the source root, creates the profile, and `hermes profile update` re-pulls
  the distribution **while preserving user data** (`.env`, state). This *is* the
  template engine — idea #1 = assembling a profile distribution.
- **A profile is just** `config.yaml` + `.env` + `SOUL.md` + `profile.yaml` +
  `skills/` + `hooks/`. The persona is literally one `SOUL.md`.
- **aahil-sh's persona pipeline** authors modular markdown in `self/*.md` and
  compiles it via `ops/scripts/aahil_sync.py` + `manifest.json` into both the
  Hermes `SOUL.md` and the Claude Code head `~/.claude/agents/aahil.md`. This is
  the "full-fidelity" (B) persona model we generalize here.
- **ccpkg's interactive installer** (`ccpkg/wizard.py`) is the canonical
  termios-style wizard pattern to match: a pure, I/O-free `WizardState`
  machine + a raw-mode termios renderer + a numbered fallback, stdlib-only,
  with graceful degradation. ccpkg's **base/overlay model** (scrubbed public
  base + private overlay for secrets/PII) is the secret-handling spine.

### Chosen direction

A **mix of B (full-fidelity, dual-runtime persona) and C (wizard-first)**, built
on native Hermes profile distribution, with **all terminal-based install steps
interactive in the ccpkg termios style**.

## Goals

1. A stranger can stand up their own war-room agent with one install command
   plus an interactive wizard — no hand-editing required (but possible).
2. The agent is dual-runtime: it produces a Hermes `SOUL.md` **and** a Claude
   Code head, from one modular persona source.
3. Discord + Slack work out of the box once tokens are supplied.
4. Secrets never enter the template repo; the repo is a public-safe scrubbed
   base.
5. The owner can push template improvements that `hermes profile update` applies
   without clobbering a user's secrets or persona.
6. Forward-compatible with the war room: a stub that activates when L1/L3 land,
   with no rework to the template's shape.

## Non-goals (YAGNI — separate sub-projects)

- Multi-agent topology / multi-tenant enrollment (idea #4).
- Severity / DEFCON escalation logic (idea #5) beyond a config stub.
- Real skill propagation across agents (idea #3).
- The actual dogpile / orchestrator behavior (L1).

This sub-project delivers **one personalizable, installable, dual-runtime
agent** — not the swarm.

## Architecture

### Repo layout

```
agentic-war-room/template/
  distribution.yaml          # Hermes profile-distribution manifest
  README.md                  # install + Discord/Slack portal provisioning checklist
  .env.example               # every token fill-in
  config.yaml                # discord{} + slack{} blocks + war_room{} defaults
  persona/                   # MODULAR persona source (the "B" part), with <<FILL-IN>> slots
    voice.md
    role.md
    decisions.md
    communication.md
    team.md
  manifest.json              # generator map: persona sections -> SOUL.md + Claude head
  bin/
    persona_sync.py          # stdlib generator (generalized aahil_sync), name-parameterized
  wizard/                    # ccpkg-pattern interactive setup, stdlib only, py3.9-safe
    state.py                 # pure I/O-free WizardState machine
    render.py                # raw-mode termios renderer + numbered fallback
    stages.py                # stages declared as data
    run.py                   # entrypoint; TTY detection -> raw vs fallback
  hooks/
    post_install.py          # Hermes post-install hook -> launches the wizard
  skills/
    warroom/                 # /warroom pre-brief bundle STUB (no-op until L2/L3)
  tests/
    test_wizard_state.py
    test_persona_sync.py
    test_distribution.py
    test_env_wizard_parity.py
```

### Components and responsibilities

Each unit has one clear purpose, a defined interface, and is independently
testable.

- **`distribution.yaml`** — declares the distribution to Hermes (name, version,
  requirements, source). Consumed by `hermes profile install`. *Interface:*
  whatever schema Hermes mandates (verify, §9). *Depends on:* nothing.
- **`config.yaml`** — Hermes profile config: `discord{}` + `slack{}` adapter
  blocks (mirroring aahil-sh defaults: `require_mention`, `auto_thread`, etc.)
  and a `war_room{}` block (stub). *Interface:* Hermes config schema.
- **`persona/*.md`** — modular persona source with `<<FILL-IN>>` slots. The
  single source of truth a user edits (directly or via the wizard).
  *Interface:* markdown sections named to match `manifest.json`.
- **`manifest.json`** — maps persona sections to two outputs (SOUL.md, Claude
  head), each with preamble/trailer. *Interface:* same shape as aahil-sh's
  `manifest.json`, name-parameterized.
- **`bin/persona_sync.py`** — pure generator: reads `persona/*.md` + manifest,
  emits `SOUL.md` and `~/.claude/agents/<name>.md` with a `DO NOT EDIT —
  generated` header. Supports `--check` (drift detection for hooks/CI).
  Stdlib-only. *Depends on:* persona files + manifest. *Used by:* the wizard
  (apply step) and any post-edit hook.
- **`wizard/state.py`** — `WizardState`: pure, I/O-free state machine
  (stages, cursor, selections, review, done). Unit-tested directly. Mirrors
  ccpkg's `WizardState`. *Depends on:* `stages.py` data only.
- **`wizard/render.py`** — two renderers driving the state: raw-mode termios
  TUI (arrow/space/Enter/Esc, hidden cursor, ANSI clear, review screen) and a
  numbered fallback for non-TTY/EOF, with graceful degradation
  (raw failure -> fallback). *Depends on:* `WizardState`.
- **`wizard/stages.py`** — the five stages declared as data (Identity, Persona,
  Channels, Model, War room) + the fields each collects.
- **`wizard/run.py`** — entrypoint: detect TTY, run the wizard, then **apply**
  (write `profile.yaml`, fill `persona/*.md`, run `persona_sync`, write `.env`,
  patch `config.yaml`), and persist answers to a profile JSON for `--yes`
  replay.
- **`hooks/post_install.py`** — Hermes post-install hook that launches
  `wizard/run.py`. *Depends on:* Hermes' post-install hook contract (verify).
- **`skills/warroom/`** — a documented no-op `/warroom` skill bundle
  (forward-compat). Becomes real when L1 + L3 land.

### Install -> wizard -> apply flow

```
hermes profile install <agentic-war-room/template | git>
   |
   |-- Hermes reads distribution.yaml -> creates the profile, lays down files
   |
   '-- hooks/post_install.py -> wizard/run.py:
         Stage 1  Identity   -> agent name / handle / owner user id   -> profile.yaml
         Stage 2  Persona    -> fill persona/*.md (or pick archetype)
                                -> persona_sync -> SOUL.md + ~/.claude/agents/<name>.md
         Stage 3  Channels   -> toggle Discord / Slack, collect tokens -> .env
         Stage 4  Model      -> provider + API key                     -> .env
         Stage 5  War room   -> enroll on a board                      -> config.yaml war_room{}
         Review  -> apply
         (answers persisted to a profile JSON; `--yes` replays headless)
```

### Wizard architecture (mirrors ccpkg)

- Pure I/O-free `WizardState` — all transitions (move, toggle, next/prev stage,
  review, confirm) are methods with no I/O; unit-tested without a terminal.
- Raw-mode termios renderer when both stdin/stdout are TTYs; otherwise the
  numbered fallback. Raw-mode failure (e.g. missing `termios`) degrades to the
  fallback. EOF/Ctrl-C aborts cleanly and restores the terminal.
- A final review screen confirms before apply. Stdlib-only, Python 3.9-safe.

### Persona generator — dual-runtime

`persona_sync.py` generalizes `aahil_sync.py`:
- `manifest.json` lists two `outputs`, each with `target`, `preamble`,
  `trailer`, and `sections` mapping to `persona/*.md`.
- Output 1: Hermes `SOUL.md` (persona-relevant sections).
- Output 2: Claude head `~/.claude/agents/<name>.md` (with `model:` frontmatter
  preserved).
- Fully name-parameterized — agent name/handle come from `profile.yaml`, never
  hardcoded.
- Both outputs carry a `DO NOT EDIT — generated from persona/` header.
- `--check` mode detects drift (for an optional post-commit hook / CI).

### Secret handling (base/overlay spine)

- `template/` is the **scrubbed base**: only `.env.example`; persona files hold
  placeholder content; zero real tokens. Safe to make public.
- Real secrets land **only** in the installed profile's `.env` (chmod 600,
  outside the repo). The repo never sees them.
- Optional private **overlay** repo lets a team share real persona content
  across installs.
- Hermes' native `profile update` preserves the user's `.env`/state on re-pull,
  so template improvements land without clobbering secrets.

### War-room enrollment — forward-compat stub

- Stage 5 writes a `war_room{board, role}` block to `config.yaml`.
- v1 ships a documented **no-op `/warroom` skill bundle**.
- It activates when **L1** (mailbox client wiring) and **L3** (skill packs)
  land. No change to the template's shape is required to turn it on — only the
  bundle's contents and a client call.

## Error handling

- **Not a TTY / piped input:** wizard uses the numbered fallback; `--yes`
  applies the saved profile or defaults with no prompts (so `update`/CI never
  block).
- **Missing `termios`:** raw renderer raises -> caught -> numbered fallback.
- **Ctrl-C / EOF mid-wizard:** abort, restore terminal (show cursor, reset
  raw mode), exit non-zero without partial apply.
- **Missing/invalid tokens:** wizard validates required keys per selected
  channel; apply writes only what was provided and the README documents the
  portal provisioning steps (Discord intents, Slack scopes).
- **Persona drift:** `persona_sync --check` exits non-zero when generated
  outputs are stale relative to `persona/*.md`.

## Testing (TDD — repo mandate)

- **`test_wizard_state.py`** — drive `WizardState` directly: navigation,
  toggling, stage transitions, review/back, done. No terminal (ccpkg pattern).
- **`test_persona_sync.py`** — golden-file tests: `persona/*.md` + manifest ->
  expected `SOUL.md` and Claude head; `--check` drift detection; name
  parameterization.
- **`test_distribution.py`** — `distribution.yaml` validates against the schema
  Hermes expects (once confirmed).
- **`test_env_wizard_parity.py`** — every key the wizard can write to `.env` is
  present in `.env.example`, and vice versa, so the two never drift.
- Renderers (raw/fallback) are thin over the pure state and covered by a
  fallback-path test feeding scripted input; the raw termios path is exercised
  manually (documented in README) since it needs a real TTY.

## Risks — RESOLVED by source research (2026-06-05)

All four pre-planning risks were resolved by reading Hermes v0.15.1 source
(`hermes_cli/profile_distribution.py`, `main.py`, `plugins.py`, `gateway.py`),
the aahil-sh profile, and ccpkg. Evidence lives in the plan's "Ground Truth"
section with `file:line` citations.

1. **Git-subdir install — NOT supported.** `hermes profile install <git URL>`
   shallow-clones the repo and checks only `<clone-root>/distribution.yaml`
   (`profile_distribution.py:407-416`). A **local directory** source works when
   `<dir>/distribution.yaml` exists at its root, so installing from `template/`
   locally is fine. Public git-URL install requires a root-level repo →
   resolved by a `git subtree split` **publish** step (plan Task 13).
2. **`distribution.yaml` schema — fully mapped** (`from_dict`,
   `profile_distribution.py:191-213`): `name` (required), `version`,
   `description`, `hermes_requires`, `author`, `license`, `env_requires[]`,
   `distribution_owned[]`. `source`/`installed_at` auto-written. Used verbatim
   in plan Task 0.
3. **Post-install hook — DOES NOT EXIST.** Install runs no author script
   (`VALID_HOOKS` is runtime-only; `install_distribution` only copies files).
   → personalization is an explicit `warroom setup` step; optional
   `on_session_start` sentinel guard for auto-run (plan Task 14).
4. **Native-flow overlap — clarified.** `hermes profile create/export/import`
   are plain-profile ops, **not** the distribution format; they do not collide
   with `profile install`. The wizard owns personalization; Hermes owns
   install/update/gateway. No duplication.

A late, higher-severity finding the original spec did not foresee:
**`hermes profile update` deletes and re-copies every shipped directory**
(`persona/`, `skills/`, `hooks/`) from source (`profile_distribution.py:560-582`).
A naive "user edits `persona/` in place" design would be silently wiped on the
first update. **Mitigation (now load-bearing):** user-editable state lives under
the user-owned `local/` namespace (in `USER_OWNED_EXCLUDE`), which `update`
never touches. See *Concurrency & state ownership* below.

---

# Engineering depth (treat this as a production system)

This template is small in LOC but is a *distributed, secret-handling,
multi-runtime* artifact installed on machines we do not control and updated
out-of-band. It is specified to the same bar as a full-stack service.

## A. System architecture & code structure

### A.1 Layered module graph (no cycles; imports point downward only)

```
                 ┌─────────────────────────────────────────┐
  interface      │ cli.py            render.py              │  (effectful edges: argv, TTY, ANSI)
                 └─────┬───────────────────┬────────────────┘
                       │                   │
  orchestration  ┌─────▼───────┐     ┌─────▼──────┐
                 │ setup.py    │     │ state.py   │           (state.py is PURE: no I/O)
                 └─┬───┬───┬───┘     └─────┬──────┘
                   │   │   │               │
  logic        ┌───▼─┐ │ ┌─▼────────┐ ┌────▼─────┐
               │prompts│ │persona_sync│ │ (uses)  │
               └───────┘ │  (pure fns)│ │selectables
                         └──────┬─────┘ └──────────┘
  data            ┌─────────────▼──┐ ┌───────────┐ ┌───────────┐
                  │ agent_model.py │ │ answers.py│ │selectables│  (leaf dataclasses + JSON IO)
                  └────────────────┘ └───────────┘ └───────────┘
```

**Import rules (enforced by a structural test, Task 16):**
- `selectables`, `agent_model`, `answers` import nothing from the package
  (leaves). `agent_model` may be imported by `persona_sync`/`answers`/`setup`.
- `state` imports only `selectables`. `state` performs **no I/O** (the purity
  guarantee that makes it unit-testable without a TTY).
- `render` imports `state` + `selectables` only; it owns all terminal I/O.
- `setup` is the only module allowed to import everything below it and is the
  only place side effects are composed; `cli` is a thin argv→`setup` adapter.
- No module imports `cli` or `setup` (prevents cycles).

### A.2 Single-responsibility + file budget

Each file does one thing and stays small enough to hold in context (soft cap
~200 lines; `render.py` is the largest at ~180). Responsibilities:

| File | Responsibility | Pure? |
|---|---|---|
| `selectables.py` | declarative toggle/text field catalog + stage bucketing | pure |
| `agent_model.py` | `AgentIdentity` + `local/agent.json` IO | IO-leaf |
| `answers.py` | persisted answers (`local/.warroom-setup.json`), secret-stripping | IO-leaf |
| `state.py` | wizard state machine (cursor/toggle/stage/review) | **pure** |
| `render.py` | raw-termios + numbered renderers; `run_wizard` | IO |
| `prompts.py` | line/secret text capture | IO |
| `persona_sync.py` | persona compiler (strip/assemble/substitute/write/--check) | pure core + write edge |
| `setup.py` | orchestration: seed overlay → resolve → collect → write → compile | composes effects |
| `cli.py` | argparse + exit codes | IO |

### A.3 Invariants (asserted in tests)
- **I1 — purity:** `state.py` never imports `os`/`sys`/`termios` and touches no
  stream. (grep-based structural test.)
- **I2 — substitution completeness:** no generated artifact contains `{{` after
  `persona_sync.run`.
- **I3 — env↔example parity:** every `ENV_FIELD_IDS` key exists in
  `.env.template`, and every non-comment `.env.template` key is reachable from a
  `TextField`.
- **I4 — secret containment:** no `SECRET_IDS` value ever appears in
  `local/.warroom-setup.json` or in stdout/stderr/logs.
- **I5 — overlay survival:** `seed_overlay` is idempotent and never overwrites an
  existing `local/persona/*.md`.
- **I6 — atomic writes:** every state file is written via temp+`os.replace`.

### A.4 Why stdlib-only (a real constraint, not dogma)
The package is **copied into the installed profile and run by the user's system
`python3`** — there is no install step that can `pip install` dependencies, and
adding any would mean vendoring or a network fetch at setup (a supply-chain +
offline-failure surface). `aahil_sync.py` and ccpkg are both stdlib-only for the
same reason. Consequence: **no PyYAML** → the persona param source is JSON
(`local/agent.json`), and `config.yaml`'s `war_room` block is edited with a
conservative line-based append (never a full YAML rewrite).

## B. Data model & schemas

| Artifact | Path | Owner | Lifecycle | Format |
|---|---|---|---|---|
| Distribution manifest | `distribution.yaml` | distribution | shipped; Hermes stamps `source`/`installed_at` | YAML |
| Profile config | `config.yaml` | distribution→user | shipped fresh; preserved on update | YAML |
| Env / secrets | `.env` (from `.env.EXAMPLE`) | **user** | never copied/overwritten | dotenv |
| Identity | `local/agent.json` | **user** | written by setup; survives update | JSON |
| Setup answers | `local/.warroom-setup.json` | **user** | written by setup; secrets stripped | JSON |
| Persona overlay | `local/persona/*.md` | **user** | seeded once; survives update | Markdown |
| Persona skeleton | `persona/*.md` | distribution | refreshed on update | Markdown |
| Generated SOUL | `SOUL.md` | generated | recompiled by `--sync` | Markdown |
| Generated head | `~/.claude/agents/<name>.md` | generated | recompiled; outside profile | Markdown |

**Schema versioning & migration.** v1 `load()` for both JSON files is already
**forward-compatible**: it reads known keys via `data.get(...)` defaults and
ignores unknown keys, so an older file or a newer-with-extra-keys file both load
without error (verified by `test_answers.py`/`test_agent_model.py`). A
`schema_version` integer field is **reserved** — it is not emitted today and is
added (with a `migrate(data)` shim) only when the first breaking shape change
lands, at which point absence is treated as version `1`. `config.yaml` carries
Hermes' own `_config_version` (observed `25`) — we never touch it. This avoids
shipping migration machinery before there is anything to migrate (YAGNI), while
the forward-compatible loader guarantees we can introduce it non-disruptively.

## C. Security model & threat model

### C.1 Trust boundaries
1. **Distribution author → installer.** A profile distribution is code+config
   copied onto the user's machine. **Mitigating fact (verified):** `hermes
   profile install` executes **no** author script — it only copies files and
   renames `.env.template`. So install itself is not a code-exec vector. The
   `warroom_setup` package is inert until the user explicitly runs it.
2. **Operator (setup-time) → local files.** The operator is trusted; inputs are
   validated for *correctness* (slug rules, token shape), not for *malice*.
3. **Channel users (runtime) → agent.** Discord/Slack/board messages are
   **untrusted**. This is the live prompt-injection surface and is governed by
   persona rules + channel config, not by the template's setup code.

### C.2 Asset inventory & secret lifecycle
Assets: model API key, Discord/Slack tokens, allowed-user IDs (PII-ish).
Lifecycle, end to end:
- **Entry:** secrets are entered via `getpass` (no terminal echo) on a real TTY;
  in headless/test paths via an injected stream.
- **At rest:** written **only** to `.env`, created with mode **0600**;
  `local/agent.json` and `local/.warroom-setup.json` written 0600; `local/` dir
  0700. Atomic temp+`os.replace` so a crash never leaves a half-written secret.
- **Never:** `SECRET_IDS` are stripped before `answers.save` (I4); secrets are
  never logged (`setup.log` records steps, not values); never echoed; never
  committed (`.gitignore` excludes `.env`, `local/`).
- **Update safety:** `.env` and `local/` are in `USER_OWNED_EXCLUDE` → a malicious
  or careless template update cannot exfiltrate or clobber them.

### C.3 Distribution / supply-chain posture
- **No install-time execution** (verified) — the headline supply-chain win.
- **Symlink rejection:** Hermes aborts install if the staged tree contains any
  symlink (`profile_distribution.py:435-446`). The template must contain none →
  asserted by a test (Task 16) so we never ship one and break installs.
- **Publish hygiene:** `scripts/publish.sh` runs `git subtree split` over
  `template/` only; `.env` and `local/` are git-ignored and never enter the
  history, so a published distribution carries zero secrets. (A test asserts no
  `.env`/`local/` is tracked.)
- **`hermes update` integrity:** updates re-pull from the recorded `source`;
  pin to a tag via the distribution `version` + release tags so users can audit
  diffs. (Note: Hermes' `#<ref>` git-pin is documented but unimplemented —
  publish to an immutable tag/branch the user chooses.)

### C.4 First-run hook = the one code-exec-on-start vector (opt-in, default off)
The optional `on_session_start` guard (Task 14) runs a shell script at first
agent start. With `hooks_auto_accept: true` this executes **without prompting**.
This is a genuine trade-off: convenience vs. an auto-run script in a downloaded
profile. **Decision:** ship it **disabled by default**; the explicit
`warroom setup` step is the recommended path. If enabled, it (a) only ever runs
`warroom setup --yes` (no network, no privilege change), (b) is sentinel-guarded
(`local/.setup-done`) so it runs exactly once, (c) is documented as requiring
informed consent. README states the security implication plainly.

### C.5 Input validation (setup-time)
- `agent_name`: must match `^[a-z][a-z0-9-]{0,63}$` (Hermes profile-name rule:
  lowercase/alphanumeric). Reject + reprompt otherwise.
- `handle`: same slug rule; defaults to `agent_name`.
- Token *shape* warnings (non-fatal): Slack bot `xoxb-`, app `xapp-`; empty
  required key → reprompt. We warn, never hard-block (a future token format
  could differ).
- `warroom.board`: slugified; bounded length.
- Path safety: setup only ever writes within `PROFILE_ROOT` and the computed
  head path; no user input is interpolated into a shell command (no `os.system`;
  gateway calls are explicit `hermes` subcommands the user runs, not setup).

### C.6 Runtime (agent) hardening carried by the template defaults
- `require_mention: true` on both Discord and Slack (no ambient response).
- Discord deny-by-default: without `DISCORD_ALLOWED_USERS`/roles the gateway
  denies everyone (documented).
- `max_attachment_bytes: 33554432` (32 MiB) and `history_backfill_limit: 50`
  bound resource use / context blow-up.
- Persona `decisions.md` ships an **"Untrusted Input and Prompt Injection"**
  section (data-not-instructions, no-exfiltration, no privilege escalation) so
  every generated SOUL/head carries the guardrail.

### C.7 STRIDE summary

| Threat | Vector | Control |
|---|---|---|
| **S**poofing | unauthorized channel user | `require_mention`, allowed-users deny-by-default |
| **T**ampering | malicious template update overwrites secrets | `local/` + `.env` in `USER_OWNED_EXCLUDE` |
| **R**epudiation | "who changed persona" | `setup.log` + git history of `local/` if user versions it |
| **I**nfo disclosure | secret leak to JSON/log/git | secret-strip (I4), 0600, `.gitignore`, getpass |
| **D**oS | huge attachment / backfill | byte cap + backfill limit |
| **E**oP | auto-run hook / injected instructions | hook opt-in + sentinel; persona injection rules |

### C.8 Dependency / CVE posture
Zero third-party dependencies → no transitive CVE surface, no lockfile, nothing
to `audit`. The only external trust is the Hermes runtime itself (out of scope;
the user installs and updates it). `pytest` is dev-only and never shipped in the
distribution payload.

## D. Efficiency & performance

- **Setup is O(files), single-pass, fully offline.** No network calls at any
  point in `warroom setup` (verifiable: a test asserts no `socket`/`urllib`
  import in the package). Cold-start is dominated by `python3` interpreter
  startup, not our code.
- **`persona_sync`** reads each source file exactly once, does one linear
  `str.replace` pass per placeholder per output, and writes each target once.
  No quadratic assembly. Worst case ≈ (#outputs × #sections) small file reads.
- **Idempotent + cheap re-runs:** `--sync` skips all prompts and only
  recompiles; `seed_overlay` no-ops on already-seeded files; `--yes` replays
  without I/O-bound prompting.
- **`hermes profile update` cost:** user content under `local/` is never
  recompiled or recopied — only the small shipped skeleton refreshes — so update
  is bounded by distribution size, not user data size.
- **Memory:** all files are small Markdown/JSON; everything is read fully into
  memory intentionally (KB-scale). No streaming needed.

## E. Reliability — failure modes & recovery (fail-open vs fail-closed)

| Failure | Behavior | Posture | Recovery |
|---|---|---|---|
| Not a TTY / piped stdin | numbered fallback renderer | fail-open | n/a |
| `termios` missing/raw fails | fall back to numbered renderer | fail-open | n/a |
| Ctrl-C / EOF mid-wizard | restore cursor+raw mode; exit 130; **no partial apply** | fail-closed | re-run `warroom setup` |
| Required field empty at EOF | stop, write nothing for it, warn | fail-closed | re-run |
| `agent.json` missing on `--sync` | exit 2 with "run setup first" | fail-closed | run `warroom setup` |
| Persona source file missing | `persona_sync` raises `FileNotFoundError` (loud) | fail-closed | restore from skeleton / re-seed |
| Unclosed frontmatter in persona | `ValueError` (loud, names the file) | fail-closed | fix the file |
| `config.yaml` already has `war_room:` | left untouched (no double-write) | safe | edit manually |
| Half-written file (crash) | temp file orphaned, target intact (atomic replace) | safe | delete `*.tmp` |
| `hermes update` wipes skeleton edits | only `persona/` skeleton refreshes; `local/` intact | safe-by-design | `--sync` after update |

Principle: **fail-open for ergonomics (rendering), fail-closed for correctness
(identity, secrets, persona).** Never apply a partial/ambiguous result silently.

## F. Observability & logging

- `warroom setup` prints a human-readable step trace to stdout and a structured
  next-steps block at the end. The optional first-run hook appends to
  `local/setup.log`.
- **Logging rules:** record *what* happened (`wrote SOUL.md`, `seeded overlay`,
  `enrolled board=<name>`), never secret *values*. Log lines are greppable and
  prefixed by phase.
- `persona_sync --check` emits a unified diff to stderr and exit 1 on drift —
  suitable for a git pre-commit hook / CI drift gate on `local/persona`.
- Exit codes are a stable contract (see §G).

## G. Concurrency & state ownership

- **Single-writer ownership.** Exactly one running gateway binds a profile's
  channel tokens (Hermes single-owner rule). `warroom setup` is an
  operator-invoked, non-concurrent tool — it is **not** designed for two
  simultaneous runs; atomic writes mean the last writer wins without corruption,
  but the operator should not race it against a live gateway. Recommend
  `gateway stop` → `setup` → `gateway restart` when changing identity.
- **State ownership matrix** is the heart of update-safety (§B table): anything
  the user edits lives under `local/` (Hermes-owned-by-user); anything the
  distribution ships and may overwrite lives at the profile root. Generated
  outputs are derivable and never hand-edited.
- The AWR coordination substrate (file/lane claims) is the concurrency story for
  *multiple agents* — out of scope here, wired via the `/warroom` stub.

**Exit-code contract:** `0` ok · `2` usage/precondition (no identity, no
command) · `130` user-cancelled (Ctrl-C). `persona_sync --check` adds `1` =
drift detected.

## H. Operational runbook

- **Install (local):** `hermes profile install <path>/template --name <n>`
- **Install (public):** publish via `scripts/publish.sh`, then
  `hermes profile install <git-url> --name <n>`
- **Personalize:** `bash scripts/setup.sh [--reconfigure|--sync|--yes]`
- **Run:** `hermes -p <n> gateway install && hermes -p <n> gateway restart`
- **Update:** `hermes profile update <n>` then `bash scripts/setup.sh --sync`
- **Rollback:** `local/` is user-owned; keep it under git for per-edit rollback.
  Distribution rollback = `hermes profile install <git-url>@<older-tag> --force`
  (user data preserved).
- **Uninstall:** `hermes profile delete <n>` (warn: removes `local/` too — back
  it up first).
- **Verify health:** `hermes -p <n> gateway status`;
  `python3 -m warroom_setup.persona_sync --check` for drift.

## I. Test strategy & coverage matrix

Layers: **unit** (pure logic), **integration** (multi-module against `tmp_path`),
**security** (negative assertions), **e2e** (real `hermes profile install`,
manual/documented). TTY-free patterns from ccpkg: scripted `io.StringIO`,
`os.pipe()` + `SIGALRM` for `_read_key` non-block, `pty.openpty()` for raw mode.

| Concern | Test(s) | Type |
|---|---|---|
| distribution schema/root/`.env.template` | `test_distribution.py` | unit |
| identity IO + substitution keys | `test_agent_model.py` | unit |
| compiler strip/assemble/substitute/--check | `test_persona_sync.py` | unit+integration |
| manifest compiles against seeded overlay | `test_persona_sync.py::shipped_manifest` | integration |
| stage model/order/defaults | `test_selectables.py` | unit |
| state machine transitions | `test_state.py` | unit (pure) |
| renderers (fallback + key decode) | `test_render.py` | unit |
| text/secret prompts, enable_if, required | `test_prompts.py` | unit |
| answers roundtrip + **secret-strip** | `test_answers.py` | unit+security |
| overlay seed idempotency, `.env` merge, run_setup | `test_setup.py` | integration |
| CLI flags, exit codes, Ctrl-C→130 | `test_cli.py` | unit |
| `/warroom` bundle resolves to a real skill | `test_warroom_bundle.py` | unit |
| **security:** no secrets in answers/log; `.env` is 0600; no `socket`/`urllib` import; no symlinks shipped; import-graph has no cycles; I1 purity | `test_security.py` | security/structural |
| e2e install → setup → update-preserves-overlay | Task 15 (manual) | e2e |

Coverage gate: the full suite (`pytest -q`) must be green before publish; the
security/structural tests are non-optional.

## J. Code quality standards & invariants
- Python ≥3.9, **stdlib only**, `# type:` comment hints (3.9-safe), no PEP 604
  unions (matches ccpkg/aahil_sync).
- Every state-mutating write is atomic (temp+`os.replace`) and permission-scoped.
- Dataclasses for all models; no ad-hoc dicts crossing module boundaries.
- Functions are small and mostly pure; side effects isolated to `setup`/`render`/
  IO-leaf `save` functions.
- No `os.system`/`shell=True`; no string-built shell commands from user input.
- Docstrings cite the Hermes/ccpkg `file:line` ground truth they depend on.



## Open follow-ups (future sub-projects, not this spec)

- L1: Hermes integration layer + orchestrator (makes `/warroom` real).
- #4: multi-agent / multi-team topology built on this template.
- #5: severity/DEFCON model feeding the `war_room{}` block.
- #2/#3: skill pre-brief packs + propagation via Hermes `bundles`/`skills tap`.
