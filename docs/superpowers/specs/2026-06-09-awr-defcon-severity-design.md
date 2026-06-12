# DEFCON / Severity Model — per-severity confidence floors + independent verifier — Design

- **Date:** 2026-06-09
- **Sub-project of:** Agentic War Room (AWR). Extends the **confidence gate**
  (`template/plugins/warroom-gate/`, "Layer 2") and the **war-room agent template**
  (`template/warroom_setup/`). The gate was explicitly designed to accept this
  without rework (see the confidence-gate spec's "Severity hook" + "Verifier" notes).
- **Depends on:** the confidence gate's `decide()` decision table + `Decision`
  dataclass (`wg_policy.py`), the envelope grammar (`wg_envelope.py`), and the
  sentinel-managed `war_room:` block / Option-B rewrite (`schema.py`, `setup.py`);
  the multi-board federation spec for inter-agent verifier routing and
  severity-driven auto-escalation (`2026-06-09-awr-multi-board-federation-design.md`).
- **Referenced by:** `2026-06-09-awr-l1-orchestrator-design.md` (the `/warroom`
  triage protocol assigns severity at intake; this spec consumes it).
- **Status:** design, pre-implementation.

## Problem

The confidence gate today enforces **one** profile-wide floor: a claim posts only
if its envelope clears `min_confidence` (default 75) and is grounded
(`wg_policy.decide`, `wg_gateconfig._DEFAULTS`). Every claim is treated the same,
whether it is "the build is flaky" or "we should fail the customer's prod
database over". A war room needs **graduated rigor**: the higher the stated
severity of an alert, the higher the confidence floor it must clear **and** — at
the top of the scale — a second, independent agent must sign off before the claim
reaches the channel.

We call the severity ladder **DEFCON** (operator-facing label only; the config
keys are plain `severity_*`). Two capabilities:

1. **Per-severity confidence floors.** `alert1` (highest) demands a higher floor
   than `alert2`, which demands more than the `default` baseline. A claim tagged
   `alert1` that clears the baseline 75% but not the alert1 floor (e.g. 95%) is
   abstained — same fail-closed posture, a stricter bar.
2. **Independent verifier requirement.** Above a configured severity, clearing the
   confidence floor is **necessary but not sufficient**: the originating agent must
   obtain a *signed* verdict from a second agent (the "verifier") that
   independently grounded the claim, before the claim posts. Absent a signoff
   within a timeout, the gate **abstains** (fail-closed).

This sub-project consumes a `severity` for each claim; the confidence-gate spec
explicitly defers *defining* severity to here (`Out of scope` of that spec).

## Core decisions (proposed — no user dialogue yet; see Open Decisions)

1. **Severity is a property of a claim, surfaced via the envelope.** The envelope
   grammar gains an optional `sev=` field; the gate reads it the same way it reads
   `conf=`/`grounded=`. This keeps severity *agent-controlled* and in the one slot
   the gate already trusts (anti-spoof: trailing line only). It does **not** require
   per-channel hook payload (which the gate does not have — see Current state).
2. **Severity → threshold is a config table, additive to the managed block.** A new
   `severity_thresholds:` sub-mapping under `war_room:`. The existing scalar
   `min_confidence` becomes the `default` floor when no severity matches — **no
   behavior change for un-tagged claims**, and no break to Option-B sentinel
   rewrites (the block is rewritten wholesale by `patch_war_room_block`).
3. **The confidence gate stays fail-CLOSED and in-process.** Severity routing is a
   pure extension of `wg_policy.decide()` (one more table lookup); the verifier
   wait is wrapped in the same top-level try/except that already returns the
   abstention string on any error (`wg_gate.gate`). A verifier timeout, an
   unreachable mailbox, or a malformed verdict all resolve to **abstain**.
4. **The verifier is a real second agent reached over the mailbox**, not a second
   LLM call inside the hook. The originating gate posts a *verification request*
   to a verifier mailbox label and blocks (bounded) for a *signed verdict*. This
   reuses the federation/mailbox transport — no new network primitive, stdlib only.
5. **Comprehensive scope.** This spec covers the full feature: severity inference,
   the threshold table, the verifier protocol (request/verdict envelopes, routing,
   timeout/fallback), audit, and config/wizard surface. Sequencing is in **Build
   order**, not by omission.

## Current state (VERIFIED against source, 2026-06-09)

- **Single floor only.** `wg_gateconfig._DEFAULTS = {"enforce": False,
  "min_confidence": 75, "show_badge": True}` and `_scan()` only recognizes
  `enforce` / `min_confidence` / `show_confidence_badge` inside the `war_room:`
  block (`wg_gateconfig.py:10`, `:26`). There is **no** severity key today.
- **`decide()` has four branches, no severity.** Inputs are `(is_claim, env,
  threshold)`; it abstains on no-envelope, ungrounded, or below-threshold, else
  passes (`wg_policy.py:18-28`). The single `threshold` is
  `cfg["min_confidence"] / 100.0`, computed once in the callback
  (`wg_gate.py:53`).
- **`Decision` dataclass** is `action` / `reason` / `missing` with a closed reason
  vocabulary (`chatter | ok | no-envelope | ungrounded | below-threshold |
  empty-body | internal-error`) (`wg_policy.py:11-15`). A new severity reason must
  be added here and mirrored in `wg_render.abstention()` (`wg_render.py:7-22`).
- **Envelope grammar has no `sev`.** `_ENV_RE` matches exactly
  `⟦conf=… grounded=… missing=…⟧` anchored `^…$` on the final line; `Envelope` is
  `conf` / `grounded` / `missing` (`wg_envelope.py:21-27`, `:31-35`). Bounded
  quantifiers only (ReDoS-safe). Adding `sev=` means an additive, still-anchored
  alternation, defaulting to absent when omitted (back-compat).
- **The hook is fail-CLOSED around a fail-OPEN host.** `wg_gate.gate()` wraps
  everything in `try/except Exception` and returns the abstention string on any
  internal error (`wg_gate.py:31`, `:64-70`) — because Hermes leaves text unchanged
  if the hook raises. **Any verifier logic must live inside this guard.**
- **The gate is profile-wide, no `chat_id`, no session-evidence handle.** The only
  grounding signal in-hook is the agent's own envelope (confidence-gate spec, "Two
  constraints"). This is *why* v1 deferred the verifier: a verifier inside the hook
  could only re-judge text against itself. The verifier here lives **outside** the
  hook process — a separate agent with its own tools/evidence, reached by message.
- **Config is a line scan, not PyYAML.** `wg_gateconfig._scan()` walks lines,
  detecting block end by "a non-indented, non-comment, non-empty line"
  (`wg_gateconfig.py:23-24`). A nested `severity_thresholds:` mapping is *indented*,
  so it stays inside the block — but the scanner must learn to parse a nested
  mapping (today it only matches flat `key: value` via one regex,
  `wg_gateconfig.py:26`).
- **Managed block is rewritten wholesale.** `patch_war_room_block` renders the
  block from `schema.DEFAULTS` + `schema.WAR_ROOM_KEYS` and replaces the
  sentinel region (or re-anchors via the Option-B YAML-key fallback)
  (`setup.py:182-220`, `_replace_sentinel_block` at `setup.py:55-96`). Because the
  block is **regenerated, not edited in place**, adding a nested mapping requires
  the renderer to emit nested lines — a flat `for key in WAR_ROOM_KEYS` loop
  (`setup.py:211-215`) cannot emit a sub-mapping as-is.
- **Wizard knobs.** `selectables.TEXT_FIELDS` collects `warroom.board`,
  `warroom.min_confidence`, `warroom.label` (`selectables.py:72-79`);
  `warroom.enforce` is a toggle (`selectables.py:54`). `run_setup` passes
  `min_confidence` + `enforce` into `patch_war_room_block` and calls
  `enroll.bootstrap(profile_root, board, label)` (`setup.py:418-431`).
- **Enrollment writes only `MAILBOX_BOARD`/`MAILBOX_LABEL` to `.env`**
  (`enroll._runtime_env_values`, `enroll.py:126-143`); the verifier's *label* is
  the addressing handle this spec routes to.
- **Audit log** records `action / reason / conf / kind / sha` and no secrets
  (`wg_audit.log`, `wg_audit.py:15-37`). Severity + verifier outcome are additive
  fields.

All changes below are **additive and backward-compatible**: an envelope with no
`sev=` is `default`; a `war_room:` block with no `severity_thresholds:` uses the
scalar `min_confidence` for every claim exactly as today; `require_verifier` off
(default) means the verifier path never runs.

## Architecture & components

Two layers, mirroring the federation spec:

- **`template/plugins/warroom-gate/` (the gate that enforces severity):** envelope
  `sev=` parsing, severity→threshold resolution, `decide()` extension, the verifier
  client (request + bounded wait + verdict parse), audit fields.
- **`template/warroom_setup/` (config + wizard surface):** the
  `severity_thresholds` / `require_verifier` / `verifier_label` /
  `verifier_timeout_s` keys, their defaults, wizard prompts, and the renderer that
  emits the nested mapping into the managed block.
- **A verifier agent role** (a war-room agent running the same distribution, with
  `war_room.role: verifier`) that subscribes to verification requests on its label
  and emits signed verdicts. It is a *behavioral* role layered on the existing
  runtime — no new daemon.

### 1. Severity inference (`wg_envelope.py` + `wg_classify.py`)

- The envelope grammar gains an **optional** trailing `sev=<token>` field, token in
  a closed vocabulary `{alert1, alert2, alert3, default}` (extensible via config).
  `Envelope` gains `sev: str = "default"`. Absent ⇒ `default`. Still anchored,
  still bounded-quantifier ReDoS-safe.
- The agent (Layer 1 protocol + the `/warroom` orchestrator at intake) sets `sev`.
  This is the **explicit operator/agent tag** path.
- **Open Decision (severity inference):** explicit envelope tag vs.
  classifier-inferred severity vs. both. *Recommendation: explicit envelope tag is
  the source of truth (v1), with an optional, conservative **classifier upgrade**
  in `wg_classify` that can only ever *raise* severity, never lower it (keyword
  cues like "prod", "outage", "data loss" bump an untagged/`default` claim to
  `alert2`). Rationale: the gate already trusts the agent-controlled envelope slot;
  letting the classifier only escalate preserves fail-closed (it can demand more
  rigor, never less), and matches the existing conservative "when unsure, gate"
  bias of `is_claim` (`wg_classify.py:1-6`). A pure-explicit v1 is simplest;
  classifier upgrade is a Phase 3 add-on behind a `severity_inference: explicit |
  hybrid` config flag.*

### 2. Severity → threshold resolution (`wg_gateconfig.py` + `wg_policy.py`)

- `wg_gateconfig.read()` returns a new `severity_thresholds: Dict[str, int]` (e.g.
  `{"alert1": 95, "alert2": 85, "default": 75}`), plus `require_verifier_at: str`
  (the lowest severity that requires a verifier, e.g. `alert1`), `verifier_label:
  str`, and `verifier_timeout_s: int`. The scalar `min_confidence` populates
  `default` when `severity_thresholds` is absent (back-compat).
- `wg_policy.decide()` gains a `severity` argument and resolves the floor from the
  table: `threshold = severity_thresholds.get(sev, severity_thresholds["default"])
  / 100.0`. The four existing branches are unchanged; only the threshold value
  changes per claim. A new abstain reason `below-severity-floor` distinguishes a
  claim that cleared `default` but not its alert floor (clearer audit + message).
- **Open Decision (threshold config shape):** how to extend the single
  `min_confidence` key without breaking Option-B rewrites. *Recommendation: keep
  `min_confidence: 75` as the **baseline/`default`** and ADD a nested
  `severity_thresholds:` mapping; `default` is implied from `min_confidence` if not
  restated. This is fully additive — un-upgraded profiles render exactly today's
  block, and `_replace_sentinel_block` rewrites the whole block so a nested mapping
  is just more rendered lines. The alternative (replacing `min_confidence` with a
  table) would break every existing test/installer that passes
  `min_confidence=`.*

### 3. Verifier client — inside the gate (`wg_verify.py`, NEW)

When `decide()` returns PASS **and** the claim's severity is at or above
`require_verifier_at`, the gate does not return the cleared text directly. Instead
`wg_verify.request_and_wait(...)`:

1. **Builds a verification request** (shape below) and posts it to the mailbox via
   the discovered CLI (`enroll.discover_mailbox_cli`, `enroll.py:74-100`) — a
   `subprocess` call to `mailbox send --to <verifier_label> --scope escalate
   <json>`. Stdlib `subprocess` only; no client import (mailbox package is
   read-only — `enroll.py` docstring).
2. **Blocks for a verdict** with a hard deadline `verifier_timeout_s`, polling the
   mailbox for a reply addressed back to this agent's label and carrying the
   matching `request_id`. Polling is a bounded loop of short `subprocess` reads
   (stdlib `time` + the CLI's `inbox --json` read), never an unbounded wait.
3. **Resolves:**
   - **signed** verdict (`verdict=signed`) with the verifier's own grounded
     envelope ⇒ the gate returns the original (badged) text — now double-signed.
   - **rejected** verdict (`verdict=rejected`) ⇒ **abstain** with the verifier's
     stated gap as `missing`.
   - **timeout / unreachable / malformed verdict** ⇒ **abstain** (fail-closed),
     reason `verifier-timeout` / `verifier-unreachable`.
- This entire call sits inside `wg_gate.gate()`'s top-level try/except, so any
  unexpected error still degrades to the generic abstention (`wg_gate.py:64-70`).
- **Open Decision (verifier protocol + which severities):** the verdict envelope,
  how the originator waits, timeout/fallback, and which severities require it.
  *Recommendation: only the top severity (`alert1`) requires a verifier in v1
  (`require_verifier_at: alert1`); the verdict is a mailbox message whose body is a
  small JSON object `{request_id, verdict: signed|rejected, by, envelope, gap}`;
  the originator polls its inbox with a 30s default deadline; on any
  non-`signed` outcome (including timeout) it **abstains**. Rationale: blocking on
  a second agent is the most latency-expensive thing the gate can do (handoff §6
  gotcha: "if every claim above threshold blocks on a verifier, latency could
  explode") — restricting it to the rare top tier bounds the blast radius, and
  abstain-on-timeout keeps the fail-closed contract.*

### 4. Verifier agent role (behavioral, `template/skills/`)

- A second war-room agent enrolled with `war_room.role: verifier` and a known
  `verifier_label`. Its `/warroom`-style protocol (skill doc) instructs it to:
  watch its inbox for verification requests, **independently** ground the claim
  using its own tools (it has session-evidence access the requester's hook lacks),
  emit its own confidence envelope, and reply `mailbox send --to <requester>` with
  a `signed` or `rejected` verdict carrying its envelope.
- The verifier MUST NOT simply echo the requester's confidence — the skill doc
  frames it as an adversarial second look (the same posture as the
  adversarial-agent pattern used elsewhere in AWR).
- **Open Decision (verifier selection / addressing):** how the verifier is chosen
  and addressed. *Recommendation: route by **mailbox label** — a new
  `war_room.verifier_label` config key names the verifier's mailbox label; the gate
  sends `--to <verifier_label>`. Selection is operator-configured (a designated
  verifier agent per board), NOT dynamic election in v1. This depends on the
  federation spec's labeled-message routing (`send --to <label>`); cross-ref
  `2026-06-09-awr-multi-board-federation-design.md` §"CLI surface". A future
  enhancement could pick any idle peer on the board via `mailbox fleet`, but that
  needs liveness + load logic out of scope here.*

### 5. Severity-driven auto-escalation (federation hook)

High-severity claims that pass the gate should also become **visible up the board
tree** automatically. When a claim's resolved severity ≥ a configured
`escalate_at` (e.g. `alert2`), the gate posts the cleared claim with
`--scope escalate` so the federation layer surfaces it to ancestor boards (the
federation spec's `escalate` mechanism;
`2026-06-09-awr-multi-board-federation-design.md` §3/§"CLI surface"). This is the
hook the federation spec's "Automatic severity-driven escalation — lives in the
DEFCON/severity spec" note points at.
- **Open Decision (auto-escalation):** whether the gate itself escalates, or only
  annotates and lets the orchestrator escalate. *Recommendation: the gate annotates
  severity in the audit + envelope, and the **`/warroom` orchestrator** performs
  the `escalate` post at intake time (it owns routing); the gate stays a pure
  transform that does not initiate new sends except the verifier request. This
  keeps the gate's side effects minimal and avoids double-posting. Behind
  `auto_escalate: true` if we later want the gate to do it.*

## Data model & config

### Extended war-room managed YAML block

```yaml
# >>> warroom-managed (set via `warroom setup`) >>>
war_room:
  enabled: true
  board: squad-api
  label: api-sh
  role: contributor          # or `verifier` for a designated verifier agent
  min_confidence: 75         # baseline == severity_thresholds.default
  gate_action: abstain
  enforce: true              # Layer 2: gate active
  show_confidence_badge: true
  # --- DEFCON / severity (all NEW, all optional) ---
  severity_thresholds:       # per-severity confidence floors (%)
    alert1: 95
    alert2: 85
    default: 75              # falls back to min_confidence if omitted
  severity_inference: explicit   # explicit | hybrid  (hybrid lets classifier raise only)
  require_verifier_at: alert1    # lowest severity that needs a 2nd-agent signoff ("" = never)
  verifier_label: ""             # mailbox label of the designated verifier agent
  verifier_timeout_s: 30         # bounded wait; on timeout -> abstain (fail-closed)
  escalate_at: alert2            # severity at/above which a passed claim auto-escalates ("" = never)
# <<< warroom-managed <<<
plugins:
  enabled: true
```

`severity_thresholds` is a nested mapping; `wg_gateconfig._scan()` and the
`patch_war_room_block` renderer both learn to handle one nested level (the only
nested key in the block). Everything else stays flat. Empty-string scalars are
omitted by the renderer exactly as today (`setup.py:213`).

### Confidence envelope — `sev=` (additive, optional)

```
⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧
```

- `sev` ∈ closed vocab `{alert1, alert2, alert3, default}`; absent ⇒ `default`.
- Appended AFTER `missing=` so the existing field order is preserved; the regex is
  an additive optional group, still anchored `^…$`, bounded quantifiers only.
- Anti-spoof unchanged: only the trailing-line, agent-controlled envelope is read;
  a user-pasted `sev=alert1` mid-message is ignored and stripped
  (`wg_envelope.parse_last_line` / `strip_stray_envelopes`, `wg_envelope.py:38-57`).

### Verifier request message (gate → verifier, `--scope escalate`)

```jsonc
{
  "kind": "verify_request",
  "request_id": "<uuid4 hex>",
  "from": "api-sh",                  // requester label
  "severity": "alert1",
  "conf": 0.97,
  "grounded": ["tool", "file"],
  "claim_sha": "<sha256[:8] of claim text>",   // NO raw claim body in transit by default
  "claim": "<claim text>",           // see Open Decision below
  "deadline_ts": 1733760000
}
```

### Verifier verdict message (verifier → requester)

```jsonc
{
  "kind": "verify_verdict",
  "request_id": "<uuid4 hex>",       // echoes the request
  "by": "verify-sh",                 // verifier label
  "verdict": "signed",               // signed | rejected
  "envelope": "⟦conf=0.96 grounded=tool missing=none⟧",  // verifier's own grounding
  "gap": ""                          // on rejected: what was missing (-> abstention `missing`)
}
```

- **Open Decision (claim body in transit):** does the request carry the full claim
  text, or only a sha + a pointer? *Recommendation: carry the full claim text — the
  verifier cannot independently judge a claim it cannot read, and the mailbox is a
  local single-host state dir (federation spec, "single-host"), so this is not a
  network exfil path. The audit log still records only the sha (no body), per the
  existing no-secrets convention (`wg_audit.py:18`).*

## Reliability — failure modes (fail-closed where it matters)

The host is **fail-OPEN on a raising hook**; this gate is **fail-CLOSED**
(`wg_gate.py:64-70`, confidence-gate spec §Reliability). Every new failure mode
below resolves to **abstain on a claim**.

| Failure | Behavior | Posture |
|---|---|---|
| Unknown/malformed `sev=` token | treated as `default` severity (lowest floor it can map to safely is `default`, but see note) | safe-default |
| `severity_thresholds` missing for a present `sev` | fall back to `default` floor (= `min_confidence`) | safe |
| Config has `severity_thresholds` but unparseable nested map | use scalar `min_confidence` for all + log error | fail-closed |
| `require_verifier_at` set but `verifier_label` blank | abstain on the gated severity (can't verify ⇒ can't post) + log misconfig | fail-closed |
| Mailbox CLI not found at verify time | **abstain** (`verifier-unreachable`) — same as `enroll` `cli-not-found` | fail-closed |
| Verifier does not reply within `verifier_timeout_s` | **abstain** (`verifier-timeout`) | fail-closed |
| Verifier replies `rejected` | **abstain**, surface verifier's `gap` as `missing` | fail-closed |
| Verdict JSON malformed / `request_id` mismatch | ignore that message; if none valid before deadline ⇒ abstain | fail-closed |
| Any internal error in `wg_verify` | propagates to `wg_gate`'s top-level except ⇒ generic abstention | fail-closed |
| `enforce: false` | whole gate (incl. severity + verifier) is a no-op (`wg_gate.py:36`) | opt-in |

> **Note on unknown `sev`:** mapping an unknown token to `default` is *less* strict
> than treating it as the highest floor. **Open Decision:** unknown `sev` ⇒
> `default` (lenient, simplest) vs. ⇒ highest-known floor (strictest, safest). *Per
> spec recommendation: map unknown ⇒ `default` BUT log it as an anomaly; a genuine
> high-severity claim must use a known token, and the classifier-upgrade path
> (hybrid mode) is the safety net. Treating typos as alert1 would make the gate
> abstain on benign typos — too brittle.*

**Critical: the verifier wait must not deadlock or run unbounded.** The poll loop
uses a monotonic deadline; `verifier_timeout_s` is clamped to a sane max (e.g.
≤120s) by the config reader so a misconfig can't hang the gateway turn.

## Security

- **Anti-spoof preserved.** `sev=` is read only from the agent-controlled trailing
  envelope; mid-message lookalikes are ignored + stripped (same mechanism as
  `conf=`, `wg_envelope.py`). A channel user cannot downgrade severity to dodge the
  verifier, nor upgrade it to trigger spurious verification (it would only make the
  bar *stricter* on the agent's own claim).
- **Verifier verdicts are authenticated by transport, not by content.** The verdict
  is trusted because it arrives on the mailbox from the configured `verifier_label`;
  the gate matches `by == verifier_label` and `request_id`. A message claiming
  `verdict=signed` from any other label is ignored. (Federation spec: records keep
  their original `from`, can't be spoofed as originating elsewhere.)
- **No secrets in transit/logs.** Audit records sha + severity + verifier outcome,
  never tokens, never the verdict body (`wg_audit.py:18`). The request carries the
  claim text (a war-room message the agent was about to post anyway) on a
  single-host local socket — not a new exfil surface.
- **Least authority + stdlib-only.** `wg_verify` shells out to the already-trusted
  `mailbox` CLI via `subprocess` (no new dep, no mailbox client import — the package
  stays read-only per `enroll.py`). It reads only `war_room.*` config + the
  message text; it never touches `.env`, `auth.json`, or `local/` beyond the audit
  log.
- **Verifier as a trust boundary.** Trusting a `signed` verdict = trusting the
  configured verifier agent (a peer in the same distribution). The operator
  designates it; v1 does not auto-elect (Open Decision §4).

## Observability

- **Audit log gains `sev=` and `verify=`.** `wg_audit.log` line extends to
  `ts action=… reason=… conf=… sev=<severity> verify=<none|signed|rejected|timeout|unreachable>
  kind=… sha=…`. Still append-only, mode 0600, no secrets (`wg_audit.py:23-35`).
  This is the war room's record of *which severity bar* a claim faced and *whether
  a second agent signed it*.
- **Reasons are explicit.** New `Decision.reason` values — `below-severity-floor`,
  `verifier-rejected`, `verifier-timeout`, `verifier-unreachable` — make
  abstentions self-documenting in both the log and the user-visible message
  (`wg_render.abstention`).
- **A future `warroom gate --stats`** (noted as out-of-scope in the gate spec) would
  summarize pass/abstain/verify counts per severity; this spec adds the per-severity
  + verifier dimensions the stats would aggregate.

## Test strategy

**`template/plugins/warroom-gate/` (pure core, no gateway):**
- `test_envelope.py` — `sev=` parses; absent ⇒ `default`; unknown token handling;
  `sev=` still anchored last-line-only; spoofed mid-message `sev=` ignored; the
  extended regex is still ReDoS-safe (extend the existing `redos` test).
- `test_classify.py` — (hybrid mode) classifier raises severity on cue words, never
  lowers an explicit tag.
- `test_policy.py` — extend the full decision table for every severity × envelope
  row: `default`/`alert2`/`alert1` floors, `below-severity-floor` vs
  `below-threshold`, missing `severity_thresholds` ⇒ scalar fallback.
- `test_gateconfig.py` — nested `severity_thresholds:` parsed; block-end detection
  still correct with a nested mapping present; `min_confidence`-only profile yields
  `{default: min_confidence}`; `verifier_timeout_s` clamp.
- `test_render.py` — abstention text for each new reason (severity floor + verifier
  outcomes).
- `test_verify.py` (NEW) — request shape; verdict parse (signed/rejected/malformed);
  `request_id` mismatch ignored; `by != verifier_label` ignored; **timeout ⇒
  abstain** (monotonic-clock fake, no real sleep); CLI-not-found ⇒ abstain;
  `subprocess` is the only effect (mock it).
- `test_gate.py` — end-to-end callback: a passing `alert1` claim with a `signed`
  verdict returns the badged text; with a `rejected`/timeout verdict returns the
  abstention; **the callback never raises** even if `wg_verify` throws (extend the
  existing fail-closed `never_raises` test); `enforce:false` ⇒ `None`.
- `test_audit.py` — log carries `sev=`/`verify=` and still no secrets.

**Integration (real daemon, `--runintegration`):**
- Two profiles (`api-sh` contributor, `verify-sh` verifier) on board `squad-api`;
  contributor posts an `alert1` claim; assert the request lands in `verify-sh`'s
  inbox, a `signed` verdict round-trips, and the claim posts double-signed; a
  second run where the verifier `rejects` ⇒ contributor abstains; a third where the
  verifier is silent ⇒ contributor abstains on timeout.

## File-path map (complete — every file created/modified)

**`template/plugins/warroom-gate/` (the gate):**
- `wg_envelope.py` — add optional `sev=` to `_ENV_RE` (additive anchored group) +
  `Envelope.sev` field; default `default`. *Why: severity must ride the one
  agent-controlled, anti-spoofed slot the gate already trusts.*
- `wg_gateconfig.py` — parse nested `severity_thresholds:` + `severity_inference`,
  `require_verifier_at`, `verifier_label`, `verifier_timeout_s` (with clamps);
  default `severity_thresholds = {default: min_confidence}`. *Why: the gate needs
  the per-severity floors + verifier config; back-compat fallback to the scalar.*
- `wg_policy.py` — `decide()` takes `severity` + `severity_thresholds`; resolves the
  per-severity floor; new abstain reason `below-severity-floor`; add the verifier
  reason constants to the `Decision.reason` vocab. *Why: severity routing is a pure
  table lookup on top of the existing four branches.*
- `wg_verify.py` (NEW) — `request_and_wait()`: build request, `subprocess` to
  `mailbox send`, bounded poll for a matching signed/rejected verdict, return a
  resolution; all stdlib. *Why: the independent verifier is a real second agent
  over the mailbox, not an in-hook LLM call.*
- `wg_render.py` — abstention copy for `below-severity-floor`, `verifier-rejected`,
  `verifier-timeout`, `verifier-unreachable`; (optional) severity in the pass badge.
  *Why: self-documenting abstentions per new reason.*
- `wg_gate.py` — after a PASS, if `severity ≥ require_verifier_at` call
  `wg_verify.request_and_wait()` (inside the existing top-level try/except) and
  resolve pass/abstain; pass `severity` into `decide()`; log `sev`/`verify`. *Why:
  the verifier gate composes at the one effectful edge, staying fail-closed.*
- `wg_audit.py` — extend the log line with `sev=` + `verify=`. *Why: per-severity +
  verifier observability with no secrets.*
- `plugin.yaml` — version bump (manifest). *Why: discovery metadata.*

**`template/warroom_setup/` (config + wizard):**
- `schema.py` — add `severity_thresholds`, `severity_inference`,
  `require_verifier_at`, `verifier_label`, `verifier_timeout_s`, `escalate_at` to
  `WAR_ROOM_KEYS` + `DEFAULTS` (with `role` extended to allow `verifier`). *Why:
  single source of truth for the new managed keys; renderer + scanner read it.*
- `setup.py` — `patch_war_room_block` renderer emits the nested
  `severity_thresholds:` mapping (the one nested case) while keeping the wholesale
  sentinel rewrite / Option-B fallback intact. *Why: the block is regenerated, so
  the renderer must know how to emit one nested level.*
- `selectables.py` — optional `TextField`s for `warroom.severity_alert1`,
  `warroom.severity_alert2` (mapped into the table), `warroom.verifier_label`,
  `warroom.require_verifier` toggle (`enable_if="warroom.enroll"`); **appended after
  existing fields** to avoid reordering the wizard. *Why: collect the new knobs
  without breaking the F10 append-order discipline.*
- `enroll.py` — no `.env` shape change (federation/runtime unchanged); the verifier
  label is a config-routed mailbox label, not an env var. *Why: routing stays in
  `config.yaml` per locked decision #1; documented as intentionally untouched.*
- `template/skills/warroom/SKILL.md` — `/warroom` triage assigns `sev=` at intake +
  performs `escalate` for high severity. *Why: the explicit-tag source of truth +
  the auto-escalation hook live in the orchestrator protocol.*
- `template/skills/confidence-gate/SKILL.md` — document the `sev=` envelope field and
  the verifier handshake the agent participates in. *Why: Layer 1 protocol must
  teach the agent to emit `sev=` and to answer verify requests.*
- `template/skills/warroom-verifier/SKILL.md` (NEW) — the verifier-role protocol:
  watch inbox, independently ground, reply signed/rejected. *Why: the verifier is a
  behavioral role, not new code; its rigor lives in the skill doc.*

**Docs:**
- `docs/superpowers/specs/2026-06-09-awr-multi-board-federation-design.md` — already
  references this spec + exposes `escalate`/`--to <label>`; no edit needed (cross-ref
  only). *Why: this spec's verifier routing + auto-escalation depend on it.*

**Tests:** `template/tests/test_envelope.py`, `test_classify.py`, `test_policy.py`,
`test_gateconfig.py`, `test_render.py`, `test_gate.py`, `test_audit.py` (extend);
`test_verify.py` (new); `template/tests/test_schema.py`, `test_setup.py`,
`test_selectables.py` (extend for the new keys + nested-mapping render). *Why: every
new branch + the nested-config render + the verifier resolution are covered, with
the fail-closed `never_raises` guard extended.*

## Build order (phasing — NOT omission; everything above is in scope)

1. **Phase 1 — per-severity floors (no verifier).** `Envelope.sev`,
   `severity_thresholds` config (schema + scanner + renderer), `decide(severity=…)`,
   `below-severity-floor` reason + render, audit `sev=`. Pure, in-process, ships
   working graduated floors with zero inter-agent dependency. Back-compat:
   un-tagged claims and untouched blocks behave identically to today.
2. **Phase 2 — independent verifier.** `wg_verify.py`, request/verdict envelopes,
   bounded poll, `require_verifier_at` / `verifier_label` / `verifier_timeout_s`
   config, the verifier-role skill doc, audit `verify=`. Depends on the federation
   spec's labeled `send --to`/inbox round-trip.
3. **Phase 3 — classifier severity upgrade (hybrid).** `wg_classify` cue-word
   escalation behind `severity_inference: hybrid`; raise-only, never lower.
4. **Phase 4 — auto-escalation hook.** Wire high-severity passed claims to the
   federation `escalate` scope (orchestrator-driven per Open Decision §5), behind
   `escalate_at`.

Each phase is independently shippable and leaves the suite green (the gate's
fail-closed contract holds at every step).

## Out of scope (this spec)

- **The federation transport itself** (board tree, `escalate`/`broadcast`, `send
  --to <label>` routing) — defined in
  `2026-06-09-awr-multi-board-federation-design.md`; this spec *consumes* it.
- **Dynamic verifier election / load-balancing across idle peers** — v1 uses a
  static operator-configured `verifier_label`; auto-selection via `mailbox fleet`
  is a future enhancement.
- **The `/warroom` orchestrator's full triage protocol** — defined in the L1
  orchestrator spec; this spec only specifies the `sev=` it must emit + the
  escalate hook.
- **Per-channel severity** — the gate is profile-wide with no `chat_id` (gate spec,
  "Two constraints"); severity is per-claim (envelope), not per-channel.
- **A second LLM judge inside the hook** — explicitly rejected; the verifier is a
  real agent with its own evidence access (the reason v1 deferred the verifier).

## Open questions

1. **Verifier latency budget under load.** If multiple `alert1` claims arrive at
   once, the verifier serializes them; does the 30s deadline per claim compound into
   a poor war-room experience? (Recommend: keep `alert1` rare by policy; revisit a
   queue/SLA only if real traffic shows contention — ties to §9 classifier tuning.)
2. **Self-verification guard.** Must the verifier be a *different* agent than the
   requester? (Recommend: yes — the gate refuses to send a request to its own label;
   a verifier verdict from `by == requester` is ignored. Prevents an agent
   self-signing.)
3. **Verifier availability fallback.** If the designated verifier is offline, should
   the gate degrade to "floor-only" (post if it cleared the alert floor) or stay
   strict-abstain? (Recommend: strict-abstain — that is the whole point of requiring
   a verifier at the top tier; a "post anyway when verifier is down" mode would be a
   fail-open hole. Make it an explicit, off-by-default `verifier_optional` knob if
   ever wanted.)
4. **Severity vocabulary extensibility.** Is the fixed `{alert1, alert2, alert3,
   default}` set enough, or should the vocab be config-driven from the
   `severity_thresholds` keys themselves? (Recommend: derive the valid severity
   tokens from the `severity_thresholds` mapping keys — one source of truth — and
   keep `default` reserved.)
```
