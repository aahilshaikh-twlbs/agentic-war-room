# Skill Pre-Brief Packs + Propagation — Design

- **Date:** 2026-06-09
- **Sub-project of:** Agentic War Room (AWR). Extends the **war-room agent
  template** (`template/`) — specifically its `skills/`, `skill-bundles/`, and
  distribution-manifest surface — and rides the **Hermes distribution +
  skills-hub** machinery (`hermes profile install/update`, `hermes bundles`,
  `hermes skills tap`). Ideas #2/#3 from the original template spec.
- **Depends on:** the template's static-file distribution model (whole `template/`
  tree copied by `hermes profile install`); the confidence-gate Layer 1 skill
  (`template/skills/confidence-gate/SKILL.md`); the `warroom` skill + bundle; the
  persona-sync path (`manifest.json` → `SOUL.md`). No dependency on multi-board
  federation or the DEFCON model.
- **Referenced by:** `2026-06-09-awr-l1-orchestrator-design.md` (the L1
  orchestrator is the natural first *consumer* of a pre-brief pack — `/warroom`
  becomes the pack's slash entry). Loosely related to
  `2026-06-09-awr-multi-board-federation-design.md` and
  `2026-06-09-awr-defcon-severity-design.md` (both add skills/knowledge a pack
  would later bundle), but this spec stands alone.
- **Status:** design, pre-implementation.

## Problem

Every war-room agent needs the same baseline behavior loaded *before* it does
anything: the confidence-gate protocol, the mailbox coordination commands, and
(eventually) persona/severity/orchestration rules. Today these ship as **loose,
individually-invoked skills**:

- `template/skills/confidence-gate/SKILL.md` and `template/skills/warroom/SKILL.md`
  are separate skills.
- `template/skill-bundles/warroom.yaml` already groups them under one `/warroom`
  slash command (`skills: [warroom, confidence-gate]`).
- **Nothing auto-loads on session start.** A Hermes bundle is loaded *only when
  the user (or a hook) types `/<slug>`* — verified in the runtime:
  `build_bundle_invocation_message` is invoked by slash dispatch, never by
  SessionStart (`agent/skill_bundles.py:255`). So "all agents load the gate on
  startup" is currently aspirational; in practice the gate fires only because its
  *behavioral* contract is also baked into persona text, and the *structural*
  enforcement is the Layer 2 plugin, not the skill.

Two distinct wants, both unsolved:

1. **Pre-brief pack** — a *named, versioned set* of skills **plus shared knowledge
   docs** that constitute "the briefing every war-room agent has read before its
   first message," with a defined, reliable way to make that briefing *present in
   context on startup* — without editing `~/.claude/settings.json` (locked
   decision #9).
2. **Propagation** — when the pack's content changes (a sharper gate rule, a new
   mailbox verb, an updated org doc), a defined path for that update to reach
   **already-installed agents** across a fleet, with a clear push-vs-pull story and
   a security posture for skill content that is executable-ish instruction.

This spec defines what a pack *physically is*, how it loads on startup, how it
versions and survives `hermes profile update`, and how updates propagate — and
flags every meaningful fork as an **Open Decision** (we did not brainstorm this
with the user).

## Core decisions

These are the load-bearing choices. Each contested one carries an **Open
Decision** with a recommendation.

1. **A pack is a curated trio: a bundle + its skills + a meta knowledge doc.** Not
   a single SKILL.md, not a bare bundle. Concretely: a `skill-bundles/*.yaml`
   that names the member skills, the member `skills/<name>/SKILL.md` bodies, and a
   **pack knowledge doc** (`shared/prebrief/<pack>.md`) that is the human-readable
   briefing and the manifest-of-record for the pack. The bundle is the *runtime
   loader*; the knowledge doc is the *briefing + version anchor*.
2. **Startup load = persona-injection of a pointer + an opt-in `/warroom`
   expansion — never a settings.json hook.** SOUL.md (always loaded by Hermes at
   session start) and the Claude head agent file (`~/.claude/agents/<name>.md`)
   gain a generated "Pre-brief" section, emitted by the existing persona-sync
   manifest. That guarantees the *briefing summary + the gate contract* are in
   context turn 1 with zero settings edits. The full skill bodies remain a
   `/warroom` (bundle) expansion the agent or operator can pull on demand.
3. **Propagation reuses Hermes' two existing, verified channels — no new
   mechanism.** (a) *Whole-pack* updates ride `hermes profile update`
   (distribution re-pull; replaces distribution-owned paths in place). (b)
   *Individual hub skills* ride `hermes skills tap` + `hermes skills update`
   (lock-file provenance, pull-based). We do not invent a bespoke transport.
4. **Propagation is pull-on-update, not push.** Both Hermes channels are pull: the
   operator (or a cron) runs `hermes profile update <name>` / `hermes skills
   update`. There is no AWR-side push to running sessions; a pack change lands on
   the *next* session of an updated profile. (See Open Decision P-2 for an opt-in
   nudge.)
5. **Packs version explicitly and pin via the user-owned `local/` namespace.** The
   pack doc carries a `pack_version`; the distribution carries `version`. User
   overrides/pins live under `local/` (never touched by update), so an operator can
   freeze a pack against a noisy upstream.
6. **Security is first-class: skills are untrusted-by-default instruction.**
   Propagated skill content is treated as a supply-chain surface. We lean on
   Hermes' `skills_guard.py` scan for tap-installed skills, ship only
   first-party packs in the distribution, and never auto-trust a tapped repo.
7. **Comprehensive scope, phased build.** This spec covers the full feature —
   pack format, startup injection, distribution propagation, hub-tap propagation,
   versioning/pinning, and the operator surface. Sequencing lives in **Build
   order**, not in omission.

> **Open Decision (D-1) — what a pre-brief pack physically IS.** Candidates:
> (a) one big `SKILL.md`; (b) a bare `skill-bundles/*.yaml`; (c) **a bundle + its
> member skills + a `shared/prebrief/<pack>.md` knowledge doc** (recommended).
> **Recommendation: (c).** A single SKILL.md cannot be both the always-loaded
> briefing and a `/slug`-expandable bundle, and it forces everything into one
> file. A bare bundle has no always-loaded surface (bundles only load on `/slug`)
> and no place for prose knowledge. The trio cleanly separates *loader* (bundle),
> *protocol bodies* (skills), and *briefing + version anchor* (knowledge doc), and
> every piece already has a shipped precedent in the repo.

## Current state (VERIFIED against `template/` + real Hermes source, 2026-06-09)

Hermes source inspected at `~/.hermes/hermes-agent/` (the live install). Paths
below are real; Hermes-side behaviors are flagged where a future Hermes version
could break an assumption (per handoff §0 plan-defect class #4).

**Template artifacts (shipped today):**
- `template/skills/confidence-gate/SKILL.md` — Layer 1 anti-hallucination
  protocol; frontmatter has `name`, `description`, and `metadata.hermes.tags:
  [coordination, war-room, safety]` (`SKILL.md:1-7`).
- `template/skills/warroom/SKILL.md` — coordination commands; frontmatter `name`
  + `description` only (`SKILL.md:1-5`).
- `template/skills/assimilate-warroom/SKILL.md` — opt-in "join the war room"
  trigger skill (not in the bundle).
- `template/skill-bundles/warroom.yaml` — the one shipped bundle:
  `skills: [warroom, confidence-gate]`, plus a top-level `instruction:` field
  (`warroom.yaml:1-7`).
- `template/skills/.hub/taps.json` — **empty registry `{"taps": []}`**
  (`taps.json:1-3`). NOTE: the handoff §7 said "one tap shipped"; **that is stale
  — the shipped registry is empty.** The official taps are *built into the
  runtime* (see below), so the registry only needs entries for *extra* sources
  (`template/skills/.hub/README.md:5-14`).
- `template/skills/.bundled_manifest` — **ships empty (0 bytes)**. It is a
  runtime-managed `name:hash` integrity cache; a skill listed there but absent
  from `skills/` is treated as user-deleted and suppressed, so shipping it empty
  is deliberate (`.hub/README.md:16-22`; guard `test_template_content.py:78-88`).
- `template/shared/org.md` — the one shared knowledge doc today; persona-sync
  injects it as "Org context" into both the Claude head and SOUL.md
  (`manifest.json:10,28`).
- `template/SOUL.md` — always-loaded persona skeleton, regenerated from
  `local/persona/*.md` by `warroom setup --sync` via `manifest.json`.
- `template/distribution.yaml` — `name: war-room-agent`, `version: 0.1.0`,
  `distribution_owned: [SOUL.md, config.yaml, skills, cron, distribution.yaml]`.
  **`skill-bundles` and `shared` are NOT in this list** (`distribution.yaml:30-35`).

**Hermes runtime behavior (VERIFIED in source; flag-for-reverify on version bump):**
- **Bundles live under `<HERMES_HOME>/skill-bundles/*.yaml`** and load N skill
  bodies into one user message *on `/<slug>` invocation only* —
  `build_bundle_invocation_message` (`agent/skill_bundles.py:255-345`), reached by
  slash dispatch, NOT by SessionStart. *Dropping a YAML into the dir registers a
  bundle* (`agent/skill_bundles.py:9-24`). **`<profile>` is `<HERMES_HOME>` when
  the profile is active** (handoff §0 Hermes notes), so the shipped
  `template/skill-bundles/warroom.yaml` lands at the right path.
- **Distribution copy/update — `hermes_cli/profile_distribution.py`:**
  `_copy_dist_payload` (`:545-591`) iterates **every top-level entry** of the
  staged source and copies anything **not** in `USER_OWNED_EXCLUDE`
  (`:100-119`, which includes `local`, `.env`, `memories`, `sessions`, etc.). For
  a dir it does `rmtree(dest)` + `copytree`. **Consequence:** `skill-bundles/` and
  `shared/` *do* propagate on `profile update` via the catch-all copy even though
  they're absent from `distribution_owned` — but the manifest's
  `distribution_owned` list is the *documented contract* and omits them, a real
  discrepancy this spec resolves (add them explicitly).
- `config.yaml` is distribution-owned but **preserved on update** unless
  `--force-config` (`:568-570`); user data (`local/`, `.env`, memories, sessions,
  state dbs) is never touched (`:100-119, 563-564`).
- `update_distribution` re-pulls from the profile's recorded
  `distribution.yaml::source` and re-applies the same copy
  (`profile_distribution.py:653-693`). Pull-based, operator-initiated.
- **`hermes bundles`** = list/show/create/delete/reload over the bundles dir
  (`hermes_cli/bundles.py:1-13`); CRUD only, no startup hook.
- **`hermes skills tap`** (`hermes_cli/skills_hub.py:1235`) edits `taps.json`
  (extra GitHub sources). **`DEFAULT_TAPS`** is hard-coded in the runtime
  (`tools/skills_hub.py:395-413` — openai/anthropics/huggingface/NVIDIA/etc.), so
  the official hub needs no registry entry.
- **`hermes skills update`** is **pull-based**: it reads `.hub/lock.json`
  provenance, asks each source if an update is available, and re-installs the ones
  that are (`hermes_cli/skills_hub.py:946-963`; lock = `tools/skills_hub.py:3022`).
- **Security gate exists:** tap/hub-installed skills are scanned by
  `tools/skills_guard.py` with a `TRUSTED_REPOS` allowlist before install
  (`do_audit` re-runs it; `hermes_cli/skills_hub.py:965+`).
- Skill-dir hard-exclusion (locked decision #5): `is_excluded_skill_path` /
  `EXCLUDED_SKILL_DIRS` (`agent/skill_utils.py:27-62`) skip `.git`, `node_modules`,
  etc. when counting/copying skills — packs must avoid those dir names.

> **VERIFY-AGAINST-HERMES (do before building):** (1) confirm bundles still do not
> auto-load on SessionStart in the target Hermes version — the whole startup-load
> design depends on it; (2) confirm `_copy_dist_payload`'s catch-all copy still
> propagates non-`distribution_owned` top-level dirs (so `skill-bundles/`/`shared/`
> ride along) — if a future Hermes restricts the copy to `owned_paths()` only, the
> manifest MUST list them or propagation silently stops; (3) confirm
> `<HERMES_HOME>/skill-bundles` is the scanned path for an installed profile.
> Handoff §0 explicitly warns that Hermes-side behavior breaks plans that assume
> otherwise — these three are exactly that class.

All changes below are **additive and backward-compatible**: today's loose skills
and the `/warroom` bundle keep working; a profile with no pre-brief doc behaves
exactly as it does now.

## Architecture & components

Three layers, mirroring the existing split:

- **`template/` (the pack itself):** the bundle, member skills, the pack knowledge
  doc, the persona-sync wiring that injects the briefing on startup, and the
  manifest declaration that makes the pack distribution-owned.
- **`warroom_setup/` (the producer/sync):** generate the SOUL.md / head-agent
  "Pre-brief" section from the pack doc, compute/record the pack version, and
  expose `warroom prebrief` operator verbs (stdlib-only).
- **Hermes (the transport):** `profile update` for whole-pack propagation; `skills
  tap`/`skills update` for individual hub-skill propagation. We touch *no* Hermes
  code; we only ship files into its scanned paths and document the verbs.

### 1. Pack format — the trio (`template/`)

A pre-brief pack named `<pack>` is:

- **Loader:** `template/skill-bundles/<pack>.yaml` — a Hermes bundle naming the
  member skills (existing shape; the shipped `warroom.yaml` *is* the v1 pack
  loader).
- **Bodies:** `template/skills/<member>/SKILL.md` for each member (confidence-gate,
  warroom, …).
- **Briefing + anchor:** `template/shared/prebrief/<pack>.md` — a markdown doc
  with frontmatter (`pack`, `pack_version`, `members:`, `summary:`) and a prose
  briefing. This is the *one file an operator reads to know what the pack is*, and
  the source the persona-sync pulls the startup summary from.

> **Open Decision (D-2) — does the pack doc live in `shared/` or a new
> `prebrief/` top-level dir?** **Recommendation: `template/shared/prebrief/`.**
> `shared/` is already the "knowledge injected into persona outputs" home
> (`shared/org.md`), and persona-sync already reads from it (`manifest.json`).
> Reusing it means the briefing flows through the *existing* sync path with no new
> machinery. A new top-level dir would need explicit `distribution_owned` +
> sync-source wiring for no gain.

### 2. Startup load — persona injection, not a hook (`template/` + `warroom_setup/`)

The locked decision is absolute: **war-room code never edits
`~/.claude/settings.json`** (decision #9). So "load on startup" is realized
through the surfaces Hermes/Claude already load unconditionally:

- **SOUL.md** (Hermes loads it every session) and **`~/.claude/agents/<name>.md`**
  (the Claude head, also always loaded) each gain a generated **"War-room
  pre-brief"** section. Content = the pack doc's `summary` + the *condensed gate
  contract* (the confidence envelope + the "abstain below threshold" rule) +
  "run `/warroom` to load the full protocol." This is emitted by the **existing
  persona-sync manifest** (`manifest.json`) — we add a `prebrief` section sourced
  from `shared/prebrief/<pack>.md`, exactly like the current "Org context" section
  is sourced from `shared/org.md`.
- **Full bodies on demand:** the agent (or operator) runs `/warroom` to expand the
  whole bundle into context when it actually needs the verbatim commands. The
  briefing in SOUL guarantees it *knows the gate exists and knows to do this*.

This means: **turn-1 context always contains the briefing + the gate rule; the
exhaustive skill text is a cheap `/warroom` away.** Zero settings.json edits, zero
new hooks, and it composes with the Layer 2 structural plugin (which enforces the
gate regardless of whether the skill body is loaded).

> **Open Decision (D-3) — how literally "loaded" must the *full* skill bodies be on
> turn 1?** Options: (a) **briefing-summary-in-SOUL + `/warroom` for full bodies**
> (recommended); (b) auto-fire `/warroom` via the mailbox SessionStart hook's
> output (the hook already runs and can print a UserPromptSubmit-style nudge);
> (c) inline the *entire* gate + mailbox bodies into SOUL. **Recommendation: (a),
> with (b) as an opt-in.** (c) bloats every session's base context and duplicates
> the skill bodies (drift risk). (b) is attractive but couples startup-load to the
> mailbox hook's behavior — viable as an *enhancement* (the hook can emit "war-room
> pre-brief active; `/warroom` for the full protocol"), but the *guarantee* should
> rest on the always-loaded SOUL section, which we fully control via persona-sync.

### 3. Whole-pack propagation — `hermes profile update` (Hermes transport)

The primary propagation channel for a *first-party* pack is the distribution
itself. Because the whole `template/` tree is the distribution source, a pack
update is just a new commit + a bumped `distribution.yaml::version`. An operator
runs `hermes profile update <name>`; `_copy_dist_payload` replaces the
distribution-owned tree (skills, bundle, pack doc) while preserving `config.yaml`
(unless `--force-config`) and never touching `local/`/`.env`/memories.

To make this **explicit and contract-correct**, `distribution.yaml` MUST add
`skill-bundles` and `shared` to `distribution_owned` (today the catch-all copy
carries them, but the manifest doesn't declare it — a latent break if Hermes ever
tightens the copy to `owned_paths()`).

### 4. Individual-skill propagation — `skills tap` + `skills update` (Hermes transport)

For agents that were *not* installed from this distribution (e.g. an existing
profile that ran `assimilate-warroom`), whole-distribution update doesn't apply.
For them, a pack member can be published as a **hub skill** in a first-party
GitHub repo and propagated via:

- `hermes skills tap add <owner>/<repo>` — register the source (writes
  `taps.json`).
- `hermes skills install <owner>/<repo>/<skill>` — pull-install (scanned by
  `skills_guard`, recorded in `lock.json`).
- `hermes skills update [<name>]` — pull the latest for already-installed skills.

This is the path the handoff's "propagation via `skills tap`" gesture refers to.
It is **per-skill, pull-based, and security-scanned** — the right channel for
distributing a single sharpened skill (e.g. an updated `confidence-gate`) to a
heterogeneous fleet that wasn't all built from the same distribution.

> **Open Decision (P-1) — distribution-update vs hub-tap as the *primary*
> propagation path.** **Recommendation: distribution-update is primary for
> template-born agents; hub-tap is the secondary path for assimilated/foreign
> agents.** They're complementary, not competing: a template-born fleet updates
> atomically via `profile update` (pack stays internally consistent — bundle +
> bodies + doc move together); a foreign profile can still receive a single
> sharpened skill via the hub. Do NOT try to make every agent a hub consumer — it
> fragments the pack (the bundle/doc wouldn't travel with a single tapped skill).

> **Open Decision (P-2) — push vs pull to *already-installed* agents.** Both Hermes
> channels are **pull** (operator runs the update; the change lands next session).
> A true push to a *running* session is out of scope (would require a Hermes hook
> we won't add, per locked decision #9). **Recommendation: stay pull; add an
> optional *nudge* via the mailbox.** A new `mailbox` broadcast convention — e.g.
> an operator runs `warroom prebrief announce --version <v>` which posts a board
> message "pre-brief pack updated to v<v>; restart to pick it up" — gives the fleet
> a *soft* push signal without any settings/hook change. The actual content still
> arrives via the next `profile update` + session restart.

### 5. Versioning + pinning (`template/` + `warroom_setup/`)

- **Pack version** lives in `shared/prebrief/<pack>.md` frontmatter
  (`pack_version`) AND is mirrored into the persona-injected SOUL section so a
  running agent can *state which pack it briefed against* (observability).
- **Distribution version** (`distribution.yaml::version`) is the coarse-grained
  "everything moved" anchor; bump it on any pack change so `hermes profile info`
  shows drift.
- **Pinning/override = the user-owned `local/` namespace.** Update never touches
  `local/`. An operator who wants to freeze the briefing creates
  `local/prebrief/<pack>.md`; persona-sync prefers `local/prebrief/<pack>.md` over
  `shared/prebrief/<pack>.md` when present (same override pattern persona already
  uses: `local/persona/*` is authoritative over the `template/persona/*`
  skeletons). This gives a clean pin with zero new config keys.

> **Open Decision (V-1) — pin granularity.** Options: (a) pin the *whole pack* via
> a `local/prebrief/` override (recommended, simplest, matches the persona
> override model); (b) per-skill pins in `config.yaml` (`war_room.prebrief:
> {confidence-gate: "1.2.0"}`); (c) lock-file-style pin. **Recommendation: (a) for
> v1.** Per-skill pinning is real complexity (Hermes' hub already has `lock.json`
> for hub skills; we shouldn't reimplement it for distribution skills). A
> whole-pack `local/` override is the 80% case — "I don't want upstream changing
> my briefing right now."

### 6. Operator surface — `warroom prebrief` (`warroom_setup/`, stdlib-only)

A small CLI surface (stdlib `argparse`, no deps) parallel to `warroom setup` /
`warroom enroll`:

| Verb | Purpose |
|---|---|
| `warroom prebrief show [<pack>]` | print the pack doc, members, version, and which members are installed |
| `warroom prebrief verify` | check pack integrity: every `members:` entry resolves to a `skills/<m>/SKILL.md`; bundle lists them; pack doc version present |
| `warroom prebrief sync` | (re)generate the SOUL/head "Pre-brief" section from the pack doc (delegates to the existing persona-sync) |
| `warroom prebrief announce --version <v>` | (opt-in, P-2) post a fleet nudge on the mailbox board |
| `warroom prebrief pin` / `--unpin` | copy `shared/prebrief/<pack>.md` → `local/prebrief/<pack>.md` (pin) / remove it |

`verify` is the high-value one: it catches the failure mode the existing
`test_warroom_bundle.py` already guards against at test time ("a bundle would be
suppressed if the skill does not resolve") and surfaces it as an operator check.

## Data model & config

**The pack knowledge doc** (`template/shared/prebrief/<pack>.md`):

```markdown
---
pack: warroom
pack_version: 1.0.0
summary: >
  Every war-room agent has read this. Ground every claim, score confidence,
  abstain below the board threshold, coordinate via the mailbox.
members:
  - confidence-gate
  - warroom
---

# War-room pre-brief

(prose briefing — the gate contract in one paragraph, the mailbox verbs in one
paragraph, "run /warroom to load the full protocol bodies".)
```

**The bundle loader** (`template/skill-bundles/<pack>.yaml`) — unchanged shape
(this is the existing `warroom.yaml`):

```yaml
name: warroom
description: Agentic war-room coordination bundle.
skills:
  - warroom
  - confidence-gate
instruction: |
  War-room protocol. Follow confidence-gate before posting any claim.
```

**Persona-sync wiring** (`template/manifest.json`) — add a `prebrief` section to
BOTH outputs (`claude_head`, `hermes_soul`), sourced from the pack doc, exactly
like the existing `org.md` section:

```jsonc
{ "title": "War-room pre-brief",
  "source": "shared/prebrief/warroom.md",
  "local_override": "local/prebrief/warroom.md" }   // NEW field; falls back to source
```

> **Open Decision (D-4) — does persona-sync gain a `local_override` field, or do we
> reuse the existing source-resolution?** **Recommendation: add an explicit
> `local_override` key** so the pin (V-1) is declarative in the manifest rather
> than a special-cased path rule in `setup.py`. It generalizes: `org.md` could get
> the same treatment later.

**Distribution manifest** (`template/distribution.yaml`) — make pack ownership
explicit:

```yaml
distribution_owned:
  - SOUL.md
  - config.yaml
  - skills
  - skill-bundles      # NEW — was carried by catch-all copy; now declared
  - shared             # NEW — carries the pack doc + org.md
  - cron
  - distribution.yaml
# version bump on any pack change (drives `hermes profile info` drift display)
```

`config.yaml` is unchanged for v1 (no new keys). `<profile>/.env` is unchanged.
`local/prebrief/<pack>.md` is the only new *user-owned* path, and it is created by
the operator (or `warroom prebrief pin`), never by the distribution.

## Reliability — failure modes

- **Bundle references a missing skill.** Hermes loads the bundle anyway and notes
  the skipped skill (`build_bundle_invocation_message` → `missing` list,
  `agent/skill_bundles.py:294-296`). `warroom prebrief verify` catches it
  pre-flight; the existing `test_warroom_bundle.py` catches it at test time.
- **Pack doc missing / malformed frontmatter.** Persona-sync degrades: if
  `shared/prebrief/<pack>.md` is absent, the "Pre-brief" section is simply omitted
  (same graceful behavior as `org.md` "delete the body if not needed"). SOUL stays
  valid; the agent still has the Layer 2 plugin enforcing the gate structurally.
- **`profile update` clobbers a customized skill.** `skills/` is
  distribution-owned → replaced on update. An operator who hand-edited
  `skills/warroom/SKILL.md` *in the profile* loses it. Mitigation: edits belong in
  `local/`; document that profile-level skill edits are transient. (`config.yaml`
  is the *preserved* exception, by design.)
- **Catch-all copy assumption breaks (Hermes tightens to `owned_paths()`).**
  Declaring `skill-bundles` + `shared` in `distribution_owned` (this spec)
  pre-empts it. Flagged in VERIFY-AGAINST-HERMES.
- **Bundles silently stop auto-… they never auto-loaded.** The whole design avoids
  the trap of *assuming* bundles auto-load; the guarantee rests on SOUL injection,
  which we control.
- **Pin drift.** A pinned `local/prebrief/<pack>.md` can fall behind a security-
  relevant gate update. `warroom prebrief show` reports both the pinned version
  and the available `shared/` version so the operator sees the gap.
- **Hub-skill update fails the security scan.** `skills_guard` blocks install; the
  old skill stays. Surfaced by `hermes skills update` output. No partial state.
- **Slug collision.** A bundle and a skill sharing a slug → the bundle wins
  (`agent/skill_bundles.py:26-31`). Don't name a member skill `warroom` *and* a
  bundle `warroom`… the repo already does exactly this (`skills/warroom` +
  `skill-bundles/warroom.yaml`); verified behavior is bundle-wins, so `/warroom`
  loads the bundle. Document so a future author doesn't "fix" it.

## Security

Skill/knowledge content is **instruction the agent treats as authoritative** —
effectively executable in the sense that it steers tool use. Propagating it is a
supply-chain surface.

- **First-party packs only in the distribution.** The pack shipped in `template/`
  is authored in-repo, reviewed in PR, and sanitization-gated
  (`template/scripts/sanitize_check.py`, the employer-leak grep). No third-party
  skill enters the distribution without code review.
- **Tap propagation is untrusted-by-default.** `hermes skills tap add <repo>` does
  NOT grant trust. Hub installs are scanned by `tools/skills_guard.py` against a
  `TRUSTED_REPOS` allowlist before landing (`tools/skills_hub.py`); a war-room
  operator should treat any non-allowlisted tap as untrusted and read the skill
  before install. We document: **never add a tap you don't control or trust.**
- **No auto-tap, no auto-trust.** The shipped `taps.json` stays empty
  (`{"taps": []}`). The pack never adds a tap on the operator's behalf; the
  official hub is built-in (`DEFAULT_TAPS`) and curated by the runtime, not by us.
- **The pin is a security control too.** `local/prebrief/<pack>.md` lets an
  operator freeze the *briefing* against an upstream change they haven't reviewed —
  useful when a pack update is pending audit.
- **Prompt-injection via the pack doc.** The pack doc is injected into SOUL; a
  malicious edit could try to override the gate ("ignore confidence rules"). Two
  defenses: (1) the doc is distribution-owned + PR-reviewed; (2) the Layer 2
  *structural* gate plugin enforces abstention regardless of persona text, so a
  prose override of the *behavioral* contract cannot disable the *structural* one.
- **Audit.** Pack version is recorded in SOUL and reported by `warroom prebrief
  show`; hub-skill provenance is in `lock.json`. No secrets in any pack file
  (sanitization-gated).

## Observability

- `warroom prebrief show` — current pack, version, member install status, pin
  state (and the available-vs-pinned version gap).
- `warroom prebrief verify` — pass/fail on pack integrity (members resolve, bundle
  consistent, doc version present); CI-runnable.
- **Agent self-report:** because `pack_version` is injected into SOUL, an agent
  can answer "which pre-brief are you on?" in-session — a cheap fleet-consistency
  probe over the mailbox.
- `hermes profile info` shows `distribution_version` drift (whole-pack channel);
  `hermes skills` / `lock.json` shows per-skill provenance (hub channel).
- The opt-in `warroom prebrief announce` leaves a dated board message — an audit
  trail of "fleet notified of pack v<x>".

## Test strategy

**`template/tests` (existing harness, stdlib + pytest):**
- *Pack integrity:* extend `test_warroom_bundle.py` — every `members:` in the pack
  doc resolves to a `skills/<m>/SKILL.md` AND appears in the bundle's `skills:`;
  the bundle's skills ⊆ pack members (no orphan in either direction).
- *Pack doc:* `shared/prebrief/<pack>.md` parses, has `pack`, `pack_version`,
  `members`, `summary` frontmatter; `pack_version` is semver.
- *Persona-sync injection:* running the sync produces a SOUL.md (and head agent
  file) containing the "War-room pre-brief" section with the pack summary + the
  condensed gate contract + the `/warroom` pointer; missing pack doc → section
  omitted, SOUL still valid (mirror existing `org.md` optional behavior).
- *Pin override:* `local/prebrief/<pack>.md` present → its body is injected
  instead of `shared/`'s; `warroom prebrief pin`/`--unpin` create/remove it
  atomically (temp + `os.replace`, per the atomic-write convention).
- *Manifest ownership:* `distribution.yaml::distribution_owned` includes
  `skill-bundles` and `shared` (the contract-correctness fix).
- *Verify CLI:* `warroom prebrief verify` exits non-zero on a broken pack
  (missing member, missing doc) and zero on a healthy one; exit-code matrix like
  the existing assimilate tests.
- *Sanitization:* extend `scripts/sanitize_check.py` scope to
  `shared/prebrief/**` so no employer string leaks via the pack doc.

**Integration (real Hermes, gated like the existing `--runintegration` smoke):**
- Build the distribution, `hermes profile install` it, assert
  `<profile>/skill-bundles/<pack>.yaml`, `<profile>/skills/<members>/SKILL.md`, and
  `<profile>/shared/prebrief/<pack>.md` all land.
- `hermes -p <name> bundles list` shows `/<pack>`; invoking it loads the member
  bodies (proves the loader path).
- Bump `pack_version`, `hermes profile update <name>`, assert the pack doc + bundle
  + skills are replaced while `config.yaml` and `local/` are preserved (the
  pull-on-update propagation proof).
- Place a `local/prebrief/<pack>.md`, run update, assert it survives (pin proof).
- (Stash `template/.venv` before any real `hermes profile install` — handoff §0.)

## File-path map (complete — every file created/modified)

**`template/` (the pack):**
- `template/shared/prebrief/warroom.md` — **NEW.** The v1 pre-brief pack doc
  (briefing + version anchor; members: confidence-gate, warroom).
- `template/skill-bundles/warroom.yaml` — **modified** (optional). Stays the
  loader; may grow `instruction` to reference the pre-brief. Possibly add future
  pack members here as they ship.
- `template/skills/confidence-gate/SKILL.md` — **unchanged** (member; referenced).
- `template/skills/warroom/SKILL.md` — **unchanged** (member; referenced).
- `template/manifest.json` — **modified.** Add a "War-room pre-brief" section to
  both `claude_head` and `hermes_soul` outputs, sourced from
  `shared/prebrief/warroom.md` with a `local_override` of
  `local/prebrief/warroom.md`.
- `template/distribution.yaml` — **modified.** Add `skill-bundles` + `shared` to
  `distribution_owned`; bump `version`.
- `template/skills/.hub/taps.json` — **unchanged** (stays `{"taps": []}`; security
  posture).
- `template/skills/.bundled_manifest` — **unchanged** (stays empty).
- `template/SOUL.md` — **regenerated** by sync (not hand-edited); the skeleton
  gains the pre-brief section after `warroom setup --sync`.

**`template/warroom_setup/` (producer/sync; stdlib-only):**
- `template/warroom_setup/prebrief.py` — **NEW.** `show`/`verify`/`sync`/`pin`/
  `announce` logic; pack-doc parse; member-resolution check; atomic pin write
  (`os.replace`).
- `template/warroom_setup/__main__.py` (or wherever the `warroom` subcommand
  dispatch lives) — **modified.** Register the `prebrief` subcommand group.
- `template/warroom_setup/setup.py` — **modified** (small). Persona-sync honors the
  new `local_override` manifest field; the pre-brief section render reuses the
  existing section machinery. (No new `config.yaml` block → no `patch_*_block`
  change; Option B sentinel logic untouched.)
- `template/warroom_setup/schema.py` — **unchanged** for v1 (no new config keys).
  (Touch only if V-1 ever moves to config-based per-skill pins.)

**`template/tests/` (extend existing):**
- `template/tests/test_warroom_bundle.py` — **modified.** Pack ↔ bundle ↔ skills
  consistency; pack-doc frontmatter checks.
- `template/tests/test_prebrief.py` — **NEW.** Pack-doc parse, persona-sync
  injection (present + omitted cases), pin override + survive-update, `verify`
  exit-code matrix.
- `template/tests/test_template_content.py` — **modified.** Assert
  `distribution.yaml` lists `skill-bundles` + `shared` as owned.
- `template/tests/test_persona_sync.py` — **modified.** Pre-brief section appears
  in generated SOUL + head agent; `local_override` precedence.

**`template/scripts/`:**
- `template/scripts/sanitize_check.py` — **modified.** Extend scan scope to
  `shared/prebrief/**` (and document in `template/SANITIZATION.md`).
- `template/SANITIZATION.md` — **modified.** Note the new scanned path.

**`template/docs/` + repo docs:**
- `template/README.md` — **modified.** "Pre-brief pack" subsection: what it is, the
  `/warroom` expansion, propagation via `hermes profile update` vs `skills tap`,
  pinning via `local/prebrief/`.
- `docs/superpowers/specs/2026-06-09-awr-skill-prebrief-packs-design.md` — **this
  file.**
- `docs/superpowers/plans/2026-XX-XX-awr-skill-prebrief-packs.md` — **NEW** (the
  build plan, authored before implementation per AWR's plan-first discipline).

> **Open Decision (D-5) — first-party hub repo for `skills tap` propagation.** The
> hub channel (§4) needs a *real GitHub repo* to tap. **Recommendation: defer the
> repo to a later phase; ship the distribution-update channel first.** When built,
> it is a *separate* public repo of individual war-room skills (generic-named, no
> employer strings), referenced by `hermes skills tap add <owner>/<repo>` — NOT a
> dir inside this distribution. Listed here so the file-map is complete: no file in
> *this* repo is created for it in Phase 1.

## Build order (phasing — NOT omission; everything above is in scope)

1. **Phase 1 — pack format + manifest correctness.** Create
   `shared/prebrief/warroom.md`; add `skill-bundles` + `shared` to
   `distribution_owned`; bump `version`; pack-integrity tests
   (`test_warroom_bundle.py`, `test_template_content.py`); sanitize-scope
   extension. This alone makes the pack a *real, versioned, propagating* artifact
   (it already rides `hermes profile update`).
2. **Phase 2 — startup load via persona-sync.** Add the `prebrief` section to
   `manifest.json` (both outputs); wire the render in `setup.py`; persona-sync
   tests. Now every freshly-synced agent briefs against the pack on turn 1.
3. **Phase 3 — operator surface + versioning/pinning.** `warroom_setup/prebrief.py`
   (`show`/`verify`/`sync`/`pin`); `local_override` manifest field + precedence;
   `local/prebrief/` pin; `test_prebrief.py`. Operators can inspect, verify, and
   freeze.
4. **Phase 4 — hub-tap propagation + fleet nudge.** Stand up the first-party hub
   repo (D-5); document `skills tap`/`skills update` for foreign/assimilated
   profiles; implement the opt-in `warroom prebrief announce` mailbox nudge (P-2).

Each phase is independently shippable and leaves the suite green (the existing
409/419 baseline must not regress).

## Out of scope (this spec)

- **A new propagation transport.** We deliberately reuse `profile update` +
  `skills tap`; no bespoke daemon, no settings.json hook (locked decision #9).
- **True push to running sessions.** Out of scope — would require a Hermes-side
  hook we won't add. The mailbox *nudge* (P-2) is a soft signal, not a push of
  content.
- **Making `/warroom` a real orchestrator.** The L1 orchestrator spec
  (`2026-06-09-awr-l1-orchestrator-design.md`) owns the *content* of the pack's
  orchestration skill; this spec owns the *packaging + propagation* of whatever
  skills the pack contains.
- **Per-skill version pinning in `config.yaml`** (V-1 option b) — deferred; the
  `local/prebrief/` whole-pack pin covers v1.
- **DEFCON/severity and multi-board skills** — when those land they become
  *members* of the pack, but their content is specified in their own specs.
- **Auto-trusting taps / curating a public skill registry** — security posture is
  "first-party + scanned + operator-reviewed"; running a registry is a separate
  effort.

## Open questions

1. **Bundle slug vs pack name.** v1 reuses `warroom` for the bundle slug, the pack
   name, and a member skill. Confirm we keep the bundle-wins collision (verified
   behavior) rather than renaming for clarity. (Recommend keep — renaming churns
   the `/warroom` UX users may already rely on.)
2. **Should the condensed gate contract live in the pack doc or be templated from
   the gate SKILL.md?** Single-source-of-truth argues for deriving the SOUL
   summary from `confidence-gate/SKILL.md`; simplicity argues for authoring it in
   the pack doc. (Recommend: author the *summary* in the pack doc, but keep it
   short enough that drift from the SKILL.md is obvious in review.)
3. **`hermes profile update` UX for the fleet.** Is the expected operator workflow
   a manual per-profile `update`, or a scripted loop / cron over all war-room
   profiles? (Recommend a documented `for p in $(...); do hermes profile update
   $p; done` recipe in README; a cron is the operator's call.)
4. **Does the head-agent file (`~/.claude/agents/<name>.md`) reliably reload
   per-session like SOUL.md?** Persona-sync writes it, but confirm Claude Code
   re-reads it each session so the pre-brief section is actually present turn-1 on
   the Claude side (SOUL is confirmed; the head file should be VERIFIED).
