# Real-Traffic Classifier Tuning — Design

- **Date:** 2026-06-09
- **Sub-project of:** Agentic War Room (AWR). Tunes the **claim-vs-chatter
  classifier** (`is_claim`) inside the confidence gate (`template/plugins/warroom-gate/`).
- **Depends on:** **real deployment + traffic data.** This is a methodology + harness,
  not a feature. The actual tuning *cannot start* until a real war room is adopted and
  used, and that usage produces classifier failure cases (false positives / false
  negatives). The harness + log-format work below is doable now; the tuning loop is
  gated on data.
- **Referenced by:** the confidence-gate design (`2026-06-05-war-room-confidence-gate-design.md`,
  "Classification (conservative bias — load-bearing)", lines 167–182, and the
  "tune with real traffic" note at `wg_classify.py:5`). Independent of the
  multi-board federation spec.
- **Status:** design, pre-implementation, **DATA-GATED** (▶ blocked on real adoption
  producing failure data — see Build order).

## Problem

The gate's classifier decides, per outbound message, whether the text is a **claim**
(must clear the confidence gate) or **chatter** (skips the gate). It is a small
stdlib heuristic and was the single highest-risk module in the build: of the four
plan defects found, two were classifier-specific (a length short-circuit and an
emoji-strip). It is currently tuned against a handful of hand-written examples only.

Two failure modes matter:

- **False positive (over-gating):** an ack/greeting/chatter message is classified as
  a claim and gets gated/abstained — noisy, the room sees a "🛑 holding back" on
  "thanks!".
- **False negative (under-gating):** a real, ungrounded factual claim is classified
  as chatter and **passes the gate unverified** — the exact thing the gate exists to
  stop. This is the dangerous one.

We have no way today to know which of these is happening in practice, because we have
no real traffic. This spec defines: (1) the **tuning loop** (collect failures →
label → regression-test → minimal tune → verify), (2) the **data-collection harness**
(what the audit log must capture to make retroactive failure analysis possible
*without storing secrets*), and (3) the **regression-test workflow** that keeps the
classifier from regressing as it's tuned. It defines a PROCESS and the small amount of
plumbing that process needs — it adds **no product features**.

## Core decisions

These are the load-bearing rules. The first three are **non-negotiable hard
constraints** carried forward verbatim from the wrap handoff (§9) and the gate spec;
re-litigating them is out of scope.

1. **NEVER reintroduce a length-based heuristic.** Terse declaratives — "it's down",
   "payments are failing", "db is corrupted" — MUST gate. Any rule that routes text
   to *chatter* because it is short is a bug, not a convenience, and must not exist.
   The fix for "an ack got gated" is to **add the exact token to the `_CHATTER` set**
   (`wg_classify.py:7-11`), not to add a length short-circuit. (Gate spec lines
   178–182; handoff §9.)
2. **Default-to-gate bias is preserved.** When the classifier is unsure, it classifies
   as **claim** (gate it). The asymmetry is deliberate: a false-*abstain* on a real
   claim is safe (the room sees the gap and what would unblock it); a false-*pass* on
   a terse claim is the failure mode to avoid. Tuning must never widen the chatter set
   so far that the default flips. Every new `_CHATTER` entry must be an *exact*,
   *unambiguous* ack/greeting/closed-token — never a substring or fuzzy match.
3. **Tuning is minimal and test-driven.** Per real failure case: add a regression test
   that asserts the desired classification *first*, then change the classifier *just
   enough* to make it pass, then re-run the whole suite. One failure case → one test →
   one minimal change → one commit. No speculative broadening.
4. **Audit log stays hash-only.** The log already records a `sha256(text)[:8]` digest
   and *never* the body (`wg_audit.py:18`). Any log extension keeps that invariant: no
   raw message bodies, no secrets, ever. (See Security.)
5. **Stdlib only.** No new pip deps in `template/pyproject.toml`. The review tool, the
   fixtures, and any log extension are all plain Python 3.9+ / stdlib.
6. **The classifier's public contract is frozen.** `is_claim(text) -> bool` stays a
   pure function with no I/O. All tuning happens by editing `_CHATTER` and the small
   set of structural rules — never by adding state, network calls, or model calls.

> **Open Decision — what "the classifier" may grow into.** Recommendation: keep
> `is_claim` a pure, rule-based, exact-match function indefinitely. Do **not** evolve
> it into a learned/statistical classifier — that would break stdlib-only, make the
> default-to-gate bias non-auditable, and reintroduce the fuzzy behavior the exact-set
> design exists to avoid. If real traffic ever demands more than exact-set + a few
> structural rules can express, that is a *new* spec, not this tuning loop.

## Current state (VERIFIED against `template/` source, 2026-06-09)

**What the classifier does today** (`template/plugins/warroom-gate/wg_classify.py`):

- `_CHATTER` is a closed set of exact lowercased tokens — acks/greetings/emojis:
  `ok, okay, kk, got it, thanks, thank you, ty, on it, sure, yep, yes, no, nope, hi,
  hey, hello, ack, acknowledged, done, +1, 👍, ✅` (`wg_classify.py:7-11`).
- `is_claim(text)` (`wg_classify.py:14-31`):
  - empty / whitespace → `False` (chatter) (`:16-18`).
  - lowercase + strip of `" .!👍✅"`; if it strips to empty (bare 👍/✅/punct/"…") or
    matches `_CHATTER` exactly → `False` (`:19-23`).
  - **pure question** (ends `?`, single line, `len < 200`, no `.` before the `?`) →
    `False` (`:26`).
  - **everything else → `True` (CLAIM)** — the default-to-gate branch (`:31`).
  - **No length-based exemption.** The deliberate absence is documented in-code at
    `wg_classify.py:28-30` ("any length short-circuit is a bug, not a convenience").
- Tests today (`template/tests/test_classify.py`, 5 cases): chatter set, pure
  question, substantive assertion, terse declarative (`"it's down"` etc. → claim),
  empty input.

**How the classifier is wired** (`template/plugins/warroom-gate/wg_gate.py`):

- `gate()` parses the envelope, then calls `wg_classify.is_claim(...)` (`:47`).
- If **not a claim**, it strips stray envelopes and returns — and **does NOT call the
  audit log** (`:49-51`). Only the claim branch (`:56`) and the empty-body branch
  (`:45`) call `wg_audit.log`.
- The policy `Decision` (`wg_policy.py:11-15`) carries `action` (pass|abstain),
  `reason` (chatter|ok|no-envelope|ungrounded|below-threshold|empty-body|
  internal-error), and `missing`.

**What the audit log captures today** (`template/plugins/warroom-gate/wg_audit.py`):

- `log(profile_root, decision, conf, kind, text)` writes one line per logged decision
  to `<profile>/local/war_room/gate.log`, dir `0700`, file `0600` (`:23-35`):
  ```
  2026-06-09T18:22:01+00:00 action=abstain reason=below-threshold conf=0.62 kind=claim sha=1a2b3c4d
  ```
  where `sha = sha256(text)[:8]` (`:18`), `conf` is the envelope confidence or `-`,
  `kind` is the caller-supplied label (`"claim"` / `"empty-body"`).
- Best-effort: any logging exception is swallowed (`:36-37`) so logging can't fail the
  gate.

**VERIFIED GAP — the log is NOT sufficient to tune from as-is.** Three concrete
problems for retroactive classification analysis:

1. **Chatter is invisible.** The chatter branch never logs (`wg_gate.py:49-51`). So
   *false positives are recorded* (chatter mis-gated → logged as a `claim` abstain),
   but *true chatter and false negatives* (a claim mis-classified as chatter) leave
   **no log line at all**. You cannot find under-gating in a log that omits every
   chatter decision.
2. **The classifier verdict is not recorded distinctly from the gate decision.** The
   log records the gate's *policy* `action`/`reason`, not the *classifier's* `is_claim`
   boolean. `kind=claim` is the caller's hint, not a stable record of "the classifier
   said claim." There is no field saying which branch of `is_claim` fired.
3. **The 8-char sha is collision-prone and un-joinable.** 8 hex chars (32 bits) is
   fine for "this isn't the body" but too short to reliably join a log line back to a
   reviewed message, and there are no minimal *features* (length bucket, ends-with-`?`,
   matched-chatter-token) to label from without the body.

Conclusion: a small, additive log-format extension is required before the tuning loop
can run (see Architecture §2, Data model). The extension stays hash-only.

## Architecture & components

Two halves: the **tuning loop** (a documented, repeatable process) and the **harness**
(the small plumbing the loop needs — a log extension, a review tool, and a fixture
file). The harness is buildable now; the loop runs only once real failures exist.

### 1. The tuning loop (the methodology — the heart of this spec)

```
        ┌─────────────────────────────────────────────────────────────┐
        │  (real war-room traffic — DATA-GATED, depends on adoption)    │
        └───────────────────────────┬─────────────────────────────────┘
                                     ▼
   ① COLLECT   read <profile>/local/war_room/gate.log (hash-only, 0600).
               Each line = one gate decision + classifier verdict + features.
                                     ▼
   ② LABEL     operator reviews flagged lines and marks each as:
               • correct  • false-positive (chatter mis-gated)
               • false-negative (claim mis-classified as chatter / passed unverified)
               Labeling needs the ORIGINAL text, which the log does NOT store →
               the operator supplies it out-of-band (they were in the room).
                                     ▼
   ③ FIXTURE   each confirmed failure becomes a labeled fixture row:
               (text, expected is_claim bool, why) appended to a fixtures file.
                                     ▼
   ④ TEST      add/extend a regression test in test_classify.py that asserts the
               desired is_claim() for that fixture. Run it → it FAILS (red).
                                     ▼
   ⑤ TUNE      change wg_classify.py the MINIMUM needed to go green:
               • FP (ack mis-gated)  → add the EXACT token to _CHATTER.
               • FN (claim passed)   → tighten a too-broad chatter/question rule.
                                       NEVER add a length short-circuit.
                                     ▼
   ⑥ VERIFY    run the FULL suite (template -q). No prior test may regress.
               Re-run the no-length-heuristic guard. One commit per failure case.
                                     └────────────► back to ① on next traffic batch
```

Each pass is intentionally tiny: one failure case, one fixture, one test, one minimal
edit, one commit. This is the same surface-don't-patch, TDD discipline the whole AWR
build used.

### 2. Audit-log extension (harness — buildable now, `wg_audit.py` + `wg_gate.py`)

Extend the log line with three things, all derivable without storing the body:

- **`verdict=claim|chatter`** — the classifier's `is_claim` boolean, recorded for
  *every* message (so chatter is no longer invisible). This is distinct from the gate
  `action`.
- **A stable, longer text hash** — widen the digest from 8 hex chars to a full
  `sha256` hex (or a salted HMAC; see Open Decision in Security). Still hash-only, but
  long enough to deduplicate and to join a log line to an operator-confirmed sample.
- **Minimal, non-reconstructing features** — a tiny, bounded set that helps labeling
  without revealing content: `len` bucketed (`xs|s|m|l`, not exact char count),
  `ends_q` (ends with `?`), `multiline` (contains `\n`), and `matched=<token>|none`
  (which `_CHATTER` token matched, if any). These are categorical and cannot
  reconstruct the message.

The **chatter branch must also log** (`wg_gate.py:49-51` gains a `wg_audit.log(...,
"chatter", ...)` call) so the log finally captures the FN-relevant decisions. The
empty-body and claim branches already log; they gain the new fields.

Example extended line (hash-only, no body, no secret):
```
2026-06-09T18:22:01+00:00 verdict=chatter action=pass reason=chatter conf=- kind=chatter len=xs ends_q=0 multiline=0 matched=thanks sha256=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

> **Open Decision — extend the log, or add a separate sampling sink?** Options: (a)
> extend `gate.log` in place (one richer line per decision); (b) leave `gate.log`
> untouched and write a parallel `classify_samples.log` only when a sampling flag is
> set. **Recommendation: (a) extend `gate.log` in place.** It is already the
> per-decision audit record, already 0600, already best-effort; one log is simpler,
> avoids a second file's permissions/rotation story, and the new fields are cheap.
> The format change is additive (new `key=value` tokens) and the parser tolerates old
> lines (missing keys default). Keep the per-decision log small; rely on the operator
> to export/rotate if volume grows (see Reliability).

### 3. Failure-review tool (harness — buildable now, new `template/scripts/`)

A tiny stdlib CLI, `template/scripts/gate_review.py`, that:

- reads `gate.log`, parses the `key=value` lines, and prints a review table grouped by
  `verdict` / `action` / `matched` so the operator can spot anomalies (e.g. lots of
  `verdict=claim action=abstain` on what they remember were acks → over-gating; or
  a known-claim message that they remember never being gated → under-gating);
- lets the operator append a confirmed failure to the fixtures file by supplying the
  *original text* + the *expected* verdict (the tool re-hashes the supplied text and
  can confirm it matches a log line's `sha256`, proving the operator is labeling the
  right message — without the log ever having stored that text);
- is read-mostly: it never edits `wg_classify.py` and never posts anywhere.

> **Open Decision — how failures get labeled: operator-marks-a-log-line vs. a review
> tool.** Marking a `gate.log` line in place (e.g. appending a `# FP`/`# FN`
> annotation) is tempting but bad: the log is append-only, 0600, and hash-only, and we
> never want the operator pasting the original (possibly secret) text *into* the log.
> **Recommendation: the review tool (`gate_review.py`).** It reads the log, the
> operator supplies the original text transiently at the terminal (it is never
> written to the log), the tool verifies the hash matches, and it writes only the
> labeled fixture (which the operator has judged safe to commit — see Security on
> fixture sanitization). The log stays a pure, untouched audit trail.

### 4. Regression fixtures + test wiring (harness — buildable now, `template/tests/`)

- Confirmed failures live as data, not as ad-hoc test code, in a fixtures file the
  test imports. Each row: `(text, expected_is_claim, note)`.
- `test_classify.py` gains a parametrized test that asserts `is_claim(text) ==
  expected` for every fixture row, so adding a regression is appending one row.
- The existing five hand-written tests stay as the canonical baseline (they encode the
  hard constraints: terse declarative → claim, pure question → chatter, emoji-only →
  chatter, empty → chatter). They never get deleted by tuning.

> **Open Decision — where labeled-failure fixtures live + how they feed
> `test_classify.py`.** Options: (a) a Python module `template/tests/fixtures/
> classifier_cases.py` exporting `CASES: list[tuple[str, bool, str]]`; (b) a JSON
> file `template/tests/fixtures/classifier_cases.json` loaded by the test; (c) inline
> in `test_classify.py`. **Recommendation: (b) a JSON fixtures file** under
> `template/tests/fixtures/`, loaded by a parametrized test. JSON keeps the data
> declarative and language-agnostic (the review tool appends to it without importing
> test code or risking executable-fixture mistakes), is trivially diffable in PRs, and
> runs through the existing `sanitize_check.py` scan like any other committed file.
> The fixture text is operator-curated and must be sanitized before commit (Security).

### 5. The no-length-heuristic guard (harness — buildable now, `template/tests/`)

A standing guard test that fails if anyone reintroduces a length short-circuit. Two
complementary checks (an *intent* check is more robust than a source grep):

- **Behavioral:** assert that a battery of *terse declaratives* of increasing brevity
  all classify as claims — e.g. `"it's down"`, `"db is corrupted"`, `"prod broke"`,
  `"oom"`, `"503s"` — and that a *long* obvious chatter string (a 250-char "thanks so
  much everyone, really appreciate the help …") still classifies as chatter. This
  encodes the rule directly: classification must not correlate with length.
- **Source-level (belt-and-suspenders):** a test that reads `wg_classify.py` source
  and asserts no `len(` comparison gates the claim/chatter decision (allowing the
  existing `len(t) < 200` *inside* the pure-question rule, which bounds a question, not
  a claim — pin it exactly so a new length test trips the guard).

## Data model & config

**Extended `gate.log` line** (`<profile>/local/war_room/gate.log`, dir `0700`, file
`0600`). Whitespace-delimited `key=value`; parser tolerates missing keys (old lines):

| field | today | after extension | notes |
|---|---|---|---|
| timestamp | ✓ | ✓ | ISO-8601 UTC, seconds |
| `verdict` | — | **new** | `claim`\|`chatter` — the `is_claim` result, every message |
| `action` | ✓ | ✓ | `pass`\|`abstain` (gate policy) |
| `reason` | ✓ | ✓ | chatter\|ok\|no-envelope\|ungrounded\|below-threshold\|empty-body\|internal-error |
| `conf` | ✓ | ✓ | envelope confidence or `-` |
| `kind` | ✓ | ✓ | caller label (claim\|chatter\|empty-body) |
| `len` | — | **new** | bucket `xs`\|`s`\|`m`\|`l` (NOT exact count) |
| `ends_q` | — | **new** | `0`\|`1` |
| `multiline` | — | **new** | `0`\|`1` |
| `matched` | — | **new** | matched `_CHATTER` token, or `none` |
| `sha` → `sha256` | 8 hex | **full hex** | hash-only; long enough to join/dedup |

**Fixtures file** (`template/tests/fixtures/classifier_cases.json`):
```jsonc
[
  // each row is one confirmed real-traffic failure, sanitized for public commit
  { "text": "rolling back the deploy now",
    "expected_is_claim": true,
    "note": "FN: was passing as chatter; an action statement is a claim" },
  { "text": "ty all",
    "expected_is_claim": false,
    "note": "FP: 'ty all' got gated; add exact token 'ty all' to _CHATTER" }
]
```

**No config changes.** Tuning needs no new `config.yaml` / `.env` keys. The log
extension is unconditional (it already runs on every gated decision). If a sampling
toggle is ever wanted, it would be a `war_room.gate_log_features: true|false` managed
key — deferred; see Open questions.

## Reliability — failure modes

- **Logging must never fail the gate.** The extension stays inside `wg_audit.log`'s
  existing best-effort `try/except` (`wg_audit.py:36-37`). New feature computation
  (bucketing, `ends_q`) is trivial and total; it still runs under the swallow-all.
- **Log growth.** A busy room appends one line per message. Lines are tiny and the
  file is 0600 + local. **Recommendation:** document an operator-run export/rotate
  step in the tuning runbook rather than building in-process rotation (keeps the
  plugin stdlib-simple and side-effect-light). Open question on automatic rotation.
- **Stale fixtures.** A fixture might encode a case the classifier already handles
  after an unrelated change. That's fine — the parametrized test simply stays green;
  fixtures are cumulative regression armor, not a to-do list.
- **Over-correction (the real risk).** The pressure when an ack gets gated is to make
  chatter detection "smarter" (fuzzy/substring/length). That *will* introduce false
  negatives — the dangerous direction. The guard test (§5) and the exact-match-only
  rule (Core decision 1–2) are the firebreak. Every tuning PR must show the full suite
  green *and* the guard green.
- **Empty traffic / never deployed.** The loop simply never runs. The harness sits
  inert and tested; no failure case is invented. This is expected (Status: DATA-GATED).
- **Operator mislabels a case.** Mitigated by the review tool's hash-match check (the
  tool confirms the supplied text hashes to the log line being labeled) and by code
  review of the fixture PR (a human re-reads each `(text, expected)` row).

## Security

- **The log hashes text — keep it that way.** The single most important security
  property: `gate.log` stores a `sha256` of the body and **never the body**
  (`wg_audit.py:18`). The extension *widens* the hash and adds *categorical* features
  (length bucket, ends-with-`?`, matched token) — none of which reconstruct content.
  **Do NOT start storing raw message bodies, ever**, in the log or anywhere the plugin
  writes.
- **Features must not leak.** `len` is bucketed, not exact, so it cannot fingerprint a
  known message by length. `matched=<token>` only ever names a token already public in
  `_CHATTER` source. `ends_q`/`multiline` are single bits.
- **The original text lives only in the operator's head and terminal.** During
  labeling the operator types the original text into the review tool transiently to
  hash-match it; the tool never writes that text to the log. The only place real text
  becomes durable is the **fixtures file**, which the operator has explicitly judged
  safe and which goes through the public-repo sanitization gate before commit.
- **Fixtures are public-repo content.** They run through `template/scripts/
  sanitize_check.py` and the employer-leak grep like any committed file. The operator
  must scrub real names/tokens/PII from a fixture's `text` before committing — a
  redacted-but-representative sample is the goal (e.g. replace a real service name with
  `api/pay.py`). No secrets, no employer strings, no real handles in fixtures.
- File perms unchanged: dir 0700, file 0600.

> **Open Decision — plain `sha256` vs. salted HMAC for the widened hash.** A plain
> `sha256` of short, low-entropy chatter ("ok", "thanks") is trivially reversible by
> dictionary — but those exact strings are *already public* in `_CHATTER`, so there's
> nothing to protect. For substantive claims the body has enough entropy that a plain
> sha is fine for join/dedup. **Recommendation: plain `sha256` (stdlib `hashlib`), no
> per-profile salt.** A salt would only matter if we feared an attacker brute-forcing
> claim bodies from the log, but the log is already 0600/local and we never need to
> *reverse* the hash — only to *match* an operator-supplied original. Keep it simple;
> revisit only if the threat model changes.

## Observability

The point of the harness is to *make the classifier observable*, so metrics are
first-class:

- **Gate-decision distribution.** From `gate.log`: counts of
  `verdict=claim`/`verdict=chatter` and, within claims, `action=pass`/`abstain` and
  the `reason` breakdown. `gate_review.py` prints these. A healthy room is mostly
  `verdict=chatter pass` + `verdict=claim pass`, with abstains correlating to genuinely
  ungrounded/low-confidence claims — not to acks.
- **FP rate (over-gating):** `confirmed false positives / total chatter messages`.
  Measured by the operator confirming, from review, how many `verdict=claim` lines
  were actually chatter. Lower is better; FPs are *noise*, tolerable in moderation.
- **FN rate (under-gating):** `confirmed false negatives / total claim messages`.
  Measured by the operator confirming how many `verdict=chatter` lines were actually
  ungrounded claims that should have been gated. FNs are the *dangerous* error; target
  is near-zero.

> **Open Decision — acceptable FP/FN targets + how measured.** There is no ground
> truth without operator labeling, so any "rate" is over the *reviewed* sample, not all
> traffic. **Recommendation:** treat the two errors asymmetrically, consistent with the
> default-to-gate bias — set an explicit *FN ceiling near zero* (every confirmed FN is
> a release-blocking regression case that gets a fixture immediately) and a *soft FP
> budget* (e.g. tolerate up to ~5% over-gating of reviewed chatter before adding tokens
> to `_CHATTER`, to avoid chasing every one-off ack into the set and risking
> over-correction). Measure both as fractions of the operator-reviewed sample per
> traffic batch, recorded in the tuning runbook, not as automated production gauges.
> These numbers are starting points to revise once real volume exists.

## Test strategy

- **Regression-per-failure (the core workflow):** every confirmed real failure becomes
  one fixture row in `classifier_cases.json` and is asserted by the parametrized test
  in `test_classify.py`. Adding a regression = appending a row. Red-before-green is
  mandatory (the test must fail against the *unchanged* classifier first, proving it
  reproduces the failure).
- **The five baseline tests stay** (`test_classify.py` today) — they pin the hard
  constraints and must never regress: terse declarative → claim, pure question →
  chatter, substantive assertion → claim, chatter set → chatter, empty → chatter.
- **No-length-heuristic guard** (§Architecture 5): behavioral (terse-short →
  claim *and* long-chatter → chatter) + a source-level check that no `len(` comparison
  gates the claim decision (pinning the one allowed `len(t) < 200` inside the question
  rule). This guard is the single most important new test.
- **Log-extension tests** (`test_audit.py` extensions): assert the new
  `verdict`/`len`/`ends_q`/`multiline`/`matched`/`sha256` fields are present and
  correct; assert **no body and no secret** appears (extend the existing
  `test_log_appends_no_secret_text`); assert the chatter branch now logs
  (`wg_gate.py`); assert old-format lines still parse (back-compat); assert file stays
  0600 and logging never raises.
- **Review-tool tests** (`test_gate_review.py`, new): parse a synthetic log; the
  hash-match confirmation accepts the right original and rejects a wrong one; appending
  a fixture writes valid JSON and never writes the original text into the log.
- **Whole-suite green per tuning commit.** `template/.venv/bin/python -m pytest
  template -q` must pass after every tuning change.

## File-path map (complete)

**Harness — buildable now (not data-gated):**
- `template/plugins/warroom-gate/wg_audit.py` — extend `log(...)` with `verdict`,
  bucketed `len`, `ends_q`, `multiline`, `matched`, and the widened `sha256`; keep the
  best-effort swallow + 0600.
- `template/plugins/warroom-gate/wg_gate.py` — call `wg_audit.log(..., "chatter", ...)`
  on the chatter branch (`:49-51`) so chatter decisions are recorded; pass the
  classifier `verdict` + features into `log`. (No behavior change to the gate output.)
- `template/scripts/gate_review.py` — **new** stdlib CLI: parse `gate.log`, print the
  decision-distribution table, hash-match an operator-supplied original, append a
  confirmed fixture row.
- `template/tests/fixtures/classifier_cases.json` — **new** labeled-failure fixtures
  (starts empty/with the existing baseline encoded; grows one row per real failure).
- `template/tests/test_classify.py` — add the parametrized test over
  `classifier_cases.json`; add the **no-length-heuristic guard** (behavioral +
  source-level). Keep the five baseline tests.
- `template/tests/test_audit.py` — extend for the new log fields + back-compat + the
  no-secret assertion on the richer line.
- `template/tests/test_gate_review.py` — **new** tests for the review tool.
- `docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md` — **new**
  operator runbook documenting the six-step loop, the review-tool commands, the
  rotation/export step, and the FP/FN targets. (Or co-locate as a section in
  `template/README.md` — see Open questions.)

**Touched by the data-gated tuning (edited only when real failures arrive):**
- `template/plugins/warroom-gate/wg_classify.py` — `_CHATTER` set + structural rules,
  edited minimally per confirmed failure. **Never** a length short-circuit.

**Read-only references (not modified):**
- `docs/superpowers/specs/2026-06-05-war-room-confidence-gate-design.md` — the
  classification section + "tune with real traffic" note this spec operationalizes.
- `template/plugins/warroom-gate/wg_policy.py` — `Decision` shape consumed by the log.
- `template/scripts/sanitize_check.py` — the public-repo sanitization gate fixtures
  must pass.

## Build order (phasing — NOT omission; everything above is in scope)

**Doable NOW (no real traffic needed — this is the harness + process):**

1. **Phase 0 — guard first.** Add the no-length-heuristic guard test + lock the five
   baseline tests. This is the firebreak; land it before any tuning ever happens so
   the constraint is enforced by CI from day one.
2. **Phase 1 — log extension.** Extend `wg_audit.py` (verdict, features, full sha256),
   log the chatter branch in `wg_gate.py`, add `test_audit.py` coverage + back-compat.
   After this, a deployed war room *starts collecting* tunable data.
3. **Phase 2 — review tooling + fixtures plumbing.** Add `gate_review.py`,
   `classifier_cases.json` (empty/baseline), the parametrized test, and
   `test_gate_review.py`. Write the operator runbook.

After Phases 0–2, the system is *ready to tune the moment failures exist* — but
produces no classifier changes on its own.

**DATA-GATED ▶ (cannot start until real adoption produces failure data — depends on
the AWR install being deployed and used; see wrap-handoff §2 first-adoption and §9):**

4. **Phase 3 — the tuning loop, run per traffic batch.** For each confirmed
   FP/FN: append fixture → red regression test → minimal `wg_classify.py` edit → full
   suite green → one commit. Repeat as traffic accrues. This phase **never starts in a
   vacuum**; it is invalid to invent failure cases to "exercise" it.

## Out of scope (this spec)

- **Changing the gate's *policy*** (thresholds, abstain rendering, envelope parsing) —
  that is the confidence-gate spec / the DEFCON-severity spec, not classifier tuning.
- **A learned / statistical / model-based classifier** — would break stdlib-only and
  the auditable default-to-gate bias; a separate spec if ever justified (Core
  decision §6 Open Decision).
- **Severity-aware classification** (inferring `[ALERT1]` etc.) — lives in the
  DEFCON/severity sub-project.
- **Multi-board / federation concerns** — independent; this spec is per-profile.
- **Automatic, production telemetry dashboards** — metrics here are operator-reviewed
  per batch from a local 0600 log, not a streamed metrics pipeline.
- **Storing raw message bodies anywhere** — explicitly forbidden (Security).
- **Inventing failure cases before real traffic** — Phase 3 is data-gated.

## Open questions

1. **Runbook location** — standalone `docs/superpowers/runbooks/…` vs. a section in
   `template/README.md`. (Recommend standalone runbook; it's an operator procedure, not
   distribution-install docs, and keeps the README lean.)
2. **Log rotation** — operator-run export/truncate (recommended, keeps the plugin
   side-effect-light) vs. in-process size-capped rotation. Decide once real volume is
   observed; default to manual.
3. **Optional feature-logging toggle** — should the new features always log, or sit
   behind a `war_room.gate_log_features` managed key for the privacy-cautious? (Recommend
   always-on: the features are categorical and non-reconstructing, and an off-by-default
   toggle would mean no tunable data by default — defeating the purpose. Revisit only
   if an adopter raises a concern.)
4. **Batch cadence** — how often the operator runs the review loop (per incident? weekly?).
   Data-dependent; defer to the runbook once adoption cadence is known.
5. **Cross-profile fixture sharing** — if multiple deployments find the same failure,
   do fixtures merge upstream into the template's baseline `classifier_cases.json`?
   (Recommend yes — a confirmed, sanitized failure is a gift to every adopter — but
   gate on the sanitization review.)
