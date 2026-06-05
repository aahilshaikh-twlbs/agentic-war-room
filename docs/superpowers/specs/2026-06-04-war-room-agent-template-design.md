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

## Risks / to verify during planning

1. **`hermes profile install` from a git *subdir*.** The "permanent subdir"
   layout puts the distribution at `agentic-war-room/template/`. Local-dir
   install (`hermes profile install ./template`) is fine; **git-URL-to-subdir
   may not be supported**, so publishing publicly might need a step that exports
   `template/` to its own repo root. Confirm Hermes' behavior before committing
   to the public install story.
2. **Exact `distribution.yaml` schema.** Confirm required fields
   (version / requirements / source / post-install hook declaration) by
   inspecting a known distribution or Hermes docs.
3. **Hermes post-install hook contract.** Confirm how a distribution declares a
   post-install step and how it is invoked, so `hooks/post_install.py` fires the
   wizard reliably.
4. **Overlap with Hermes' native `setup` / `profile create`.** Ensure the
   wizard complements (does not duplicate / fight) native flows; prefer calling
   native commands where they already do the job.

## Open follow-ups (future sub-projects, not this spec)

- L1: Hermes integration layer + orchestrator (makes `/warroom` real).
- #4: multi-agent / multi-team topology built on this template.
- #5: severity/DEFCON model feeding the `war_room{}` block.
- #2/#3: skill pre-brief packs + propagation via Hermes `bundles`/`skills tap`.
