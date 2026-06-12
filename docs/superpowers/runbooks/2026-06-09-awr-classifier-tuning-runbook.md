# Operator Runbook — Real-Traffic Classifier Tuning

- **Date:** 2026-06-09
- **Applies to:** the claim-vs-chatter classifier in `template/plugins/warroom-gate/wg_classify.py`.
- **Status:** the harness is built and tested; this loop runs **only once real
  war-room traffic produces failures** (DATA-GATED). Do not invent failure cases.

This is the operator procedure for the six-step tuning loop. The harness (the
`gate.log` extension, `gate_review.py`, `classifier_cases.json`, the parametrized
regression test, and the no-length-heuristic guard) is already in place. You run
this loop per traffic batch.

## The hard rules (never re-litigate)

1. **NEVER add a length-based heuristic.** Terse declaratives ("it's down",
   "db is corrupted", "oom") MUST gate. The fix for "an ack got gated" is to add
   the EXACT token to `_CHATTER` in `wg_classify.py`, never a length short-circuit.
2. **Default-to-gate bias is preserved.** When unsure, classify as a claim.
   Every new `_CHATTER` entry is an exact, unambiguous ack/greeting/closed token —
   never a substring or fuzzy match.
3. **One failure -> one fixture -> one red test -> one minimal edit -> one commit.**
4. **The log is hash-only.** Never paste an original message body into `gate.log`,
   and never store raw bodies anywhere the plugin writes.

## The six-step loop

### 1. COLLECT
Read the per-profile audit log (mode 0600, local, hash-only):

    template/.venv/bin/python template/scripts/gate_review.py review --log <profile>/local/war_room/gate.log

This prints the decision distribution grouped by `verdict`, `action`, `reason`,
and `matched`. A healthy room is mostly `verdict=chatter` (pass) + `verdict=claim`
(pass), with abstains correlating to genuinely ungrounded/low-confidence claims.
Anomalies:
- lots of `verdict=claim action=abstain` on messages you remember were acks ->
  candidate **false positives** (over-gating);
- a known ungrounded claim you remember was never gated, recorded as a
  `verdict=chatter` line -> candidate **false negative** (under-gating).

### 2. LABEL
The log never stores the body — only a `sha256`. To label a line you supply the
ORIGINAL text on stdin (you were in the room). The tool re-hashes it and confirms
it matches the log line's `sha256` before writing anything:

    printf '%s' 'the exact original message' | \
      template/.venv/bin/python template/scripts/gate_review.py label --log <profile>/local/war_room/gate.log \
        --sha256 <the sha256 from the log line> \
        --expected claim|chatter \
        --note 'FP/FN: why this is wrong' \
        --fixtures template/tests/fixtures/classifier_cases.json

- `--expected claim` for a false negative (it should have gated).
- `--expected chatter` for a false positive (it should not have gated).
- A `sha256` mismatch aborts (exit 3) — the text you supplied does not hash to
  the `--sha256` you passed; you are labeling the wrong message.
- A `sha256` that no `gate.log` line carries aborts (exit 4) — the text hashes to
  `--sha256` but was never actually gated (or you are reading the wrong log).
- The original text is NEVER written to the log; it goes only into the fixtures
  file, which you must SANITIZE before commit (below).

### 3. FIXTURE
The `label` command appended one row to
`template/tests/fixtures/classifier_cases.json`:

    { "text": "...", "expected_is_claim": true|false, "note": "..." }

**Sanitize it before committing.** Fixtures are public-repo content. The
`test_classifier_fixtures_sanitize.py` guard scans them in CI; scrub real
names/tokens/PII from `text` — a redacted-but-representative sample is the goal
(e.g. replace a real service name with `api/pay.py`). No secrets, no employer
strings, no real handles.

### 4. TEST
The parametrized test in `template/tests/test_classify.py` asserts
`is_claim(text) == expected_is_claim` for every fixture row. Run it; the new row
must FAIL first (red), proving it reproduces the failure against the unchanged
classifier:

    template/.venv/bin/python -m pytest template/tests/test_classify.py -q

### 5. TUNE
Change `wg_classify.py` the MINIMUM needed to go green:
- **False positive (ack mis-gated)** -> add the EXACT lowercased token to
  `_CHATTER`. Nothing else.
- **False negative (claim passed as chatter)** -> tighten a too-broad chatter or
  question rule. NEVER add a length short-circuit.

### 6. VERIFY
Run the whole suite and the guard:

    template/.venv/bin/python -m pytest template -q
    template/.venv/bin/python -m pytest template/tests/test_classify_guard.py -q
    python3 template/scripts/sanitize_check.py template/

No prior test may regress. Then commit one failure case:

    git add template/tests/fixtures/classifier_cases.json template/plugins/warroom-gate/wg_classify.py
    git commit -m "AWR classifier-tuning: <one-line why> (<batch tag>)"

Loop back to step 1 on the next traffic batch.

## FP/FN targets

There is no ground truth without operator labeling, so any "rate" is over the
REVIEWED sample, not all traffic. Treat the two errors asymmetrically:
- **False-negative ceiling: near zero.** Every confirmed false negative is a
  release-blocking regression case that gets a fixture immediately. FNs (a real
  ungrounded claim passing unverified) are the dangerous error the gate exists to
  stop.
- **False-positive budget: soft, ~5%.** Tolerate up to roughly 5% over-gating of
  the reviewed chatter sample before adding tokens to `_CHATTER`, to avoid
  chasing every one-off ack into the set and risking over-correction (which
  introduces FNs). False positives are noise — tolerable in moderation.

Record both as fractions of the operator-reviewed sample per traffic batch in
this runbook's batch log (append a dated section per batch). These are starting
points to revise once real volume exists.

## Cross-profile fixture sharing

A confirmed, sanitized failure is a gift to every adopter: a fixture found on one
deployment may merge upstream into the template's baseline
`classifier_cases.json`, gated on the same sanitization review as any committed
file. Open a PR with the new row(s) and the matching minimal `wg_classify.py` edit.

## Log rotation / export

`gate.log` grows one tiny line per message. There is no in-process rotation
(keeps the plugin side-effect-light). When the file grows large, the operator
exports and truncates it manually:

    cp <profile>/local/war_room/gate.log <profile>/local/war_room/gate.log.$(date +%Y%m%d)
    : > <profile>/local/war_room/gate.log    # truncate in place, keep 0600

Review batches against the archived copies; the live log stays small.
