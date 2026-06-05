# War-Room Confidence Gate (Layer 2 — structural enforcement) — Design

- **Date:** 2026-06-05
- **Sub-project of:** Agentic War Room (AWR). Sibling of the war-room agent
  template (`2026-06-04-war-room-agent-template-design.md`), which ships **Layer 1**
  (the behavioral protocol). This spec is **Layer 2** — the airtight enforcement.
- **Depends on:** L1 (Hermes integration / a live war-room board) for the channel
  context; the template's Layer 1 protocol skill + `war_room.*` config keys.
- **Status:** design, pre-implementation.

## Problem

A war room must not contain hallucinated answers — "it's a war room, not a chat
room." Layer 1 asks the agent (via persona + the `confidence-gate` skill) to
ground its claims, score confidence from that grounding, and abstain below a
threshold. But Layer 1 is **advisory**: a model can ignore it. Layer 2 makes the
gate **structural and fail-closed** — a message that does not demonstrably clear
the bar never reaches the channel.

## Core decisions (carried from brainstorming)

- **Signal = grounding + verifier**, never a free-floating self-asserted number.
  Confidence is only honored when accompanied by evidence kinds; an optional
  independent verifier pass is used for high-severity boards.
- **Below-threshold action = abstain + state the gap.** The claim is suppressed
  and replaced with a short "not confident enough; here's what's missing" notice.
- **Fail closed.** Absence of a valid confidence envelope on a claim-bearing
  message is treated as confidence 0 → abstain. This is what forces the agent to
  ground its claims to be heard at all.

## Where it hooks in (verified)

Hermes exposes `pre_gateway_dispatch` in `VALID_HOOKS`
(`hermes_cli/plugins.py:127-167`) — a runtime hook that fires on an outbound
gateway message before it is sent to the channel. That is the single chokepoint
for every Discord/Slack message the agent emits, and therefore the enforcement
point. The hook is declared in the profile `config.yaml` `hooks:` block
(`agent/shell_hooks.py`) and requires hook consent (`hooks_auto_accept: true` or
`--accept-hooks`) — see Security.

```
agent produces outbound message
        │
        ▼
pre_gateway_dispatch hook (this sub-project)
        │  parse canonical envelope → classify claim vs chatter → gate
        ├─ chatter / non-claim ............................ pass through unchanged
        ├─ claim, envelope valid, conf ≥ threshold, grounded → strip envelope, pass (optional badge)
        ├─ claim, conf < threshold OR ungrounded OR no envelope → SUPPRESS, replace with abstention
        └─ high-severity board → run independent verifier before passing
        │
        ▼
message (or abstention) delivered to channel ; gate decision logged
```

## Architecture & components

A small stdlib package `warroom_gate/` shipped by the template distribution
(under the profile, like `warroom_setup/`) and wired via `config.yaml` `hooks:`.
Pure core + a thin hook adapter, mirroring the template's layering discipline.

| Module | Responsibility | Pure? |
|---|---|---|
| `envelope.py` | parse/strip the canonical envelope `⟦conf=… grounded=… missing=…⟧`; reject lookalikes | pure |
| `classify.py` | claim-bearing vs chatter heuristic | pure |
| `policy.py` | gate decision from (envelope, threshold, severity) → `pass` / `abstain` / `verify` | pure |
| `verifier.py` | optional independent support-check pass (high-severity only) | effectful (LLM) |
| `render.py` | build the abstention message + optional confidence badge | pure |
| `audit.py` | append-only gate-decision log (no secrets) | IO |
| `hook.py` | `pre_gateway_dispatch` adapter: read config, orchestrate, return transformed/suppressed message | effectful edge |

Import direction points downward to the pure leaves; `hook.py` is the only place
effects compose. Same invariants as the template (pure core unit-tested without
the gateway; structural test forbids cycles).

## The confidence envelope (grammar + trust)

Canonical, agent-controlled, machine-readable footer the protocol skill instructs
the agent to append to claim-bearing messages:

```
⟦conf=0.82 grounded=tool,file missing=none⟧
```

- `conf` ∈ [0,1] (float). `grounded` = comma list from a closed vocabulary
  {`tool`,`file`,`source`,`citation`,`memory`,`none`}. `missing` = free-ish short
  text (what would raise confidence) or `none`.
- **Grammar:** matched by a strict regex anchored to the `⟦…⟧` sentinels; only the
  **last** envelope on the **final line** is honored. Malformed → treated as
  absent (fail closed).
- **Anti-spoof (untrusted input):** a channel user can paste a fake
  `⟦conf=0.99⟧` into text the agent quotes. The hook honors an envelope only in
  the canonical trailing position the *agent* controls; any envelope-looking
  substring elsewhere (e.g., inside a quote block, mid-message) is ignored and
  stripped from display. The agent never copies a user-supplied envelope into the
  trailing slot (Layer 1 rule), and the hook's "last line only" rule enforces it
  structurally.
- The envelope is **always stripped** from the user-visible message; optionally a
  clean badge (`✓ 82%` / `⚠ unverified`) is rendered in its place
  (config `war_room.show_confidence_badge`).

## Gate policy (decision table)

Inputs: `kind` (claim|chatter), `env` (valid|missing|malformed), `conf`,
`grounded`, `threshold = war_room.min_confidence/100`, `severity`.

| kind | envelope | conf vs threshold | grounded | severity | decision |
|---|---|---|---|---|---|
| chatter | any | — | — | any | **pass** (strip stray envelope) |
| claim | valid | ≥ threshold | non-empty | normal | **pass** (+ optional badge) |
| claim | valid | ≥ threshold | empty/`none` | any | **abstain** (grounded≠∅ required for a factual claim) |
| claim | valid | < threshold | any | any | **abstain** (state `missing`) |
| claim | missing/malformed | — | — | any | **abstain** (fail closed) |
| claim | valid | ≥ threshold | non-empty | **alert 1–2** | **verify** → pass only if verifier confirms, else abstain |

`severity` is read from the board state (idea #5; until that lands, `severity`
defaults to "normal" and the `verify` branch is inert).

## Abstention output

Generated from the envelope's `missing` field when present, else generic:

```
🛑 Holding back — not confident enough to post that (62% < 75% bar).
   To clear it I'd need: <missing>.
```

Posting the abstention (rather than silently dropping) is deliberate: the room
sees that a question was reached-for-but-not-answered, and what would unblock it.

## Data model & config (extends Layer 1's managed block)

```yaml
# >>> warroom-managed (set via `warroom setup`) >>>
war_room:
  enabled: true
  board: <name>
  role: contributor
  min_confidence: 75          # Layer 1
  gate_action: abstain        # Layer 1
  enforce: true               # Layer 2: turn the hook on
  show_confidence_badge: true # Layer 2: render ✓/⚠ badge in place of the envelope
  verify_at_severity: 2       # Layer 2: run independent verifier at/above this alert level
# <<< warroom-managed <<<
hooks:
  pre_gateway_dispatch: python3 -m warroom_gate.hook
hooks_auto_accept: true       # required for unattended enforcement; see Security
```

## Efficiency

- **Normal path is pure + O(message length):** one regex match + a classification
  heuristic + a table lookup. No network, no LLM call. Negligible per-message cost.
- **Verifier pass is gated to high severity only** (`verify_at_severity`), so the
  expensive path is rare and bounded; it reuses the session's evidence context
  rather than re-fetching.
- Hook is stateless except the append-only audit log (buffered).

## Reliability — failure modes (fail-closed where it matters)

| Failure | Behavior | Posture |
|---|---|---|
| Hook crashes / raises | Hermes hook contract: a failing `pre_gateway_dispatch` must not silently pass an ungated claim. Wrap in try/except → **abstain** on internal error for claim messages; pass chatter. | fail-closed |
| Envelope malformed | treated as absent → abstain | fail-closed |
| Verifier unavailable/timeout at high severity | abstain (do not downgrade to self-score) | fail-closed |
| `war_room.enforce: false` | hook no-ops (Layer 1 protocol still applies) | opt-in |
| Config unreadable | abstain on claims + log error (do not fail open) | fail-closed |

**Open design question (flagged):** Hermes' exact `pre_gateway_dispatch` contract
— whether a hook can *replace* an outbound message (needed for abstention) vs only
*block* it — must be confirmed against `agent/shell_hooks.py` /
`transform_*` semantics during planning. If it can only block, the abstention is
posted via a separate `hermes send` call instead of an in-place transform.

## Security

- **Anti-spoof** (above): only the agent-controlled trailing envelope is trusted;
  user-injected lookalikes are ignored + stripped. The gate treats channel content
  as data, never instructions.
- **Hook = code-exec-on-dispatch.** Enabling `hooks_auto_accept` runs the hook
  without prompting. This is opt-in (`enforce: true`) and documented; the hook
  does no network I/O on the normal path and never reads secrets.
- **No secret in logs.** `audit.py` records the gate decision, message kind,
  conf, and a hash/prefix of the message — never tokens, never full secret-bearing
  payloads.
- **Least authority:** the hook only reads `war_room.*` config + the message text;
  it does not touch `.env`, `auth.json`, or `local/`.
- **DoS bound:** regex is anchored and linear (no catastrophic backtracking — a
  test asserts the pattern is safe); message length is already capped upstream by
  `max_attachment_bytes`.

## Observability

- Append-only `local/war_room/gate.log`: `ts kind decision conf board severity
  msg_prefix` — the war room's record of what was withheld and why.
- A `warroom gate --stats` helper summarizes pass/abstain/verify counts (a future
  CLI addition; out of scope for v1 mechanism).

## Test strategy

| Concern | Test | Type |
|---|---|---|
| envelope parse/strip; last-line-only; malformed→absent | `test_envelope.py` | unit (pure) |
| anti-spoof: mid-message / quoted envelope ignored | `test_envelope.py::spoof` | security |
| regex is linear / no catastrophic backtracking | `test_envelope.py::redos` | security |
| claim vs chatter classification | `test_classify.py` | unit |
| full decision table (every row) | `test_policy.py` | unit |
| severity → verify branch routing | `test_policy.py::severity` | unit |
| abstention rendering from `missing` | `test_render.py` | unit |
| hook fail-closed on internal error | `test_hook.py` | integration |
| audit log has no secrets | `test_audit.py` | security |
| e2e: low-conf claim suppressed, chatter passes | manual against a test board | e2e |

## Out of scope (this spec)
- The Layer 1 protocol/skill/config knob (shipped by the template sub-project).
- The DEFCON/severity model itself (idea #5) — this consumes `severity`, does not
  define it.
- Multi-agent coordination of who answers (AWR mailbox lanes) — orthogonal.

## Open questions to resolve in planning
1. `pre_gateway_dispatch` replace-vs-block semantics (above) — the one true
   blocker; confirm against Hermes source before writing `hook.py`.
2. How `severity` is surfaced to the hook before idea #5 exists (default
   "normal"; later read from board state).
3. Whether the verifier reuses the agent's model/provider or a cheaper fixed one
   (cost vs latency on high-severity messages).
