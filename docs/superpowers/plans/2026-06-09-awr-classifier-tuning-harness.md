# Real-Traffic Classifier Tuning Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the harness (no-length-heuristic guard, hash-only `gate.log` extension with a per-message classifier verdict + categorical features, a stdlib failure-review CLI, JSON regression fixtures, and an operator runbook) so the claim-vs-chatter classifier can be tuned the moment real traffic produces failures — without inventing failure cases and without editing `wg_classify.py`'s rules.

**Architecture:** Two halves. The *harness* (this plan, build-order Phases 0–2): a standing guard test that bans length short-circuits; an additive `wg_audit.log` line extension (`verdict`, bucketed `len`, `ends_q`, `multiline`, `matched`, full `sha256`) plus a chatter-branch log call in `wg_gate.py` so under-gating becomes visible; a read-mostly `gate_review.py` CLI; an (empty) `classifier_cases.json` fixtures file with a parametrized test; and a runbook. The *tuning loop* (Phase 3) is DATA-GATED and explicitly out of this plan: `wg_classify.py`'s rules are read-only here.

**Tech Stack:** Python 3.9+, stdlib only (`hashlib`, `argparse`, `json`, `pathlib`, `collections`); pytest; the existing war-room gate plugin (`template/plugins/warroom-gate/`); additive log format; atomic-write discipline (temp + `os.replace`, mirroring `setup._atomic_write_text`) for the one state write the review tool performs.

**Spec:** `docs/superpowers/specs/2026-06-09-awr-classifier-tuning-design.md`. All commands below run from the repo root (`/Users/aahil/Documents/Code/agentic-war-room`).

## Adopted decisions

- **Open Decision (Core §6) — what the classifier may grow into:** keep `is_claim` a pure, rule-based, exact-match function indefinitely; never a learned/statistical classifier. This plan adds NO statistical machinery and does not edit the rules.
- **Open Decision (Architecture §2) — extend the log vs. a separate sampling sink:** (a) extend `gate.log` in place with additive `key=value` tokens; the parser tolerates old lines (missing keys default). No second file, no sampling flag.
- **Open Decision (Architecture §3) — how failures get labeled:** the review tool (`gate_review.py`); the operator supplies the original text transiently at the terminal, the tool hash-matches it against a log line's `sha256`, and writes only the labeled fixture row. The log is never annotated in place.
- **Open Decision (Architecture §4) — where labeled-failure fixtures live:** (b) a JSON file `template/tests/fixtures/classifier_cases.json` loaded by a parametrized test in `test_classify.py`.
- **Open Decision (Security) — plain `sha256` vs. salted HMAC:** plain `sha256` (stdlib `hashlib`), no per-profile salt. The log is 0600/local and we only ever *match* an operator-supplied original, never reverse the hash.
- **Open Decision (Observability) — FP/FN targets:** asymmetric — an explicit FN ceiling near zero (every confirmed FN is a release-blocking fixture) and a soft FP budget (~5% over-gating of the reviewed chatter sample) before adding `_CHATTER` tokens. Recorded in the runbook as operator-reviewed per-batch fractions, not automated gauges.
- **Open question 1 — runbook location:** standalone `docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md` (the runbooks dir does not exist yet; this plan creates it via `git add`).
- **Open question 2 — log rotation:** operator-run export/truncate, documented in the runbook; no in-process rotation.
- **Open question 3 — optional feature-logging toggle:** always-on; the features are categorical and non-reconstructing. No `war_room.gate_log_features` key is added; no `config.yaml`/`.env` change.
- **Open question 4 — batch cadence:** deferred to the runbook; start per-incident, revise once real volume exists.
- **Open question 5 — cross-profile fixture sharing:** yes — confirmed, sanitized failures may merge upstream into the template's baseline `classifier_cases.json`, gated on sanitization review; the runbook documents the path.
- **Seed rows (per-project brief — decided per spec):** `classifier_cases.json` ships **empty** (`[]`). The spec sanctions "starts empty/with the existing baseline encoded"; empty is chosen because the fixtures file is semantically *real-traffic failures only* (Architecture §4: "each row is one confirmed real-traffic failure"), and the five baseline behaviors are already pinned by the existing hand-written tests in `test_classify.py` plus Task 1's guard. Encoding the baseline into the fixtures would blur that line and risk duplicating constraints. The empty-parametrize-collects-nothing concern is covered by a separate always-running `test_classifier_cases_file_is_valid_list` (Task 6). Phase 3 (data-gated) is the only thing that appends rows.

## Deviations

- **Spec "Current state" drift on the empty-body branch.** The spec (lines 106, 119, 203, and the data-model `kind` column) asserts an `empty-body` branch in `wg_gate.gate()` that calls `wg_audit.log(..., "empty-body", ...)`. Verified against live source (`template/plugins/warroom-gate/wg_gate.py`, 67 lines, 2026-06-09): there is **exactly one** `wg_audit.log` call site — the claim branch at line 49 — and **no** empty-body branch anywhere in the repo (`git grep empty-body` → empty; empty/whitespace input returns `None` at line 33 before any logging). The deferred wrap-handoff §4 minor #3 (empty-body abstention) never landed. This plan wires the chatter-branch log call (new) and extends the single existing claim-branch call; it does NOT assume an empty-body branch. The `kind` field keeps `claim`|`chatter` as the two values this plan actually emits.
- **Spec §Architecture-5 long-chatter guard restated to match live behavior.** The spec expects a 250-char "thanks so much everyone …" string to classify as *chatter*. Verified by executing the live classifier (length 285 → `is_claim` returns **True/claim**): `is_claim` default-to-gates ANY text that is not an exact `_CHATTER` token, not strip-to-empty, and not a short pure question — regardless of length. That is correct, deliberate behavior (a false-positive/over-gate is the safe direction). Task 1's behavioral guard therefore asserts the inverse the rule actually guarantees: length never SHORT-CIRCUITS a long message to chatter (the long thanks correctly stays a claim), while terse declaratives of increasing brevity all gate. This is the firebreak the spec wants, phrased so it matches what the classifier really does.
- **`sanitize_check.py` excludes `tests/`.** Verified: `sanitize_check.EXCLUDE_DIRS` contains `"tests"` (`template/scripts/sanitize_check.py:30`), so `classifier_cases.json` (under `template/tests/fixtures/`) is NOT reached by the default `python3 template/scripts/sanitize_check.py template/` scan. To honor the spec's "fixtures run through the sanitization gate" intent, Task 6 adds a dedicated test that invokes `sanitize_check.scan` **directly on the fixtures file's directory** so any future operator-added row carrying a leaked shape/name is caught in CI. This strengthens, not contradicts, the adopted decision.

## Verified source facts (live, 2026-06-09 — spec line numbers had drifted)

- `template/plugins/warroom-gate/wg_classify.py` (31 lines): `_CHATTER` at `:7-11` (22 exact tokens); `is_claim(text)` at `:14-31`; normalization `low = t.lower().strip(" .!👍✅")` at `:19`; pure-question rule at `:26` — the **only** `len(` in the module: `if t.endswith("?") and "\n" not in t and len(t) < 200 and "." not in t.rstrip("?"):`; no-length-exemption NOTE at `:28-30`; default-to-gate `return True` at `:31`. **Read-only for this entire plan except the appended `matched_chatter` helper.**
- `template/plugins/warroom-gate/wg_gate.py` (67 lines): classify call at `:40` (`claim = wg_classify.is_claim(body if env is not None else response_text)`); chatter branch at `:42-44` — does **NOT** log; the single `wg_audit.log(root, decision, conf, "claim", response_text)` call at `:49` (claim branch). `wg_audit` and `wg_policy` both imported at the top.
- `template/plugins/warroom-gate/wg_audit.py` (37 lines): `log(profile_root, decision, conf, kind, text)`; 8-char `sha = sha256(text)[:8]` at `:18`; line format at `:21-22`; dir 0700 / file 0600; best-effort `except Exception: return` at `:36-37`.
- `template/plugins/warroom-gate/wg_policy.py`: `Decision(action, reason, missing="")`; `decide(is_claim, env, threshold)` — `if not is_claim: return Decision(PASS, "chatter")` at `:20-21` (env/threshold never read on the chatter path — verified by executing `decide(False, None, 0.0)` → `pass`/`chatter`).
- `template/pyproject.toml`: `[tool.pytest.ini_options] pythonpath = [".", "plugins/warroom-gate"]`, `testpaths = ["tests"]` — so `import wg_audit` / `wg_classify` / `wg_gate` resolve and tests live under `template/tests/`.
- `template/scripts/sanitize_check.py`: `scan(root, names=())` returns `(path, lineno, reason, snippet)` tuples; `EXCLUDE_DIRS` includes `"tests"`; loadable via `importlib.util.spec_from_file_location` (pattern in `test_sanitize_check.py`).
- No other module in the tree reads or parses `gate.log` (`grep -rln "gate.log"` → only `wg_audit.py` writes it) — so `gate_review.py` is the first parser; no back-compat consumer to break.

Baselines (verified 2026-06-09 before authoring):
- `template/.venv/bin/python -m pytest template -q` → **409 passed, 10 skipped**. This plan touches only `template/` plus one new doc outside it; the coordination suite is not involved, so no coordination baseline is recorded.
- `python3 template/scripts/sanitize_check.py template/` → **exit 0, clean**.

---

## Phase 0 — guard first (the firebreak)

### Task 1: No-length-heuristic guard test (behavioral + source-level)

The single most important new test. Land it before any log or tuning work so the length-short-circuit constraint is CI-enforced from day one. Behavioral check: terse declaratives of increasing brevity all classify as claims, and a long obvious-chatter string is NOT short-circuited to chatter by its length. Source-level check: the only `len(` comparison in `wg_classify.py` is the one bounding the pure-question rule (`len(t) < 200`), pinned exactly so a newly-introduced length test trips the guard.

Files:
- Create: `template/tests/test_classify_guard.py`
- Test: `template/tests/test_classify_guard.py`

Steps:

- [ ] Write the test. Create `template/tests/test_classify_guard.py`:

```python
"""No-length-heuristic guard for the claim/chatter classifier.

Two complementary checks: a BEHAVIORAL check that classification does not
correlate with length (terse declaratives gate; a long non-token message is NOT
short-circuited to chatter by its length), and a SOURCE-LEVEL check that the only
`len(` comparison in wg_classify.py is the one bounding the pure-question rule.
Reintroducing any length short-circuit on the claim/chatter decision must fail
this test.

See the gate spec (lines 178-182) and the classifier-tuning design (Arch §5):
NEVER route text to chatter because it is short.
"""
import re
from pathlib import Path

import wg_classify as C

SRC = Path(C.__file__)


def test_terse_declaratives_of_increasing_brevity_all_gate():
    # Increasingly terse, but every one is an assertion -> must be a claim.
    for t in ["it's down", "db is corrupted", "prod broke", "oom", "503s"]:
        assert C.is_claim(t) is True, t


def test_length_never_short_circuits_a_long_message_to_chatter():
    # ~285 chars of pure thanks. It is NOT an exact _CHATTER token, so the
    # default-to-gate branch correctly classifies it as a claim. The guard's
    # point is the inverse: a long string is never EXEMPTED to chatter by length.
    # (A genuinely long ack is handled by adding the exact token to _CHATTER
    # during tuning -- never by a length rule.)
    long_thanks = "thanks so much everyone, really appreciate the help here " * 5
    assert len(long_thanks) > 200
    assert C.is_claim(long_thanks) is True


def test_only_len_comparison_is_the_pure_question_bound():
    """Source-level belt-and-suspenders: pin the ONE allowed len( use.

    The pure-question rule bounds a QUESTION's length (len(t) < 200), which is
    not a claim/chatter short-circuit. Any other `len(` comparison in the module
    is a reintroduced length heuristic and must trip this guard.
    """
    src = SRC.read_text(encoding="utf-8")
    len_uses = re.findall(r"len\([^)]*\)", src)
    # Exactly one len( call exists today, inside the pure-question rule.
    assert len_uses == ["len(t)"], len_uses
    assert "len(t) < 200" in src
    # No comparison routes to chatter based on length anywhere else.
    numeric_len_cmp = re.findall(r"len\([^)]*\)\s*[<>]=?\s*\d+", src)
    assert numeric_len_cmp == ["len(t) < 200"], numeric_len_cmp
```

- [ ] Run it (expect PASS — this guard pins already-correct source, so it is green from the start; red-before-green applies to *tuning* fixtures in Phase 3, not to a standing guard):
  `template/.venv/bin/python -m pytest template/tests/test_classify_guard.py -q`
  Expected: `3 passed`.

- [ ] Confirm the source-level guard actually bites (prove the regex discriminates against an injected short-circuit WITHOUT modifying the real file):
  `template/.venv/bin/python - <<'PY'
import re, pathlib
src = pathlib.Path("template/plugins/warroom-gate/wg_classify.py").read_text()
mutated = src.replace("    if not t:", "    if len(t) < 4:\n        return False\n    if not t:")
numeric = re.findall(r"len\([^)]*\)\s*[<>]=?\s*\d+", mutated)
print("MUTATED numeric len-compares:", numeric)
assert numeric != ["len(t) < 200"], "guard would NOT catch the injected short-circuit"
print("guard catches injected length short-circuit: OK")
PY`
  Expected stdout ends with `guard catches injected length short-circuit: OK`.

- [ ] Suite-green checkpoint: `template/.venv/bin/python -m pytest template -q` → 0 failures, adds 3 tests. Then `python3 template/scripts/sanitize_check.py template/` → exit 0.

- [ ] Commit:
  `git add template/tests/test_classify_guard.py`
  `git commit -m "AWR classifier-tuning: no-length-heuristic guard (behavioral + source-level) (T1)"`

---

## Phase 1 — hash-only log extension

### Task 2: Add the `matched_chatter` read helper to `wg_classify.py`

`matched=<token>|none` needs to know *which* `_CHATTER` token matched, without changing `is_claim`'s frozen `is_claim(text) -> bool` contract (Core decision §6) and without touching the rules. Add a pure helper that re-runs the *exact* same normalization as `is_claim` lines 16–23 and returns the matched token (or `None`). Read-only: classification is byte-unchanged (Task 1's guard still passes).

Files:
- Modify: `template/plugins/warroom-gate/wg_classify.py`
- Test: `template/tests/test_classify_matched.py` (Create)

Steps:

- [ ] Write the failing test. Create `template/tests/test_classify_matched.py`:

```python
"""matched_chatter(): which _CHATTER token a message normalized to (read-only)."""
import wg_classify as C


def test_matched_chatter_returns_exact_token():
    assert C.matched_chatter("thanks") == "thanks"
    assert C.matched_chatter("Thanks!") == "thanks"   # same normalization as is_claim
    assert C.matched_chatter("OK.") == "ok"
    assert C.matched_chatter("ty") == "ty"


def test_matched_chatter_none_for_claims_and_questions():
    assert C.matched_chatter("the db is down") is None
    assert C.matched_chatter("which service owns checkout?") is None
    assert C.matched_chatter("") is None
    assert C.matched_chatter("   ") is None


def test_matched_chatter_emoji_only_normalizes_to_empty_not_a_token():
    # Emoji-only strips to "" (not a _CHATTER member name) -> no matched token,
    # even though is_claim treats it as chatter.
    assert C.matched_chatter("👍") is None
    assert C.is_claim("👍") is False


def test_matched_chatter_does_not_change_classification():
    # The helper is read-only: is_claim must be unaffected.
    for t in ["ok", "it's down", "thanks", "prod broke", "  "]:
        before = C.is_claim(t)
        C.matched_chatter(t)
        assert C.is_claim(t) is before, t
```

- [ ] Run it (expect failure — `matched_chatter` does not exist yet):
  `template/.venv/bin/python -m pytest template/tests/test_classify_matched.py -q`
  Expected: `AttributeError: module 'wg_classify' has no attribute 'matched_chatter'`.

- [ ] Implement. Append to `template/plugins/warroom-gate/wg_classify.py` (after `is_claim`, end of file):

```python


def matched_chatter(text):
    # type: (str) -> object
    """Return the exact _CHATTER token `text` normalizes to, else None.

    Read-only audit helper for gate.log's `matched=` field. Mirrors the EXACT
    normalization is_claim() uses (lower(), strip(" .!👍✅"), _CHATTER membership)
    so a logged token is always a real, public _CHATTER entry. It never changes
    classification -- is_claim() is the sole authority on claim vs chatter.
    """
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower().strip(" .!👍✅")
    if low in _CHATTER:
        return low
    return None
```

- [ ] Run it (expect PASS):
  `template/.venv/bin/python -m pytest template/tests/test_classify_matched.py -q`
  Expected: `4 passed`.

- [ ] Re-run the guard + baseline to prove classification is unchanged:
  `template/.venv/bin/python -m pytest template/tests/test_classify_guard.py template/tests/test_classify.py -q`
  Expected: `0 failures` (3 guard + 5 baseline = 8 tests).

- [ ] Commit:
  `git add template/plugins/warroom-gate/wg_classify.py template/tests/test_classify_matched.py`
  `git commit -m "AWR classifier-tuning: matched_chatter read helper (no rule change) (T2)"`

### Task 3: Extend `wg_audit.log` with verdict + features + full sha256 (back-compat)

Extend the single log writer to emit the additive `key=value` tokens: `verdict`, bucketed `len`, `ends_q`, `multiline`, `matched`, and a full-hex `sha256` (replacing the 8-char `sha`). `verdict` is supplied by the caller (default `None` → omitted, so old call sites stay valid). Features are computed locally from `text`. Stays inside the best-effort `try/except`; file stays 0600. Field order is fixed; **`sha256=` is emitted last** so the DEFCON plan (position 3) can insert `sev=`/`verify=` immediately before it as additive tokens (per the INTERFACE CONTRACT).

> **Spec test-strategy note (back-compat parse).** The spec's log-extension bullet attributes "assert old-format lines still parse (back-compat)" to `test_audit.py`. `wg_audit.py` is a *writer* with nothing to parse, so that assertion lives where the parser does: `test_parse_old_line_tolerated_missing_keys_default` in `test_gate_review.py` (Task 5, `gate_review.parse_line` is the only/first `gate.log` parser — Verified source fact line 42). `test_audit.py` here covers the *writer* back-compat (`test_log_verdict_omitted_when_not_supplied_backcompat`: a caller omitting `verdict` still produces a valid line). Both halves of back-compat are covered; the parse half is intentionally relocated to the parser's test file.

Files:
- Modify: `template/plugins/warroom-gate/wg_audit.py`
- Test: `template/tests/test_audit.py` (Modify)

Steps:

- [ ] Write the failing tests. Append to `template/tests/test_audit.py`:

```python
import hashlib


def test_log_emits_verdict_and_features(tmp_path):
    d = P.Decision(P.PASS, "chatter")
    A.log(tmp_path, d, None, "chatter", "thanks", verdict="chatter")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=chatter" in line
    assert "len=xs" in line           # 6 chars -> xs bucket
    assert "ends_q=0" in line
    assert "multiline=0" in line
    assert "matched=thanks" in line
    full = hashlib.sha256("thanks".encode("utf-8")).hexdigest()
    assert ("sha256=%s" % full) in line
    assert " sha=" not in line        # old 8-char field gone


def test_log_features_for_multiline_question_claim(tmp_path):
    d = P.Decision(P.ABSTAIN, "no-envelope")
    text = "is the db down?\nlooks like it from the metrics"
    A.log(tmp_path, d, 0.9, "claim", text, verdict="claim")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=claim" in line
    assert "multiline=1" in line      # contains a newline
    assert "ends_q=0" in line         # whole text does not END with ?
    assert "matched=none" in line     # not a chatter token
    assert "conf=0.90" in line


def test_log_ends_q_true_for_trailing_question(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "chatter"), None, "chatter",
          "which service owns checkout?", verdict="chatter")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "ends_q=1" in line


def test_log_len_buckets(tmp_path):
    # xs < 16 <= s < 64 <= m < 256 <= l
    cases = [("hi", "len=xs"), ("x" * 20, "len=s"),
             ("y" * 100, "len=m"), ("z" * 400, "len=l")]
    for text, expect in cases:
        root = tmp_path / ("p_%d" % len(text))
        A.log(root, P.Decision(P.PASS, "ok"), None, "claim", text, verdict="claim")
        line = (root / "local" / "war_room" / "gate.log").read_text()
        assert expect in line, (text, line)


def test_log_no_body_or_secret_in_extended_line(tmp_path):
    A.log(tmp_path, P.Decision(P.ABSTAIN, "below-threshold", "a repro"),
          0.6, "claim", "SECRET deploy creds sk-xxx in api/pay.py", verdict="claim")
    text = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "sk-xxx" not in text and "SECRET deploy creds" not in text
    assert "api/pay.py" not in text
    assert "verdict=claim" in text     # features present, body absent


def test_log_verdict_omitted_when_not_supplied_backcompat(tmp_path):
    # Old call sites that don't pass verdict still work (token simply absent).
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=" not in line
    assert "len=xs" in line and "sha256=" in line
    assert "action=pass" in line


def test_log_file_still_0600_with_extension(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body", verdict="claim")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert stat.S_IMODE(os.stat(logf).st_mode) == 0o600


def test_log_never_raises_with_extension_on_bad_root(tmp_path):
    A.log(tmp_path / "nope" / "x", P.Decision(P.PASS, "ok"), None,
          "chatter", "anything", verdict="chatter")
```

- [ ] Run it (expect failure — `verdict` kwarg unknown / new fields absent):
  `template/.venv/bin/python -m pytest template/tests/test_audit.py -q`
  Expected: `TypeError: log() got an unexpected keyword argument 'verdict'` (and field-presence asserts fail).

- [ ] Implement. Replace the entire contents of `template/plugins/warroom-gate/wg_audit.py`:

```python
"""Append-only gate-decision log. Stdlib only, Python >=3.9.

Records the decision plus a per-message classifier verdict and a tiny set of
CATEGORICAL features (length bucket, ends-with-?, multiline, matched chatter
token) and a full sha256 of the text. NEVER the message body and NEVER a secret
(the sha256 is hash-only; the features are non-reconstructing). Best-effort:
logging failures never propagate (the gate must not fail because logging did).

Field order is fixed and additive: timestamp, verdict?, action, reason, conf,
kind, len, ends_q, multiline, matched, sha256. `sha256=` is emitted LAST so new
optional key=value fields slot in immediately before it.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import wg_classify
from wg_policy import Decision


def _len_bucket(text):
    # type: (str) -> str
    n = len(text or "")
    if n < 16:
        return "xs"
    if n < 64:
        return "s"
    if n < 256:
        return "m"
    return "l"


def log(profile_root, decision, conf, kind, text, verdict=None):
    # type: (Path, Decision, Optional[float], str, str, Optional[str]) -> None
    try:
        t = text or ""
        digest = hashlib.sha256(t.encode("utf-8")).hexdigest()
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conf_s = "-" if conf is None else ("%.2f" % conf)
        matched = wg_classify.matched_chatter(t) or "none"
        ends_q = "1" if t.rstrip().endswith("?") else "0"
        multiline = "1" if "\n" in t else "0"
        verdict_tok = "" if verdict is None else ("verdict=%s " % verdict)
        line = (
            "%s %saction=%s reason=%s conf=%s kind=%s "
            "len=%s ends_q=%s multiline=%s matched=%s sha256=%s\n"
        ) % (
            ts, verdict_tok, decision.action, decision.reason, conf_s, kind,
            _len_bucket(t), ends_q, multiline, matched, digest,
        )
        d = Path(profile_root) / "local" / "war_room"
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(d), 0o700)
        except OSError:
            pass
        f = d / "gate.log"
        with open(str(f), "a", encoding="utf-8") as fh:
            fh.write(line)
        try:
            os.chmod(str(f), 0o600)
        except OSError:
            pass
    except Exception:
        return  # logging is best-effort; never raise
```

- [ ] Run it (expect PASS):
  `template/.venv/bin/python -m pytest template/tests/test_audit.py -q`
  Expected: `0 failures` (3 original + 8 new audit tests).

- [ ] Commit:
  `git add template/plugins/warroom-gate/wg_audit.py template/tests/test_audit.py`
  `git commit -m "AWR classifier-tuning: extend gate.log with verdict + categorical features + full sha256 (T3)"`

### Task 4: Log the chatter branch and pass verdict from `wg_gate.py`

The chatter branch (`wg_gate.py:42-44`) currently returns without logging, so under-gating (a real claim mis-classified as chatter) leaves no log line. Add a `wg_audit.log(..., verdict="chatter")` call on that branch, and thread `verdict="claim"` into the existing claim-branch call. No change to what the gate *returns* — only what it records.

Files:
- Modify: `template/plugins/warroom-gate/wg_gate.py`
- Test: `template/tests/test_gate_callback.py` (Modify — add chatter-logs assertions)

Steps:

- [ ] Write the failing tests. Append to `template/tests/test_gate_callback.py`:

```python


def test_chatter_branch_now_logs_verdict_chatter(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # chatter -> gate returns None, but it MUST now write a verdict=chatter line.
    assert wg_gate.gate(response_text="thanks!") is None
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert logf.is_file(), "chatter branch must log so under-gating is visible"
    line = logf.read_text()
    assert "verdict=chatter" in line
    assert "reason=chatter" in line
    assert "matched=thanks" in line


def test_claim_branch_logs_verdict_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    wg_gate.gate(response_text="The fix is api/pay.py:88.\n⟦conf=0.88 grounded=tool,file missing=none⟧")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=claim" in line
    assert "api/pay.py" not in line     # body never logged, only its hash


def test_chatter_log_does_not_change_return_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # A bare ack is unchanged after stray-envelope strip -> still returns None.
    assert wg_gate.gate(response_text="ok") is None
```

- [ ] Run it (expect failure — chatter branch does not log yet):
  `template/.venv/bin/python -m pytest template/tests/test_gate_callback.py -q`
  Expected: `AssertionError: chatter branch must log so under-gating is visible`.

- [ ] Implement. Edit `template/plugins/warroom-gate/wg_gate.py`. The current lines 42-49 are:

```python
        if not claim:
            cleaned = wg_envelope.strip_stray_envelopes(response_text).rstrip()
            return cleaned if cleaned != response_text.rstrip() else None

        threshold = cfg["min_confidence"] / 100.0
        decision = wg_policy.decide(True, env, threshold)
        conf = env.conf if env is not None else None
        wg_audit.log(root, decision, conf, "claim", response_text)
```

  Replace that block with:

```python
        conf = env.conf if env is not None else None
        if not claim:
            # Log the chatter decision (verdict=chatter) so under-gating is no
            # longer invisible. decide(False, ...) returns Decision(PASS,
            # "chatter") without reading env or threshold (wg_policy.py:20-21);
            # constructed directly to avoid a meaningless threshold argument.
            wg_audit.log(root, wg_policy.Decision(wg_policy.PASS, "chatter"),
                         conf, "chatter", response_text, verdict="chatter")
            cleaned = wg_envelope.strip_stray_envelopes(response_text).rstrip()
            return cleaned if cleaned != response_text.rstrip() else None

        threshold = cfg["min_confidence"] / 100.0
        decision = wg_policy.decide(True, env, threshold)
        wg_audit.log(root, decision, conf, "claim", response_text, verdict="claim")
```

  (`wg_policy.Decision` and `wg_policy.PASS` are reachable — `wg_policy` is imported at the top of `wg_gate.py`; `wg_audit` likewise. No import changes. `conf` is hoisted above the branch so both call sites share it.)

- [ ] Run it (expect PASS):
  `template/.venv/bin/python -m pytest template/tests/test_gate_callback.py -q`
  Expected: `0 failures` (8 existing callback tests + 3 new ones = 11).

- [ ] Suite-green checkpoint (end of Phase 1): `template/.venv/bin/python -m pytest template -q` → 0 failures. Then `python3 template/scripts/sanitize_check.py template/` → exit 0. A deployed war room now collects tunable data, chatter included.

- [ ] Commit:
  `git add template/plugins/warroom-gate/wg_gate.py template/tests/test_gate_callback.py`
  `git commit -m "AWR classifier-tuning: log chatter branch + thread verdict into gate.log (T4)"`

---

## Phase 2 — review tooling, fixtures plumbing, runbook

### Task 5: `gate_review.py` — parse the log + print the decision-distribution table

The review CLI's first capability: read `gate.log`, parse the additive `key=value` lines (tolerating old lines with missing keys), and print a distribution table grouped by `verdict` / `action` / `reason` / `matched`. Pure read; never edits `wg_classify.py`, never posts. Importable (a `parse_line` / `read_log` / `summarize` surface) and runnable via `main(argv)`.

Files:
- Create: `template/scripts/gate_review.py`
- Test: `template/tests/test_gate_review.py` (Create)

Steps:

- [ ] Write the failing test. Create `template/tests/test_gate_review.py`:

```python
"""Tests for the stdlib failure-review CLI (gate_review.py): parse + summarize."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "gate_review.py"
    spec = importlib.util.spec_from_file_location("gate_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GR = _load()

OLD_LINE = "2026-06-09T18:22:01+00:00 action=abstain reason=below-threshold conf=0.62 kind=claim sha=1a2b3c4d"
NEW_CHATTER = ("2026-06-09T18:22:02+00:00 verdict=chatter action=pass reason=chatter "
               "conf=- kind=chatter len=xs ends_q=0 multiline=0 matched=thanks "
               "sha256=a6a2729cbf6bcadce577a31f7f76201d5ce63c57d6c53318000d67714bb354ef")
NEW_CLAIM = ("2026-06-09T18:22:03+00:00 verdict=claim action=abstain reason=ungrounded "
             "conf=0.50 kind=claim len=m ends_q=0 multiline=0 matched=none "
             "sha256=2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae")


def test_parse_new_line_extracts_all_fields():
    d = GR.parse_line(NEW_CHATTER)
    assert d["verdict"] == "chatter"
    assert d["action"] == "pass"
    assert d["reason"] == "chatter"
    assert d["matched"] == "thanks"
    assert d["sha256"].startswith("a6a2729c")   # sha256("thanks"), matches matched=thanks
    assert d["len"] == "xs"


def test_parse_old_line_tolerated_missing_keys_default():
    d = GR.parse_line(OLD_LINE)
    assert d["action"] == "abstain"
    assert d["reason"] == "below-threshold"
    assert d.get("verdict") in (None, "")     # missing additive key -> no KeyError
    assert d.get("matched") in (None, "")
    assert d["sha"] == "1a2b3c4d"


def test_parse_blank_and_garbage_lines_return_none():
    assert GR.parse_line("") is None
    assert GR.parse_line("   ") is None
    assert GR.parse_line("not a log line") is None   # no key=value tokens


def test_summarize_counts_by_verdict_action_matched(tmp_path):
    logf = tmp_path / "gate.log"
    logf.write_text("\n".join([OLD_LINE, NEW_CHATTER, NEW_CLAIM]) + "\n", encoding="utf-8")
    summary = GR.summarize(GR.read_log(logf))
    assert summary["total"] == 3
    assert summary["verdict"]["chatter"] == 1
    assert summary["verdict"]["claim"] == 1
    assert summary["verdict"]["(unset)"] == 1     # the old line
    assert summary["action"]["abstain"] == 2
    assert summary["action"]["pass"] == 1
    assert summary["matched"]["thanks"] == 1


def test_main_review_prints_table(tmp_path, capsys):
    logf = tmp_path / "gate.log"
    logf.write_text(NEW_CHATTER + "\n" + NEW_CLAIM + "\n", encoding="utf-8")
    rc = GR.main(["review", "--log", str(logf)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "verdict" in out and "chatter" in out and "claim" in out
    assert "total: 2" in out
```

- [ ] Run it (expect failure — script does not exist):
  `template/.venv/bin/python -m pytest template/tests/test_gate_review.py -q`
  Expected: `FileNotFoundError` / import error for `scripts/gate_review.py`.

- [ ] Implement. Create `template/scripts/gate_review.py`:

```python
#!/usr/bin/env python3
"""Failure-review CLI for the war-room confidence gate. Stdlib only, Py >=3.9.

Read-mostly operator tool for the classifier-tuning loop. It reads the hash-only
gate.log (0600, never the body), prints a decision-distribution table, and lets
the operator append a CONFIRMED failure to the JSON fixtures file by supplying
the ORIGINAL text transiently on stdin -- the tool re-hashes that text and
verifies it matches a log line's sha256 (proving the right message is labeled)
before writing only the labeled fixture row. It NEVER edits wg_classify.py and
NEVER writes the original text into the log.

Subcommands:
    review   --log <gate.log>                          print the distribution table
    label    --log <gate.log> --sha256 <hex>           hash-match an original (stdin)
             --expected claim|chatter --note <why>     + append a fixture row
             --fixtures <classifier_cases.json>

See docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import OrderedDict


def parse_line(line):
    """Parse one gate.log line into a dict, or None if it has no key=value pairs."""
    if not line or not line.strip():
        return None
    out = {}
    for tok in line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            out[k] = v
    if not out:
        return None
    return out


def read_log(path):
    """Return parsed dicts for every non-empty parseable line in the log file."""
    rows = []
    try:
        with open(str(path), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                d = parse_line(line)
                if d is not None:
                    rows.append(d)
    except OSError:
        return rows
    return rows


def _count(rows, key):
    counts = OrderedDict()
    for d in rows:
        v = d.get(key) or "(unset)"
        counts[v] = counts.get(v, 0) + 1
    return counts


def summarize(rows):
    """Distribution counts grouped by the review-relevant dimensions."""
    return {
        "total": len(rows),
        "verdict": _count(rows, "verdict"),
        "action": _count(rows, "action"),
        "reason": _count(rows, "reason"),
        "matched": _count(rows, "matched"),
    }


def _print_table(summary, out):
    out.write("gate.log review -- total: %d\n" % summary["total"])
    for dim in ("verdict", "action", "reason", "matched"):
        out.write("\n[%s]\n" % dim)
        for k, n in summary[dim].items():
            out.write("  %-16s %d\n" % (k, n))


def _cmd_review(args, out):
    _print_table(summarize(read_log(args.log)), out)
    return 0


def _atomic_write_text(path, text):
    """temp + os.replace, mirroring setup._atomic_write_text discipline."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _cmd_label(args, out, err, stdin):
    # The operator supplies the original text transiently; it is NEVER written to
    # the log. We hash it and confirm it matches A REAL LOG LINE being labeled --
    # the digest must equal both the operator-typed --sha256 AND the sha256 of an
    # actually-present gate.log line, proving the operator is labeling a message
    # that was really gated (spec Arch S3 / Reliability "operator mislabels").
    original = stdin.read()
    if original.endswith("\n"):
        original = original[:-1]
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if digest != args.sha256:
        err.write("sha256 mismatch: supplied text hashes to %s, not %s; "
                  "refusing to label the wrong message.\n" % (digest, args.sha256))
        return 3
    logged = {d.get("sha256") for d in read_log(args.log)}
    if digest not in logged:
        err.write("no gate.log line has sha256=%s; the supplied text was never "
                  "gated (or you read the wrong log). Refusing to label.\n" % digest)
        return 4
    rows = []
    if os.path.exists(args.fixtures):
        with open(args.fixtures, encoding="utf-8") as fh:
            rows = json.load(fh)
    rows.append({
        "text": original,
        "expected_is_claim": (args.expected == "claim"),
        "note": args.note,
    })
    _atomic_write_text(args.fixtures, json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    out.write("appended fixture (expected_is_claim=%s); SANITIZE before commit.\n"
              % (args.expected == "claim"))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="gate_review")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("review", help="print the gate.log distribution table")
    pr.add_argument("--log", required=True)

    pl = sub.add_parser("label", help="hash-match an original (stdin) + append a fixture")
    pl.add_argument("--log", required=True)
    pl.add_argument("--sha256", required=True, help="the log line's sha256 to match")
    pl.add_argument("--expected", required=True, choices=["claim", "chatter"])
    pl.add_argument("--note", required=True)
    pl.add_argument("--fixtures", required=True)

    args = p.parse_args(argv)
    if args.cmd == "review":
        return _cmd_review(args, sys.stdout)
    if args.cmd == "label":
        return _cmd_label(args, sys.stdout, sys.stderr, sys.stdin)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Run it (expect PASS for the parse/summarize/review tests):
  `template/.venv/bin/python -m pytest template/tests/test_gate_review.py -q`
  Expected: `5 passed` (the label tests come in Task 6). Note: the whole CLI — including `_cmd_label` — ships in this task; Task 6's label-flow tests therefore characterize/lock-in the already-shipped label path rather than driving it red-then-green. This is a deliberate T5/T6 split (CLI lands as one coherent file in T5; its fixture-plumbing tests land with the fixtures file in T6).

- [ ] Commit:
  `git add template/scripts/gate_review.py template/tests/test_gate_review.py`
  `git commit -m "AWR classifier-tuning: gate_review.py review-table CLI (parse + summarize) (T5)"`

### Task 6: Fixtures file + parametrized test + label-flow tests + fixture sanitize guard

Ship the empty `classifier_cases.json` (`[]` — Phase 3 fills it from real traffic), wire a parametrized test asserting `is_claim(text) == expected_is_claim` for every row, exercise the `gate_review.py label` hash-match flow (accepts the right original that is present in the log, rejects a wrong original (exit 3), rejects an original whose sha is absent from the log (exit 4), never writes the original into the log), and add a direct-scan sanitize guard over the fixtures file (because `sanitize_check` excludes `tests/` by default — see Deviations).

Files:
- Create: `template/tests/fixtures/classifier_cases.json`
- Modify: `template/tests/test_classify.py` (add the parametrized test)
- Modify: `template/tests/test_gate_review.py` (add label-flow tests)
- Create: `template/tests/test_classifier_fixtures_sanitize.py`

Steps:

- [ ] Create the empty fixtures file `template/tests/fixtures/classifier_cases.json` with exactly:

```json
[]
```

- [ ] Write the parametrized test. Append to `template/tests/test_classify.py`:

```python
import json
from pathlib import Path

import pytest

_CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "classifier_cases.json"


def _load_cases():
    rows = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    return [(r["text"], r["expected_is_claim"], r["note"]) for r in rows]


def test_classifier_cases_file_is_valid_list():
    # Ships empty ([]); the tuning loop (Phase 3, data-gated) appends rows.
    rows = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    for r in rows:
        assert set(r) >= {"text", "expected_is_claim", "note"}
        assert isinstance(r["expected_is_claim"], bool)


@pytest.mark.parametrize("text,expected,note", _load_cases())
def test_classifier_regression_cases(text, expected, note):
    # One confirmed real-traffic failure per row. Empty today by design.
    assert C.is_claim(text) is expected, note
```

  (`C` is already imported as `wg_classify as C` at the top of the existing `test_classify.py`.)

- [ ] Run the parametrized test (expect PASS — empty fixtures means the param test collects zero cases; the validity test passes):
  `template/.venv/bin/python -m pytest template/tests/test_classify.py -q`
  Expected: `0 failures` (5 baseline + `test_classifier_cases_file_is_valid_list`; the parametrized test contributes 0 cases while the file is `[]`).

- [ ] Write the label-flow tests. Append to `template/tests/test_gate_review.py`:

```python
import hashlib
import io
import json as _json

import pytest


def _run_label(monkeypatch, stdin_text, argv):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    return GR.main(argv)


def test_label_appends_fixture_on_hash_match(tmp_path, monkeypatch):
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    original = "rolling back the deploy now"
    sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    logf.write_text(
        ("2026-06-09T18:00:00+00:00 verdict=chatter action=pass reason=chatter "
         "conf=- kind=chatter len=s ends_q=0 multiline=0 matched=none sha256=%s\n" % sha),
        encoding="utf-8")
    rc = _run_label(monkeypatch, original, [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "claim", "--note", "FN: action statement passed as chatter",
        "--fixtures", str(fixtures)])
    assert rc == 0
    rows = _json.loads(fixtures.read_text(encoding="utf-8"))
    assert rows == [{
        "text": "rolling back the deploy now",
        "expected_is_claim": True,
        "note": "FN: action statement passed as chatter",
    }]
    # the original text must NOT have been written into the log
    assert "rolling back the deploy now" not in logf.read_text(encoding="utf-8")


def test_label_rejects_wrong_original(tmp_path, monkeypatch):
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    sha = hashlib.sha256("the real message".encode("utf-8")).hexdigest()
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=%s\n" % sha, encoding="utf-8")
    rc = _run_label(monkeypatch, "a DIFFERENT message", [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "chatter", "--note", "should reject", "--fixtures", str(fixtures)])
    assert rc == 3                                          # sha256 mismatch
    assert _json.loads(fixtures.read_text(encoding="utf-8")) == []   # nothing appended


def test_label_rejects_sha_absent_from_log(tmp_path, monkeypatch):
    # The supplied text hashes to --sha256 (so exit 3 does NOT fire), but no
    # gate.log line carries that sha256 -> the message was never gated, so the
    # tool must refuse (exit 4) rather than label a phantom decision.
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    other = hashlib.sha256("some other gated line".encode("utf-8")).hexdigest()
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=%s\n" % other, encoding="utf-8")
    original = "a message that was never gated"
    sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    rc = _run_label(monkeypatch, original, [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "claim", "--note", "should reject: not in log",
        "--fixtures", str(fixtures)])
    assert rc == 4                                          # sha not present in log
    assert _json.loads(fixtures.read_text(encoding="utf-8")) == []   # nothing appended


def test_label_bad_expected_value_exits_2(tmp_path, monkeypatch):
    # argparse choices reject anything but claim|chatter -> SystemExit(2).
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=deadbeef\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_label(monkeypatch, "x", [
            "label", "--log", str(logf), "--sha256", "deadbeef",
            "--expected", "maybe", "--note", "n", "--fixtures", str(fixtures)])
    assert exc.value.code == 2
```

- [ ] Run the gate-review tests (expect PASS):
  `template/.venv/bin/python -m pytest template/tests/test_gate_review.py -q`
  Expected: `0 failures` (5 from Task 5 + 4 label-flow tests = 9).

- [ ] Write the fixture sanitize guard. Create `template/tests/test_classifier_fixtures_sanitize.py`:

```python
"""Direct sanitize scan over the classifier fixtures file.

sanitize_check excludes tests/ by default, so committed fixture rows would
otherwise escape the public-repo gate. This scans the fixtures FILE's directory
directly via sanitize_check.scan so any future operator-added row carrying a
leaked shape (Slack/Discord id, snowflake, internal host) or a configured
employer/operator name is caught in CI.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "classifier_cases.json"


def _load_checker():
    path = ROOT / "scripts" / "sanitize_check.py"
    spec = importlib.util.spec_from_file_location("sanitize_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()


def test_shipped_classifier_fixtures_are_clean():
    violations = checker.scan(str(FIXTURES.parent), names=["alpha-sh", "beta-sh"])
    leaks = [v for v in violations if FIXTURES.name in v[0]]
    assert leaks == [], "fixture sanitization violations: %r" % leaks


def test_scan_flags_a_leaked_shape_in_a_fixture(tmp_path):
    # Prove the guard bites: a fixture row carrying a blocked shape is caught.
    bad = tmp_path / "classifier_cases.json"
    bad.write_text('[{"text": "ping from U0ABCDE1234X", '
                   '"expected_is_claim": false, "note": "x"}]\n', encoding="utf-8")
    v = checker.scan(str(tmp_path))
    assert any(r == "blocked-shape" for _, _, r, _ in v)
```

- [ ] Run it (expect PASS — the shipped fixtures are empty/clean):
  `template/.venv/bin/python -m pytest template/tests/test_classifier_fixtures_sanitize.py -q`
  Expected: `2 passed`.

- [ ] Suite-green checkpoint: `template/.venv/bin/python -m pytest template -q` → 0 failures. Then `python3 template/scripts/sanitize_check.py template/` → exit 0.

- [ ] Commit:
  `git add template/tests/fixtures/classifier_cases.json template/tests/test_classify.py template/tests/test_gate_review.py template/tests/test_classifier_fixtures_sanitize.py`
  `git commit -m "AWR classifier-tuning: empty JSON fixtures + parametrized regression + label-flow + fixture sanitize guard (T6)"`

### Task 7: Operator runbook

Standalone runbook documenting the six-step tuning loop, the exact `gate_review.py` commands, the manual export/rotate step, and the FP/FN targets. The `docs/superpowers/runbooks/` directory does not exist yet — `git add` of this file creates it. A small structural test pins the runbook's required sections so it cannot silently drift out of step with the tool's CLI.

Files:
- Create: `docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md`
- Create: `template/tests/test_runbook_classifier.py`

Steps:

- [ ] Write the failing test. Create `template/tests/test_runbook_classifier.py`:

```python
"""Structural guard for the classifier-tuning operator runbook."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNBOOK = REPO / "docs" / "superpowers" / "runbooks" / "2026-06-09-awr-classifier-tuning-runbook.md"


def test_runbook_exists_and_documents_the_loop():
    text = RUNBOOK.read_text(encoding="utf-8")
    for step in ("COLLECT", "LABEL", "FIXTURE", "TEST", "TUNE", "VERIFY"):
        assert step in text, step
    assert "gate_review.py review --log" in text
    assert "gate_review.py label --log" in text
    assert "classifier_cases.json" in text
    assert "never" in text.lower() and "length" in text.lower()
    assert "false negative" in text.lower() and "false positive" in text.lower()
    assert "rotate" in text.lower() or "truncate" in text.lower()
```

- [ ] Run it (expect failure — runbook does not exist):
  `template/.venv/bin/python -m pytest template/tests/test_runbook_classifier.py -q`
  Expected: `FileNotFoundError` (the runbook path does not resolve).

- [ ] Implement. Create `docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md`:

```markdown
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
```

- [ ] Run it (expect PASS):
  `template/.venv/bin/python -m pytest template/tests/test_runbook_classifier.py -q`
  Expected: `1 passed`.

- [ ] Suite-green checkpoint: `template/.venv/bin/python -m pytest template -q` → 0 failures. Then `python3 template/scripts/sanitize_check.py template/` → exit 0. (The runbook lives outside `template/`, so it is not in the sanitize scope; intentional — it documents commands and contains no fixtures.)

- [ ] Commit:
  `git add docs/superpowers/runbooks/2026-06-09-awr-classifier-tuning-runbook.md template/tests/test_runbook_classifier.py`
  `git commit -m "AWR classifier-tuning: operator runbook + structural guard (T7)"`

---

## Final verification (whole-harness checkpoint)

- [ ] Full suite: `template/.venv/bin/python -m pytest template -q` → 0 failures. Relative to the 409-passed/10-skipped baseline this plan adds roughly +31 tests (Task 1: 3, Task 2: 4, Task 3: 8, Task 4: 3, Task 5: 5, Task 6: validity 1 + label-flow 4 + fixture sanitize 2, Task 7: 1), 0 skips added.
- [ ] Sanitize: `python3 template/scripts/sanitize_check.py template/` → exit 0.
- [ ] Employer-leak grep over the touched tree: `grep -RIn -i "twelvelabs|twelve labs|@twelvelabs|tl-branding" template/ docs/superpowers/runbooks/` → empty.
- [ ] Forbidden-helper grep (Option B invariant): `grep -RIn "normalize_unsentineled_blocks|_strip_bare_block|_MANAGED_BLOCKS" template/` → empty.
- [ ] Confirm `wg_classify.py`'s `_CHATTER` set and the `is_claim` rules are byte-unchanged from baseline except for the appended `matched_chatter` helper: `git diff main -- template/plugins/warroom-gate/wg_classify.py` (unified, NOT `--stat`, which only reports counts) shows only an appended `matched_chatter` function after line 31 — no hunks touching lines 7–31 (the `_CHATTER` set and `is_claim` rules).
- [ ] Confirm `classifier_cases.json` is still `[]` (Phase 3 is not run here).
```
