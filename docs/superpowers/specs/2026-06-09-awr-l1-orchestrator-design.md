# L1 Orchestrator — Make `/warroom` Real — Design

- **Date:** 2026-06-09
- **Sub-project of:** Agentic War Room (AWR). Turns the no-op `/warroom` skill
  bundle (`template/skills/warroom/` + `template/skill-bundles/warroom.yaml`) into
  a real **orchestration/triage protocol** the agent reads as instructions.
- **Depends on:** the war-room agent template (Layer 1 behavioral protocol +
  `war_room.*` config keys); the **confidence gate** (`2026-06-05-war-room-confidence-gate-design.md`,
  Layer 1 skill + Layer 2 plugin) — the orchestrator composes ON TOP of it; the
  **multi-board federation** model (`2026-06-09-awr-multi-board-federation-design.md`)
  — the orchestrator routes ACROSS the federation (escalate/broadcast/local); the
  mailbox CLI lane verbs (`claim-lane`/`release-lane`/`list-lanes`, plus `ps`/
  `claims`/`inbox`/`send`) in `coordination/src/mailbox/cli.py`.
- **Referenced by:** `2026-06-09-awr-defcon-severity-design.md` (the severity-
  assessment step consumes that spec's severity model; this spec does NOT define a
  severity model — it cross-references it). The `/swarm` slash command
  (`~/.claude/commands/swarm.md`) is a sibling, not a dependency (see §Open Decision).
- **Status:** design, pre-implementation.

## Problem

Today `template/skills/warroom/SKILL.md` is a **list of mailbox commands with no
protocol**. It tells an agent *how* to run `mailbox ps` / `claim-lane` / `send`,
but never *when*, *in what order*, or *with what discipline*. When an operator (or
a peer agent) drops a problem into the war room and someone says `/warroom`, the
agent gets a cheat-sheet, not a playbook. There is no instruction to:

- **triage** the incoming problem (is this even mine? is it a duplicate?),
- **assess severity** (does this warrant escalation? a higher confidence bar?),
- **choose a board** to route on given the federation (post local vs escalate up
  vs broadcast down),
- **decide who to ping** (a specific peer label vs a board broadcast),
- **claim the right lane** before working (so two agents don't dogpile), and
- **post a first message** that is a *grounded claim-or-question with a confidence
  envelope* — not a bare assertion.

The result is that a "war room" of multiple agents behaves like a chat room: no
intake discipline, no de-duplication, no severity awareness, ungrounded first
posts. **L1 makes `/warroom` an orchestration protocol** — the agent's intake-to-
first-post behavior in the room — without adding a new runtime primitive. It is
markdown the agent *reads as instructions*; the quality bar is "would a smart
agent follow this and do the right thing?"

## Core decisions

1. **`/warroom` is a markdown protocol skill, not code.** The deliverable is a
   rewritten `template/skills/warroom/SKILL.md` (plus an unchanged-shape bundle).
   No slash-command handler, no helper script, no new Hermes hook, no
   `~/.claude/settings.json` edit (locked decision #9). It steers the agent through
   existing mailbox CLI verbs. (See §Open Decision: automated vs prompted.)
2. **It composes on the confidence gate; it does not restate it.** The orchestrator
   *references* the `confidence-gate` skill (already in the same bundle) for the
   ground→score→gate→envelope rules and the envelope grammar. It owns the
   war-room-specific **routing/triage** layer that sits *before* the first post; the
   gate owns the **claim-grounding** layer. One canonical envelope grammar, one
   place. (See §Open Decision: compose vs restate.)
3. **A fixed intake sequence: TRIAGE → SEVERITY → ROUTE → LANE → FIRST POST.** Five
   ordered steps, each with a decision and a default. The agent runs them top-to-
   bottom on every `/warroom` intake. Each step is short, has an explicit "when in
   doubt" default, and ends in an observable mailbox action.
4. **Severity is delegated, not redefined.** The SEVERITY step *cross-references*
   the DEFCON/severity spec (`2026-06-09-awr-defcon-severity-design.md`) and maps a
   severity to two downstream effects: (a) the routing scope at the ROUTE step
   (high severity → escalate up the federation) and (b) the confidence bar the gate
   enforces. The orchestrator does not invent thresholds — it reads
   `war_room.min_confidence` and defers per-severity overrides to the DEFCON spec.
5. **Routing is a triage-time decision over the federation tree.** Using the
   federation model's `local` | `escalate` | `broadcast` scopes
   (`2026-06-09-awr-multi-board-federation-design.md` §2), the agent decides at
   intake whether the first post is local to the home board, escalated to ancestors,
   or broadcast to descendants — driven by severity + audience. The agent still has
   exactly ONE home board (federation is server-side); routing = choosing the
   message **scope**, not joining boards. (See §Open Decision: board selection.)
6. **Lane discipline is mandatory before work.** The agent claims a lane
   (`mailbox claim-lane`) before doing the substantive work, honoring the engine's
   `allow`/`deny`/`warn`(stale) decisions, and uses `seize`/`request-release` only
   per the documented escalation path. This is the dogpile-avoidance contract.
7. **Comprehensive scope, phased build.** This spec covers the full protocol +
   structural tests + bundle wiring + config knobs. Sequencing is in §Build order,
   not by omission.

## Current state (VERIFIED against the repo, 2026-06-09)

### The placeholder `/warroom` skill (`template/skills/warroom/SKILL.md`)

The current file is a flat command list with no protocol. Its body, verbatim:

> ```
> # Skill: War Room
>
> You are part of a war-room board with other agents. Use these commands to coordinate.
>
> ## See who else is here
>     mailbox ps              # active peers on this board
>     mailbox claims --all    # everyone's open file/lane claims
>
> ## Claim a work-lane before starting (prevents dogpiling)
>     mailbox claim-lane <lane-name> --note "<one-line scope>"
> (allow → you have it; deny → someone owns it; warn → stale, ask first.)
>
> ## Broadcast and read
>     mailbox send --to <peer-label> "<message>"
>     mailbox send "<broadcast>"           # to = "*"
>     mailbox inbox                        # read once; clears on read
>
> ## Release when done
>     mailbox release-lane <lane-name>
>     mailbox list-lanes
> ```

It documents the right verbs and even captures the `allow`/`deny`/`warn` lane
semantics — but there is no *intake*, no *severity*, no *routing*, no *grounding-
before-first-post*. The frontmatter `description` (lines 2-4) already promises
coordination behavior the body does not deliver.

The original template design spec
(`docs/superpowers/specs/2026-06-04-war-room-agent-template-design.md:150-151`,
`:207-208`, `:645`) explicitly ships this as a "documented **no-op** `/warroom`
skill bundle (forward-compat). Becomes real when **L1** lands." This sub-project
*is* that L1 step.

### The pattern reference — the confidence-gate skill (`template/skills/confidence-gate/SKILL.md`)

The gate skill is the **shape to mirror**: a numbered behavioral protocol the agent
reads as instructions. Its four steps — (1) GROUND IT, (2) SCORE IT, (3) GATE IT
against `war_room.min_confidence` (default 75%), (4) ENVELOPE — and the canonical
footer `⟦conf=0.82 grounded=tool,file missing=none⟧` (lines 24-26) are the
authority the orchestrator's FIRST POST step *defers to*. Its closing line —
"Higher severity = stricter bar" (lines 30-32) — is the seam the SEVERITY step
plugs into. The orchestrator must **not** re-state this grammar; it links to it.

### The bundle (`template/skill-bundles/warroom.yaml`)

Verbatim, the bundle already ships both skills and an instruction:

> ```yaml
> name: warroom
> description: Agentic war-room coordination bundle.
> skills:
>   - warroom
>   - confidence-gate
> instruction: |
>   War-room protocol. Follow confidence-gate before posting any claim to the channel.
> ```

So `confidence-gate` is **already co-loaded** with `warroom` whenever the bundle
resolves — the orchestrator can reference it by name and rely on it being present.

### Mailbox CLI verbs an agent uses (`coordination/src/mailbox/cli.py:94-233`)

VERIFIED subcommands (the protocol steers only these — no new verbs needed for the
core): `join` (`--board`/`--label`), `claim <globs> --note`, `release <selector>
[--force]`, `claim-lane <lane> [--note]`, `release-lane <lane>`, `list-lanes`,
`seize <path>`, `request-release <path>`, `send <body> [--to <label>] [--kind]`
(default `--to *` = broadcast), `inbox` (read-once, clears on read), `claims
[--mine|--all]`, `ps`, `board`, `whoami`. The lane conflict engine
(`coordination/src/mailbox/engine.py:195-346`) returns `allow` (you hold it),
`deny` (live holder), or `warn` (stale holder — ask first) — these are the
decisions the LANE step instructs the agent to read.

### Federation scopes (`2026-06-09-awr-multi-board-federation-design.md`)

That spec adds `Message.scope ∈ {local, escalate, broadcast}` (default `local`)
and the convenience verbs `escalate "<msg>"` (≡ `send --scope escalate`) and
`broadcast "<msg>"` (≡ `send --scope broadcast`). The agent joins exactly one home
board; routing is choosing a scope. **The orchestrator is the primary consumer of
these scope verbs.** (Note: those verbs ship with the federation sub-project; until
it lands, the orchestrator's ROUTE step degrades to local-only `send` — see
§Reliability.)

### Config (`template/warroom_setup/schema.py`)

`WAR_ROOM_KEYS` = `(enabled, board, label, role, min_confidence, gate_action,
enforce, show_confidence_badge)` with `DEFAULTS` `role: "contributor"`,
`min_confidence: 75`. The orchestrator reads `role` and `min_confidence`; it
introduces at most one optional new key (see §Data model).

## Architecture & components

The deliverable is the rewritten `template/skills/warroom/SKILL.md` — a five-step
intake protocol — plus the bundle instruction and structural tests. The protocol
is what the agent executes when `/warroom` is invoked.

### The intake protocol (the five ordered steps the agent follows)

```
/warroom invoked (operator or peer drops a problem into the room)
        │
        ▼
STEP 0  ORIENT ........ mailbox ps / claims --all / inbox — read the room first
        │
        ▼
STEP 1  TRIAGE ........ is this mine? is it already owned/answered? in/out of scope?
        │                 ├─ duplicate / already owned → reinforce, don't re-claim
        │                 └─ out of scope → say so + suggest the right board, stop
        ▼
STEP 2  SEVERITY ...... classify severity (defer model → DEFCON spec)
        │                 → sets (a) routing scope bias, (b) confidence bar
        ▼
STEP 3  ROUTE ......... choose scope: local | escalate(up) | broadcast(down)
        │                 + audience: broadcast (--to *) vs ping a peer label
        ▼
STEP 4  LANE .......... mailbox claim-lane <lane> --note "<scope>"
        │                 read decision: allow→proceed / deny→defer / warn→ask
        ▼
STEP 5  FIRST POST .... grounded claim-or-question + confidence envelope
                          (delegates ground→score→gate→envelope to confidence-gate)
                          posted at the STEP-3 scope; Layer 2 plugin still enforces
```

#### STEP 0 — ORIENT (read the room before speaking)

Before claiming or posting, the agent runs `mailbox ps` (who is active),
`mailbox claims --all` (open file/lane claims), and `mailbox inbox` (unread
directed messages). This is the cheap, idempotent "look before you leap" that
prevents the most common failure: posting into a problem someone already owns.

#### STEP 1 — TRIAGE (decide whether to engage)

Three triage questions, each with a default:
- **Is it already owned/answered?** If a peer holds a relevant lane (from STEP 0)
  or has posted a grounded answer, the agent **reinforces or defers** — it does not
  re-claim. Default when ambiguous: ping the owner with a clarifying question
  rather than duplicating work.
- **Is it in scope for this agent's `role`?** Reads `war_room.role`
  (`contributor` default). A `contributor` engages broadly; a future `observer`
  role watches without claiming (forward-compat — see §Open questions).
- **Is it in scope for this board?** If the problem clearly belongs to a different
  board/team, the agent says so, suggests the right board, and stops (it does not
  spam the wrong room).

#### STEP 2 — SEVERITY (assess, do not define)

The agent classifies the problem's severity. **This spec does NOT define the
severity model** — it cross-references the DEFCON/severity spec
(`2026-06-09-awr-defcon-severity-design.md`), which owns the levels, the per-
severity `min_confidence` overrides, and any independent-verifier requirement. The
orchestrator maps the assessed severity to two downstream effects:
- **Routing bias (→ STEP 3):** higher severity biases toward `escalate` up the
  federation so ancestors (team/org boards) see it.
- **Confidence bar (→ STEP 5):** higher severity means a stricter bar — the gate
  skill's "higher severity = stricter bar" line. The orchestrator reads
  `war_room.min_confidence`; when the DEFCON spec lands, per-severity overrides are
  applied by *that* spec's mechanism (managed-block rewrite), not here. Until then,
  the single profile-wide threshold applies and severity is advisory text.

#### STEP 3 — ROUTE (choose board scope + audience)

Two choices, expressed via the federation scope verbs:
- **Scope** (over the federation tree): `local` (post to home board only — the
  default), `escalate` (visible to ancestors — for cross-team-relevant or high-
  severity findings), or `broadcast` (visible to descendants — for announcements
  an ancestor agent makes to its subtree). The agent uses `mailbox escalate "…"` /
  `mailbox broadcast "…"` / plain `mailbox send "…"` (= local). The agent never
  joins extra boards (locked: one home board; federation resolves server-side).
- **Audience:** broadcast to everyone on the resolved scope (`--to *`, the default)
  vs ping a specific peer label (`--to <label>`) — e.g. directing a clarifying
  question at the lane holder found in STEP 0. (See §Open Decision: board selection
  — escalate vs post-local at triage time.)

#### STEP 4 — LANE (claim before you work)

Before doing the substantive work, the agent claims a lane scoped to the work it
is about to do:
```
mailbox claim-lane <lane-name> --note "<one-line scope of the work>"
```
and reads the engine decision (`engine.py:281-346`):
- **`allow`** → the agent holds the lane; proceed.
- **`deny`** → a live holder owns it; the agent defers (ping the holder / pick a
  different lane / contribute under the owner).
- **`warn`** (stale holder) → ask the holder before taking over; only then
  `seize`/`request-release` per the documented escalation path. The agent does not
  silently seize a warn.

Lane naming is the work-stream identifier (e.g. `incident-api-latency`), not a
file path — the lane verbs preserve the name verbatim (`cli.py:108-116`).

#### STEP 5 — FIRST POST (grounded claim-or-question + envelope)

The agent's first substantive post is **never a bare assertion**. It is either:
- a **grounded claim**, run through the `confidence-gate` skill's
  ground→score→gate→envelope discipline, ending in the canonical envelope
  `⟦conf=… grounded=… missing=…⟧`; or
- a **clarifying question** (chatter — no envelope, not gated) when the agent does
  not yet have grounding to claim anything.

The post is sent at the STEP-3 scope/audience. The orchestrator **delegates** the
grounding rules entirely to `confidence-gate` (co-loaded via the bundle) — it does
not restate the grammar. Layer 2 (the `warroom-gate` plugin,
`2026-06-05-war-room-confidence-gate-design.md`) still structurally enforces the
envelope on the outbound turn regardless — the protocol's job is to make the agent
*produce a compliant first post*, the plugin's job is to *guarantee* compliance.

### How it composes with the three siblings

- **Layer 1 confidence gate (compose, don't restate):** STEP 5 hands off to the
  `confidence-gate` skill for ground/score/gate/envelope. The bundle already
  co-loads it; the orchestrator references it by name.
- **Layer 2 gate plugin (independent backstop):** the `transform_llm_output`
  plugin still runs on every outbound turn (fail-closed). The protocol does not
  depend on it but is consistent with it — a compliant STEP-5 post passes the
  plugin untouched; a non-compliant one is abstained by the plugin.
- **Federation (route across):** STEP 3 is the consumer of `local`/`escalate`/
  `broadcast`. The orchestrator imports no federation code — it just chooses the
  scope verb. Presence/claims federation (federation spec §4) means STEP 0's
  `ps`/`claims` already see the subtree on a federated board.
- **DEFCON severity (delegate the model):** STEP 2 cross-references it; this spec
  defines only the *mapping* from severity to scope + bar, not the severity scale.

## Data model & config

No new mailbox engine fields. At most **one optional war-room config key**, and the
bundle instruction.

```yaml
# <profile>/config.yaml — war-room managed block (one optional NEW key)
# >>> warroom-managed (set via `warroom setup`) >>>
war_room:
  enabled: true
  board: <name>
  label: <handle>
  role: contributor          # EXISTING — read by STEP 1 (triage scope)
  min_confidence: 75         # EXISTING — read by STEP 5 (the bar)
  gate_action: abstain       # EXISTING
  enforce: true
  show_confidence_badge: true
  orchestrate: true          # NEW (optional, default true): /warroom runs the
                             # full 5-step intake. false => the skill degrades to
                             # the old command cheat-sheet (escape hatch).
# <<< warroom-managed <<<
```

- **`war_room.orchestrate`** (new, optional, default `true`): a single escape-hatch
  knob so an operator can fall back to the bare command list without uninstalling.
  Added to `WAR_ROOM_KEYS`/`DEFAULTS` in `template/warroom_setup/schema.py`.
  Option B's smart-sentinel block rewrite (`setup.py:_replace_sentinel_block`)
  makes adding this key safe (locked decision #10). **Open Decision below
  recommends shipping the key but defaulting it on.**
- **Bundle instruction** (`template/skill-bundles/warroom.yaml`): extend the
  one-line `instruction:` to name the intake order so the bundle's pre-brief itself
  cues the protocol, e.g. "On `/warroom`: triage → severity → route → lane → first
  post; follow confidence-gate before any claim." Skill list unchanged
  (`warroom`, `confidence-gate`).
- **SKILL.md structure** (`template/skills/warroom/SKILL.md`): unchanged
  frontmatter shape (`name`, `description`), body rewritten as the five numbered
  steps above, mirroring the `confidence-gate` skill's numbered-protocol shape. It
  keeps the existing command snippets but folds them into the relevant step. It
  references `confidence-gate` for envelope rules and cross-links the federation +
  DEFCON specs by filename in prose (no employer/operator strings; generic example
  labels `alpha`, `team-platform`, `org`).

## Reliability — failure modes

| Failure | Behavior | Posture |
|---|---|---|
| **No board fits** (problem is out of scope for any board the agent is on) | STEP 1 stops: agent states it's out of scope, suggests the right board/team, posts no claim. Does not spam the wrong room. | safe |
| **Lane already claimed** (`deny`) | STEP 4 defers: ping the holder, pick a different lane, or contribute under the owner. Never silently dogpiles. | safe |
| **Stale lane** (`warn`) | Ask the holder first; only then `seize`/`request-release`. No silent takeover. | safe |
| **Ungrounded** — agent has nothing to ground a claim on | STEP 5 posts a **clarifying question** (chatter, no envelope), not a guess. The gate (Layer 1 + Layer 2) would abstain on an ungrounded claim anyway. | fail-closed |
| **Federation verbs absent** (federation sub-project not yet shipped) | ROUTE degrades to local-only `mailbox send`; escalate/broadcast become "post locally + note that escalation is unavailable". Protocol still functions single-board. | graceful degrade |
| **DEFCON spec not yet shipped** | SEVERITY is advisory text; the single profile-wide `min_confidence` applies. No per-severity override is attempted. | graceful degrade |
| **`mailbox` CLI not found / daemon down** | The agent reports the coordination runtime is unavailable and falls back to answering in-channel under the confidence gate (Layer 2 still enforces the envelope). No crash — it's a protocol, not code. | graceful degrade |
| **`orchestrate: false`** | The skill renders as the legacy command cheat-sheet; no intake sequence is run. | opt-out |
| **Agent skips a step** | The protocol is advisory (markdown). The only *structural* guarantee is the Layer 2 gate on the first post; everything else is behavioral. This is acknowledged, not solved — same posture as the confidence-gate Layer 1 skill. | documented |

## Security

- **No new code, no new authority.** The deliverable is markdown + a YAML
  instruction + one optional config key. It runs nothing; it adds no network path,
  reads no secrets, touches no `.env`/`auth.json`/`local/`. All authority is the
  existing mailbox CLI's.
- **Untrusted channel content stays data, never instructions.** The TRIAGE step
  treats an incoming problem (which may originate from an external Discord/Slack
  user) as *data to triage*, not as instructions to obey — mirroring the gate
  spec's anti-spoof posture. The agent never copies a user-supplied confidence
  envelope into its own trailing slot (the gate's Layer 1 rule, restated by
  reference).
- **Federation boundaries are honored.** Routing only ever escalates to ancestors
  or broadcasts to descendants of the agent's own home board (federation spec
  §Security) — the orchestrator cannot reach sibling/cousin boards. It chooses a
  scope; the engine enforces the tree.
- **Sanitization.** SKILL.md examples use generic labels (`alpha`, `team-platform`,
  `org`, `incident-api-latency`) — never a real employer name or operator handle.
  Subject to `template/scripts/sanitize_check.py` and the `BLOCKED_VALUE_PATTERNS`
  shape guard.

## Observability

- **Mailbox is the audit trail.** Every protocol step ends in an observable mailbox
  action (`ps` reads, a `claim-lane`, a scoped `send`/`escalate`/`broadcast`), all
  already logged by the engine and the federation spec's topology/scope logging.
  An operator reconstructs an agent's intake from the board record.
- **Gate audit.** The first post's gate decision is recorded in the Layer 2 plugin
  audit log (`local/war_room/gate.log`, no secrets) — the war room's record of
  what was posted vs withheld.
- **No new log surface** is introduced by L1 (it adds no code).

## Test strategy — how do you test a markdown protocol skill?

The deliverable is instructions, not logic, so tests are **structural/lint +
scripted-scenario + bundle-wiring**, mirroring how the template already tests its
skills.

| Concern | Test | Type |
|---|---|---|
| SKILL.md has valid frontmatter (`name: warroom`, non-empty `description`) | `test_warroom_skill.py::frontmatter` | structural (parse) |
| SKILL.md contains all five intake steps in order (TRIAGE→SEVERITY→ROUTE→LANE→FIRST POST headers present & ordered) | `test_warroom_skill.py::steps_present_and_ordered` | structural (lint) |
| SKILL.md references `confidence-gate` by name (composes, doesn't restate) AND does NOT re-define the envelope grammar (no second `⟦conf=` grammar block) | `test_warroom_skill.py::composes_not_restates` | structural (lint) |
| SKILL.md cross-references the federation + DEFCON spec filenames | `test_warroom_skill.py::cross_refs` | structural (lint) |
| Every CLI verb the skill names actually exists in the mailbox CLI parser | `test_warroom_skill.py::verbs_exist` | structural (import `cli.build_parser`, assert each named verb is a registered subcommand) |
| No employer/operator strings; passes the shape blocklist | `test_warroom_skill.py::sanitized` (reuse `BLOCKED_VALUES_REGEX`) + `sanitize_check.py` | security |
| `/warroom` bundle resolves to real skills (`warroom`, `confidence-gate` both exist) and the instruction names the intake order | `test_warroom_bundle.py` (extends the existing bundle test) | unit |
| `orchestrate` key round-trips through the managed block (write→read→default) | `test_schema.py` / `test_setup.py` extension | unit |
| **Scripted scenarios** (the "would a smart agent do the right thing?" bar): a small set of golden intake transcripts as fixtures — `duplicate-already-owned`, `out-of-scope-board`, `high-severity-escalate`, `ungrounded→question`, `lane-deny→defer` — asserting the *expected decision path* (which step stops, which scope/verb is chosen) as a documented checklist a reviewer/LLM-judge runs. Captured as a markdown fixture set under the test dir; not auto-graded in CI v1 (see §Open questions). | `tests/fixtures/warroom_scenarios/` | scenario (manual / LLM-judge) |

All structural tests are stdlib-only (`pathlib`, a tiny frontmatter split, an
import of `mailbox.cli.build_parser`) — no new deps, consistent with the template's
stdlib-only rule.

## File-path map (complete)

**`template/` (the deliverable):**
- `template/skills/warroom/SKILL.md` — **rewritten** from the no-op command list to
  the five-step intake protocol (the core deliverable).
- `template/skill-bundles/warroom.yaml` — `instruction:` extended to name the
  intake order; skill list unchanged.
- `template/warroom_setup/schema.py` — add optional `orchestrate` to
  `WAR_ROOM_KEYS` + `DEFAULTS` (default `true`).
- `template/warroom_setup/setup.py` — `patch_war_room_block` carries the new
  `orchestrate` kwarg (Option B sentinel rewrite is key-additive-safe).
- `template/warroom_setup/selectables.py` — optional `orchestrate` toggle field
  (`enable_if="warroom.enroll"`), if the wizard should expose it; else default-only.
- `template/skills/confidence-gate/SKILL.md` — **unchanged** (it is the referenced
  authority; do not duplicate its rules into warroom).

**`template/tests/` (structural + scenario):**
- `template/tests/test_warroom_skill.py` — **new**: frontmatter, step-order lint,
  composes-not-restates, cross-refs, verbs-exist, sanitized.
- `template/tests/test_warroom_bundle.py` — extend (or new) bundle-resolution test.
- `template/tests/test_schema.py` / `test_setup.py` — extend for `orchestrate`.
- `template/tests/fixtures/warroom_scenarios/` — **new**: golden intake transcripts.

**Docs / cross-refs (no edits required, referenced):**
- `docs/superpowers/specs/2026-06-05-war-room-confidence-gate-design.md` — Layer 1/2
  authority the protocol composes on.
- `docs/superpowers/specs/2026-06-09-awr-multi-board-federation-design.md` — the
  scope verbs STEP 3 consumes.
- `docs/superpowers/specs/2026-06-09-awr-defcon-severity-design.md` — the severity
  model STEP 2 defers to (sibling spec; may not exist yet).
- `docs/superpowers/plans/2026-XX-XX-awr-l1-orchestrator.md` — the implementation
  plan (future; not written by this spec).

**Read-only (consumed, never modified):**
- `coordination/src/mailbox/cli.py` — verb surface the protocol names + the
  structural `verbs_exist` test imports.
- `coordination/src/mailbox/engine.py` — lane `allow`/`deny`/`warn` semantics the
  LANE step documents.
- `~/.claude/commands/swarm.md` — sibling slash command (see §Open Decision).
- `~/.claude/settings.json` — **never touched** (locked decision #9).

## Build order (phasing — NOT omission; everything above is in scope)

1. **Phase 1 — the protocol skill (ships standalone, local-only).** Rewrite
   `SKILL.md` to the five steps; ROUTE degrades to local `send` (no federation
   dependency); SEVERITY is advisory text (no DEFCON dependency); STEP 5 references
   `confidence-gate`. Extend the bundle instruction. Add `test_warroom_skill.py`
   structural/lint tests + extend the bundle test. **This alone makes `/warroom`
   real** and is independently shippable.
2. **Phase 2 — config knob + wizard.** Add `orchestrate` to schema/setup
   (+ optional selectable). Extend `test_schema`/`test_setup`.
3. **Phase 3 — federation routing wired.** Once the federation sub-project ships
   the `escalate`/`broadcast` verbs, upgrade STEP 3 from local-only to full
   scope selection; add the `verbs_exist` assertions for the new verbs.
4. **Phase 4 — severity mapping wired.** Once the DEFCON spec ships, upgrade STEP 2
   from advisory text to a real severity→scope/bar mapping; add the per-severity
   threshold read.
5. **Phase 5 — scenario harness.** Formalize the golden intake transcripts as an
   LLM-judge / reviewer checklist (see §Open questions).

Each phase leaves the suite green and the skill usable.

## Out of scope (this spec)

- **The severity model itself** — owned by `2026-06-09-awr-defcon-severity-design.md`;
  this spec consumes it.
- **The federation engine** (topology, scope verbs, federated reads) — owned by
  `2026-06-09-awr-multi-board-federation-design.md`; this spec consumes its verbs.
- **The confidence-gate grammar / plugin** — owned by
  `2026-06-05-war-room-confidence-gate-design.md`; this spec composes on it.
- **Multi-lead fan-out / spawning agents** — that is `/swarm`
  (`~/.claude/commands/swarm.md`), a separate, machine-specific orchestrator
  (see §Open Decision). `/warroom` is the *in-room intake protocol for one agent
  already on a board*, not a launcher.
- **Any `~/.claude/settings.json` change, slash-command handler, or new Hermes
  hook** — locked decision #9; `/warroom` stays a markdown protocol skill.

## Open Decisions (flagged for the user — not yet brainstormed)

**Open Decision — automated vs prompted (does `/warroom` need code?).**
Recommend: **purely a markdown protocol skill, no code.** The deliverable is
`SKILL.md` + a YAML instruction line + one optional config key. Every action the
protocol prescribes uses an existing mailbox CLI verb the agent already invokes.
Adding a slash-command handler or helper would mean a Claude-Code-side command file
(implying a `~/.claude` edit — violates locked decision #9) or a Hermes hook (the
plugin slot is already taken by Layer 2). The only "code" is the **structural lint
tests** that keep the markdown honest. Keep it prompt-only; let the Layer 2 plugin
remain the single structural enforcement point.

**Open Decision — relationship to `/swarm`.**
Recommend: **stay separate and complementary; do not invoke `/swarm` from
`/warroom`.** `/swarm` (`~/.claude/commands/swarm.md`) *launches* N fresh Claude
leads in iTerm2 tabs and is machine/iTerm2-specific and refuses nesting
(`if SWARM_LEAD is set … refuse`). `/warroom` is the *in-room intake protocol for
an agent already on a board*. They operate at different layers: `/swarm` is fan-out
(spawn), `/warroom` is triage (route an existing agent's first move). A swarm lead
could *follow* `/warroom`'s protocol once on a board, but `/warroom` should never
spawn a swarm — that would couple a portable, public template to a private,
iTerm2-only command. Cross-reference `/swarm` in prose as "the launcher"; keep the
code paths disjoint.

**Open Decision — compose on confidence-gate vs restate the envelope rules.**
Recommend: **compose (reference by name), do not restate.** The bundle already
co-loads `confidence-gate` with `warroom`, so it is guaranteed present. STEP 5
should say "follow the confidence-gate skill: ground → score → gate → envelope" and
link it — never paste a second copy of the `⟦conf=…⟧` grammar. A duplicated grammar
would drift from the gate plugin's regex and become a second source of truth. A
structural test (`composes_not_restates`) enforces this: assert the skill
*references* `confidence-gate` and does *not* contain a second envelope-grammar
block.

**Open Decision — board selection: escalate vs post-local at triage time.**
Recommend: **default to `local`; escalate only on an explicit severity/audience
trigger.** Given the federation model (one home board, scope chosen per message),
the cheapest correct default is to post `local` to the home board. The agent
escalates *up* only when (a) STEP 2 severity is high, or (b) the finding is
explicitly cross-team-relevant; it broadcasts *down* only when an ancestor agent is
making a subtree-wide announcement. Defaulting to `local` avoids alert-fatigue on
ancestor boards (the federation spec's read-time escalation already makes a `local`
post invisible upward, which is the safe default). The trigger for `escalate` is
the severity→scope mapping in STEP 2/3 — keep it conservative.

## Open questions

1. **Should the scenario harness be CI-gated (LLM-judge) or reviewer-run?**
   Auto-grading "did the agent follow the protocol?" needs an LLM judge per fixture
   — adds cost + flakiness. Recommend: ship the golden transcripts as a documented
   manual/reviewer checklist in v1 (Phase 5); revisit auto-grading only if drift
   becomes a real problem.
2. **`role` vocabulary.** Today `role` defaults to `contributor`. Does the triage
   step need a first-class `observer` (watch, never claim) or `lead` (coordinates,
   may reassign lanes) role, or is `contributor` enough for v1? Recommend:
   `contributor` only in v1; reserve `observer`/`lead` as a forward-compat note.
3. **Does `orchestrate` belong in the wizard, or default-only?** Exposing it as a
   selectable adds a prompt most operators will accept-default. Recommend: ship the
   key (escape hatch) but **do not** add a wizard prompt — keep it config-only,
   default `true`.
4. **Step granularity vs token budget.** A longer protocol is more precise but eats
   the agent's context on every `/warroom`. Recommend: keep each step to ~3-5 lines
   with one explicit default; lean on `confidence-gate` and the cross-referenced
   specs for depth rather than inlining it.
