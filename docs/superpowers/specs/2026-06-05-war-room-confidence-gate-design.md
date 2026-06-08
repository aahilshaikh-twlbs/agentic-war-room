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

## Where it hooks in (VERIFIED against Hermes source — corrected)

> **Correction (research 2026-06-05):** the first draft named
> `pre_gateway_dispatch`. Source proves that hook is **inbound** — it fires on the
> *user's* `MessageEvent` before auth and can `skip`/`rewrite`/`allow` the incoming
> text (`gateway/run.py:7226-7265`). It is **not** the agent's outbound reply.
> Using it would gate the wrong direction. The correct hook is
> **`transform_llm_output`**.

`transform_llm_output` (`agent/conversation_loop.py:4588-4608`) fires **once per
turn after the tool-calling loop completes, before the response is returned/sent**.
Contract (verified):
- **Receives:** `response_text` (the agent's final output), `session_id`, `model`,
  `platform`.
- **Return:** the **first hook to return a non-empty string wins and replaces**
  `final_response`; `None`/empty leaves it unchanged. → the gate can **rewrite to
  the abstention message in place** (resolves the old Q1 — no separate `hermes
  send` needed) and can strip the envelope.

**Mechanism = a Hermes Python PLUGIN, not a `config.yaml` shell hook
(VERIFIED).** A shell hook *cannot* transform LLM output: `shell_hooks._parse_response`
(`agent/shell_hooks.py:496-539`) only translates `pre_tool_call` (block) and
`pre_llm_call` (context) and returns `None` for everything else — so a shell
command's stdout is ignored for `transform_llm_output`. Only an **in-process
plugin callback** registered via `ctx.register_hook("transform_llm_output", fn)`
can return the replacement string (`hermes_cli/plugins.py:935`,
`conversation_loop.py:4592-4606`).

**Packaging + discovery (VERIFIED).** A plugin is a directory with a `plugin.yaml`
manifest **and** an `__init__.py` exposing `register(ctx)`
(`plugins.py:19`, `:1248`). User plugins load from `get_hermes_home()/plugins`
(`plugins.py:1078`), and the gateway runs with `HERMES_HOME=<profile dir>`
(`gateway.py:2378`, `:777-780`). Therefore a plugin shipped **inside the
distribution at `<profile>/plugins/warroom-gate/`** is auto-discovered when the
gateway starts — no global install, no `hooks_auto_accept` consent. It is gated
only by `plugins.enabled: true` in `config.yaml` (which the template sets).

**Two constraints this imposes (load-bearing):**
1. **No `chat_id` / no session-evidence object in the hook payload.** The gate
   therefore operates **profile-wide** (every outbound turn of a dedicated
   war-room agent), keyed only on `war_room.enforce` — it cannot do per-channel
   thresholds, and it cannot independently inspect the session's tool/evidence
   trail. The **only grounding signal available in-hook is the agent's
   envelope**. → an independent verifier pass is **deferred** (see §Verifier).
2. **Hermes is fail-OPEN on hook error:** if the hook raises, the `except` logs
   and leaves `final_response` unchanged (`conversation_loop.py:4607-4608`) — the
   ungated claim would pass. → **our hook must be internally fail-CLOSED:** catch
   all internal errors and **return the abstention string** rather than raising.
   (A test asserts the top-level hook never propagates an exception on a claim.)

```
agent finishes turn → final_response
        │
        ▼
transform_llm_output hook (this sub-project) — returns a string (replace) or None (unchanged)
        │  parse canonical envelope (last line only) → classify claim vs chatter → gate
        ├─ chatter / non-claim ............................ return None (unchanged)
        ├─ claim, envelope valid, conf ≥ threshold, grounded → return text minus envelope (+ optional badge)
        ├─ claim, conf < threshold OR ungrounded OR no/!envelope → return ABSTENTION string
        └─ internal error on a claim ...................... return ABSTENTION string (fail closed)
        │
        ▼
final_response (possibly replaced) is sent to the channel ; gate decision logged
```

**Streaming caveat:** for platforms that stream tokens live, a post-hoc replace
cannot un-send already-streamed text (tests note the transform "modified the
final text after streaming"). Discord/Slack send a buffered final message, so the
replacement is what users see there; the terminal/ACP streaming surfaces are out
of the war-room scope. Documented, not solved.

## Architecture & components

A plugin directory **shipped inside the distribution** at
`plugins/warroom-gate/` (so it lands at `<profile>/plugins/warroom-gate/` and is
auto-discovered — see above). Pure core + a thin plugin edge, mirroring the
template's layering discipline.

| File | Responsibility | Pure? |
|---|---|---|
| `plugin.yaml` | manifest (`name`, `kind: standalone`, `version`) — required for discovery | — |
| `__init__.py` | `register(ctx)`: register the `transform_llm_output` callback; the callback orchestrates and **returns** a replacement string or `None`; **internally fail-closed** (abstain on any error, never raise) | effectful edge |
| `envelope.py` | parse/strip the canonical envelope `⟦conf=… grounded=… missing=…⟧`; reject lookalikes | pure |
| `classify.py` | claim-bearing vs chatter heuristic (conservative — defaults to *claim* when unsure; see §Classification) | pure |
| `policy.py` | gate decision from (is_claim, envelope, threshold) → `pass` / `abstain` | pure |
| `render.py` | build the abstention message + optional confidence badge | pure |
| `gateconfig.py` | read `war_room.*` from `<profile>/config.yaml` (stdlib line scan of the managed block) | IO |
| `audit.py` | append-only gate-decision log (no secrets) | IO |

*(No `verifier.py` in v1 — the callback has no session-evidence access; see §Verifier.)*

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
`grounded`, `threshold = war_room.min_confidence/100`. Output: `None` (leave
unchanged) or a replacement string.

| kind | envelope | conf vs threshold | grounded | decision (return value) |
|---|---|---|---|---|
| chatter | any | — | — | **pass** → `None` if no envelope, else text-minus-stray-envelope |
| claim | valid | ≥ threshold | non-empty | **pass** → text minus envelope (+ optional badge) |
| claim | valid | ≥ threshold | empty/`none` | **abstain** (factual claim needs grounded≠∅) |
| claim | valid | < threshold | any | **abstain** (state `missing`) |
| claim | missing/malformed | — | — | **abstain** (fail closed) |
| (any) | — | — | — | on internal error: **abstain** (never raise — Hermes is fail-open) |

### Classification (conservative bias — load-bearing)

`kind` defaults to **claim** whenever there is any doubt. Only two things are
chatter and skip the gate:
1. an **exact** match in a small closed set of acks/greetings (`ok`, `thanks`,
   `on it`, `done`, 👍, …); and
2. a **pure question** (asking, not asserting — no declarative sentence).

Everything else is a claim and must clear the gate. **Do not exempt a message
merely for being short.** Terse declaratives — "it's down", "payments are
failing", "db is corrupted" — are claims, and a short *ungrounded* assertion is
exactly what the gate exists to stop. The asymmetry is deliberate: a
false-**abstain** on a real claim is safe (the room sees the gap and what would
unblock it); a false-**pass** on a terse claim is the failure mode to avoid. Any
length-based heuristic that routes short text to *chatter* is therefore a bug,
not a convenience — it must not exist.

**Severity (idea #5):** v1 uses a single profile-wide `min_confidence`. A future
DEFCON model can raise the threshold per board severity by rewriting the managed
block (no code change here). The independent-verifier branch is **deferred**
(§Verifier) because the hook lacks session-evidence access.

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
  enforce: true               # Layer 2: gate active (plugin returns None when false)
  show_confidence_badge: true # Layer 2: render ✓/⚠ badge in place of the envelope
# <<< warroom-managed <<<
plugins:
  enabled: true               # required for the shipped plugins/warroom-gate/ to load
```

No `hooks:` block and no `hooks_auto_accept` — those are for *shell* hooks, which
cannot transform LLM output. The gate is a plugin at `<profile>/plugins/warroom-gate/`,
discovered automatically when the gateway runs (`HERMES_HOME=<profile>`).

## Verifier (DEFERRED — not in v1)

The brainstorming choice was "grounding + verifier." v1 ships the **grounding**
half (the envelope + the gate); the **independent verifier** is deferred for a
hard reason found in research: `transform_llm_output` receives only
`response_text`/`session_id`/`model`/`platform` — it has **no handle on the
session's tool/evidence trail**, so a verifier here could only re-judge the text
against itself (weak, and a second LLM call per turn). A real verifier needs
evidence access, which means either a different integration point inside the
agent loop or a Hermes change. Tracked as a follow-up; v1's envelope-grounding
gate is the enforced mechanism, and Layer 1's protocol still asks the agent to
self-verify before emitting the envelope.

## Efficiency

- **Whole path is pure + O(message length):** one anchored regex match + a
  classification heuristic + a table lookup + (on abstain) a small string build.
  **No network, no LLM call, no extra model turn.** Negligible per-message cost.
- Hook is stateless except the append-only audit log (line-buffered).

## Reliability — failure modes (fail-closed where it matters)

**Critical inversion to respect:** Hermes treats a raising hook as *fail-OPEN*
(`conversation_loop.py:4607-4608` logs and leaves text unchanged). So the hook's
internal posture must be the opposite — **catch everything and return the
abstention string** so a bug can never let an ungated claim through.

| Failure | Behavior | Posture |
|---|---|---|
| Internal error on a claim | top-level try/except in `hook.py` → **return abstention** (never raise) | fail-closed |
| Internal error on chatter | return `None` (unchanged) — chatter carries no claim to gate | safe |
| Envelope malformed/missing on a claim | treated as absent → abstain | fail-closed |
| `war_room.enforce: false` | hook returns `None` (Layer 1 protocol still applies) | opt-in |
| Config unreadable | abstain on claims + log error (do **not** fall through to unchanged) | fail-closed |
| Live-streamed platform (terminal/ACP) | replacement applies to final text; already-streamed tokens can't be recalled (out of war-room scope) | documented |

## Security

- **Anti-spoof** (above): only the agent-controlled trailing envelope is trusted;
  user-injected lookalikes are ignored + stripped. The gate treats channel content
  as data, never instructions.
- **Plugin = in-process code, runs per turn.** It executes only when the gateway
  runs (install copies files but runs nothing — verified). Trusting it = trusting
  the distribution you installed. The callback does **no** network I/O and never
  reads secrets — pure parse/classify/gate over `response_text` + a config read.
  Governed by `plugins.enabled`; `enforce: false` makes the callback a no-op.
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
| abstention rendering from `missing` | `test_render.py` | unit |
| hook returns replacement on low-conf claim; `None` on chatter | `test_hook.py` | integration |
| **hook never raises** (fail-closed): inject a parse bug → still returns abstention | `test_hook.py::never_raises` | security |
| `enforce:false` → hook returns `None` | `test_hook.py::disabled` | unit |
| audit log has no secrets | `test_audit.py` | security |
| e2e: low-conf claim suppressed, chatter passes | manual against a test board | e2e |

## Out of scope (this spec)
- The Layer 1 protocol/skill/config knob (shipped by the template sub-project).
- The DEFCON/severity model itself (idea #5) — this consumes `severity`, does not
  define it.
- Multi-agent coordination of who answers (AWR mailbox lanes) — orthogonal.

## Open questions — RESOLVED by research (2026-06-05)
1. ~~Hook replace-vs-block semantics~~ → **RESOLVED.** Wrong hook in draft 1;
   correct hook is `transform_llm_output`, which **replaces** the output by
   returning a non-empty string (`conversation_loop.py:4592-4606`). Abstention is
   an in-place replacement — no separate send. The hook is also profile-wide (no
   `chat_id`) and must be internally fail-closed (Hermes is fail-open on raise).
2. ~~How `severity` reaches the hook~~ → **RESOLVED (deferred design):** v1 is
   single-threshold profile-wide; DEFCON raises it later by rewriting the managed
   block, no hook change. The hook does not need live severity in v1.
3. ~~Verifier model choice~~ → **RESOLVED (deferred feature):** no independent
   verifier in v1 — the hook has no session-evidence access (§Verifier). The
   envelope-grounding gate is the enforced mechanism; verifier is a tracked
   follow-up needing an in-loop integration point.

The implementation plan for this spec is
`docs/superpowers/plans/2026-06-05-war-room-confidence-gate.md`.
