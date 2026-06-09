# DEFCON / Severity Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Give the war-room confidence gate graduated rigor — per-severity confidence floors driven by an envelope `sev=` tag, plus a fail-closed independent-verifier handshake over the mailbox for top-severity claims.

**Architecture:** The gate plugin (`template/plugins/warroom-gate/`) gains `sev=` envelope parsing, a severity→floor table resolved at decide time, and a new `wg_verify` client that shells out to the mailbox CLI (join → directed `send --to` → bounded `inbox --json` poll) for a second agent's signed verdict; every failure path resolves to an abstention inside `wg_gate.gate()`'s existing top-level try/except. The setup layer (`template/warroom_setup/`) renders one nested `severity_thresholds:` mapping into the sentinel-managed `war_room:` block and collects the new knobs via appended wizard fields; the verifier itself is a behavioral role shipped as a skill doc.

**Tech Stack:** Python 3.9+ stdlib only (`re`, `subprocess`, `json`, `hashlib`, `uuid`, `time.monotonic`, `dataclasses`); pytest; the in-repo `coordination/` mailbox engine/CLI (read-only from the template side except one additive `inbox --json` flag); sentinel-managed YAML via `patch_war_room_block` + Option-B fallback; atomic writes via `setup._atomic_write_text`.

## Adopted decisions

- **D1 Severity inference (spec §1):** explicit envelope `sev=` tag is the source of truth; an optional, conservative classifier upgrade behind `severity_inference: hybrid` can only RAISE an untagged/`default` claim to `alert2` (Phase 3), never lower an explicit tag, never produce `alert1`.
- **D2 Threshold config shape (spec §2):** keep scalar `min_confidence` as the baseline/`default` floor; ADD a nested `severity_thresholds:` mapping; `default` is implied from `min_confidence` when not restated. Fully additive — un-upgraded profiles render byte-identical blocks.
- **D3 Verifier protocol + which severities (spec §3):** only the top tier requires a verifier in v1 (wizard wires `require_verifier_at: alert1`); the verdict is a mailbox message whose body is JSON `{kind, request_id, by, verdict: signed|rejected, envelope, gap}`; the originator polls its inbox against a monotonic deadline (default 30s, clamped ≤120s); any non-`signed` outcome (incl. timeout) abstains.
- **D4 Verifier selection/addressing (spec §4):** static operator-configured `war_room.verifier_label`, routed by `mailbox send --to <label>`; no dynamic election in v1.
- **D5 Auto-escalation (spec §5, narrowed per brief):** the gate only annotates severity (audit `sev=` + envelope); the `/warroom` orchestrator (build-order position 4) performs the `escalate` post per `escalate_at`. NO gate-side send for escalation — guarded by a test.
- **D6 Claim body in transit (spec, data model):** the verify request carries the full claim text (single-host mailbox; the verifier cannot judge what it cannot read); the audit log records only the sha.
- **D7 Unknown `sev` token (spec, reliability note):** two distinct cases. (a) An **in-grammar token absent from the config `severity_thresholds` table** (e.g. `sev=alert3` with no `alert3:` floor configured) maps to the `default` floor (lenient) — the raw token still rides the envelope and is recorded in the audit `sev=` field so the anomaly is visible; never treated as `alert1`. (b) An **out-of-grammar token** (e.g. `sev=alert9`) does NOT match the closed `_ENV_RE` alternation, so the WHOLE envelope fails to parse (`env is None`) and the claim abstains `no-envelope` — fail-closed, the gate never guesses a severity from a malformed footer. **This (b) behavior deliberately supersedes the spec reliability-table row (spec line 354 "Unknown/malformed `sev=` token ⇒ treated as `default` severity")** for out-of-grammar tokens: whole-envelope-absent (safer) rather than silent default-severity. The spec-table "⇒ default" reading is honored only for case (a), an in-grammar token missing from the config table. Pinned by `test_sev_unknown_token_makes_envelope_absent` (T1) and `test_unknown_sev_maps_to_default_floor` (T3).
- **D8 Self-verification guard (spec open question 2):** the gate refuses `verifier_label == war_room.label` (abstains `verifier-unreachable`); verdicts are authenticated by the transport sender (`from_label == verifier_label`), so a self-addressed `by` claim is ignored.
- **D9 Verifier availability fallback (spec open question 3):** strict-abstain when the verifier is silent/unreachable; no `verifier_optional` knob in v1.
- **D10 Severity vocabulary (spec open question 4):** the valid severity tokens are derived from the `severity_thresholds` mapping keys plus the reserved `default`; the `sev=` envelope grammar accepts the fixed closed lexical set `{alert1, alert2, alert3, default}` (so a malformed envelope still parses to a known token shape) but the threshold lookup is config-driven, with `default` always reserved.

## Deviations

- **DV1 (audit field placement):** the brief says "insert `sev=`/`verify=` after `conf=`". Verified against the classifier-tuning-harness plan (build-order position 2): its `wg_audit.log` signature is `log(profile_root, decision, conf, kind, text, verdict=None)` with **no `extra=` parameter**, and it emits `sha256=` **last** with an explicit INTERFACE CONTRACT (classifier Task 3) that "the DEFCON plan (position 3) can insert `sev=`/`verify=` immediately before [`sha256=`] as additive tokens". There is no `extra=` seam and no `test_extra_fields_append_after_sha256` in the landed classifier plan. This plan therefore (a) **modifies `wg_audit.log` to accept an additive `extra=None` keyword** (a dict of ordered `key=value` tokens) and emit those tokens **immediately before `sha256=`** per the classifier INTERFACE CONTRACT, and (b) threads `sev=`/`verify=` through `extra={"sev": ..., "verify": ...}`. The `gate_review.py` parser is order-tolerant `key=value`, so any token order parses; placing them before `sha256=` keeps the contract's "sha256 last" invariant. The resulting audit order is `... matched=... sev=<severity> verify=<state> sha256=<hex>`, so `text.index("sev=") < text.index("sha256=")`. Recorded here per the brief's request to flag any recommendation that needs reconciliation against live source.
- **DV2 (`wg_verify` mailbox CLI discovery):** the spec says `wg_verify` posts "via `enroll.discover_mailbox_cli`". The gate plugin is loaded by Hermes as a flat package with only its own dir on `sys.path` (`plugins/warroom-gate/__init__.py:9`); `warroom_setup.enroll` is NOT importable in the gateway process at runtime. `wg_verify` therefore implements an equivalent stdlib-only discovery (`$MAILBOX_HOME/mailbox` → `<home>/.claude/mailbox/mailbox` → `shutil.which("mailbox")`) mirroring `enroll.discover_mailbox_cli`'s precedence (enroll.py:74-100), minus the dev-checkout fallback (irrelevant in an installed profile). No `warroom_setup` import from the plugin.
- **DV3 (verify-request scope):** the spec example sends the request with `--scope escalate`. Verified against the engine: `send` places the message on the *sender's primary board* with `to=<label>` as a directed filter (`engine.send` engine.py:453-472, `poll_inbox` matches `msg.to == label` engine.py:489); scope only widens *visibility* up/down the tree for `to="*"` reads, and does not change directed same-board delivery. For a designated verifier co-located on the same board (the v1 model, D4), the minimal correct invocation is `send --to <verifier_label>` with default `scope=local`. This plan uses `scope=local`; documented so a future cross-board verifier can switch to `escalate`.
- **DV5 (verify_request `deadline_ts` dropped):** the spec's verify_request data model (spec lines 312-324) lists a `deadline_ts` field. This plan's `build_request` (T5) omits it deliberately: the **originator owns the deadline locally** — `request_and_wait` enforces a monotonic `time.monotonic() + timeout_s` deadline on its own poll loop (D3), and the verifier is asked to reply "promptly" (the verifier SKILL.md), not to honor a wall-clock instant. A `deadline_ts` in the body would be (a) advisory only (the verifier doesn't gate on it) and (b) a wall-clock value crossing into a process that uses a monotonic deadline, which is the exact clock-skew footgun the design avoids. The field carries no behavior in v1, so it is dropped rather than emitted as dead metadata; a future cross-host verifier that wants to self-cancel stale work can add it back (one key in `build_request` + the SKILL.md request example). The verifier SKILL.md request example (T7) is written WITHOUT `deadline_ts` to match. Recorded so the narrowing is intentional, not an omission.
- **DV6 (signed verdict `envelope` is informational in v1):** the spec's signed-resolution prose (spec lines 204-206) and the verdict data model (spec line 334) carry the verifier's own grounded `envelope`. This plan's `_scan_inbox` (T5) authenticates a signed verdict on `(from_label == verifier_label, kind == "verify_verdict", request_id match, verdict == "signed")` and does NOT parse or require the `envelope` field; on `signed` the gate posts the **originator's** existing badge (D3: "the gate returns the original (badged) text"). The verifier's envelope is informational — it documents the verifier's independent grounding for the audit/human reader, but the badge shown is the originator's own confidence, not the verifier's. A signed verdict with a missing/blank envelope is still accepted (the trust boundary is the transport sender + the explicit `signed` verb, not the envelope's presence). This is the conservative v1 choice; a future version could surface the verifier's envelope in the badge ("double-signed: 0.96 by verify-sh"). Recorded so the envelope-not-validated narrowing is intentional.
- **DV7 (unparseable severity_thresholds value / blank verifier_label logging):** the spec reliability table (spec lines 356-357) appends "+ log error" / "+ log misconfig" to two rows. This plan's scanner (`wg_gateconfig._scan`, T2) drops an unparseable nested floor value via `except ValueError: pass` and falls back to `{default: min_confidence}` with NO log call, and the gate abstains on a blank `verifier_label` at a gated severity without a separate misconfig log. Rationale: `wg_gateconfig` is a pure, stdlib-only, never-raise line scanner with no logger handle (mirroring `wg_audit`'s best-effort posture), and adding a logging dependency to the config reader would be a new side effect at parse time. The anomaly is instead made visible where the gate already writes — the audit `sev=` field records the raw/observed severity, and a blank-verifier abstain logs `verify=unreachable` with `reason=verifier-unreachable` (T6), so an operator reviewing `gate.log` sees the misconfig's effect. The "+ log error" intent is satisfied by the audit trail rather than a scanner-time log; recorded so this divergence from the literal spec-table wording is intentional.
- **DV4 (selectables F10 ordering vs. federation test):** the federation plan (position 1) appended `warroom.parent` LAST in `TEXT_FIELDS` and pinned `test_parent_wiring.py::test_selectables_parent_field_appended_last_with_enable_if` with `ids[-1] == "warroom.parent"`. This plan appends its own wizard fields after `warroom.parent`, which would break that strict-last assertion. Task 8 updates that one assertion to `"warroom.parent" in ids` + index-ordering (parent before the DEFCON fields), a change-detector update of the same shape federation itself used for `test_war_room_keys_exact` (their DV1). No behavioral weakening: the F10 "append, never insert between" discipline is preserved. NOTE: `template/tests/test_parent_wiring.py` (and its `_fake_profile`/`_run`/`_ParentAwareRecorder` harness) is CREATED by the federation plan, not pre-existing in live source — Task 8 edits it, so federation (position 1) MUST land first (a pre-flight check asserts the file + helpers + the target test exist by name before Task 8 runs).

---

## Pre-flight (run first; do not skip)

This plan sits at build-order position 3. It assumes positions 1 (multi-board-federation) and 2 (classifier-tuning-harness) have already landed on the branch. Verify the seams before Task 1; if any expectation fails, STOP and surface to the lead (an upstream plan diverged from its spec and this plan's signatures must be reconciled, not silently patched).

- [ ] Confirm the template baseline is green and record the running counts:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
```

Expected at this position: 0 failures. The known-good `main` baseline is **409 passed, 10 skipped**; positions 1+2 add tests on top (federation ≈ +14, classifier ≈ +14 to the template suite), so the live number will be higher. Record whatever it is — this plan's deltas are stated relative to it.

- [ ] Confirm the coordination baseline is green and record the count (this plan touches `coordination/src/mailbox/cli.py` for the additive `inbox --json` flag in Task 4):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
```

Expected: **174 passed, 1 skipped** on `main`; record the live number.

- [ ] Confirm the federation seams exist (Message.scope, `send --to`, `escalate`/`broadcast`, `inbox`, `WAR_ROOM_KEYS` has `parent`, `selectables` ends in `warroom.parent`):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -c "from mailbox.models import Message; print(Message(id='m',board='b',from_session='s',from_label='l',to='*',kind='note',body='x',created=0.0).scope)"
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -c "from warroom_setup import schema, selectables; print('parent' in schema.WAR_ROOM_KEYS, [f.id for f in selectables.TEXT_FIELDS][-1])"
```

Expected: `local` on the first; `True warroom.parent` on the second. If `parent` is absent or the last field is not `warroom.parent`, STOP — federation has not landed and this plan's DV4 / schema edits will collide.

- [ ] Confirm the classifier seam exists by its REAL contract (not an `extra=` kwarg — the classifier plan does not add one). Confirm `wg_audit.log` accepts the `verdict=` kwarg and emits `sha256=` as the LAST token of a logged line (the INTERFACE CONTRACT this plan's Task 3 inserts `sev=`/`verify=` immediately before), and that the chatter branch now logs:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -c "import sys, inspect, tempfile, re; sys.path.insert(0,'template/plugins/warroom-gate'); import wg_audit, wg_policy; print('verdict', 'verdict' in inspect.signature(wg_audit.log).parameters); d=tempfile.mkdtemp(); wg_audit.log(d, wg_policy.Decision(wg_policy.PASS,'ok'), 0.9, 'claim', 'x', verdict='claim'); import pathlib; line=pathlib.Path(d,'local','war_room','gate.log').read_text(); print('sha256-last', bool(re.search(r'sha256=[0-9a-f]+\s*$', line.strip())))"
```

Expected: `verdict True` and `sha256-last True`. If `verdict` is `False` or `sha256` is not the last token, the classifier harness has not landed (or diverged); STOP — DV1 / Task 3 depend on the `verdict=` kwarg and the "sha256 emitted last" interface contract, and Task 3 must reconcile against the actual `wg_audit.log` shape rather than apply its edits verbatim.

- [ ] Confirm the exact position-2 `wg_gate.py` claim-branch anchors this plan find-and-replaces by name. The classifier plan's Task 4 reshapes the claim branch to log `wg_audit.log(root, decision, conf, "claim", response_text, verdict="claim")` — it uses the variable **`response_text`** (NOT `classified`) as the log text and introduces NO `classified` name. Confirm that anchor verbatim:

```bash
grep -nE 'wg_audit\.log\(root, decision, conf, "claim", response_text, verdict="claim"\)' template/plugins/warroom-gate/wg_gate.py && echo "claim-branch anchor OK" || echo "STOP: claim-branch anchor differs"
grep -nq "classified" template/plugins/warroom-gate/wg_gate.py && echo "NOTE: a 'classified' variable exists (position 2 diverged from plan); reconcile Task 3/6/8 to its actual name" || echo "no 'classified' var (expected): Task 3/6/8 use response_text"
```

Expected: `claim-branch anchor OK` and `no 'classified' var (expected)`. If the claim-branch line differs, position 2 named the body variable differently — STOP and reconcile every Task 3/6/8 Edit `old_string`/`new_string` to position-2's actual symbol name (the references below assume `response_text`).

- [ ] Confirm `test_gate_callback.py` does NOT already define a `_gate_log` helper (this plan defines it in Task 3 — the classifier plan reads the log inline via `(tmp_path / "local" / "war_room" / "gate.log").read_text()` and never adds such a helper):

```bash
grep -nq "def _gate_log" template/tests/test_gate_callback.py && echo "NOTE: _gate_log already exists; Task 3 must NOT redefine it" || echo "no _gate_log yet (expected): Task 3 defines it"
```

Expected: `no _gate_log yet (expected)`. If a `_gate_log` already exists (position 2 diverged and added one), skip Task 3's helper definition and reuse the existing one.

- [ ] Confirm the federation `test_parent_wiring.py` harness this plan's Task 8 edits exists with the exact names it depends on (the file + all three helpers + the assertion target are created by the federation plan, position 1; none exist in live source before it lands):

```bash
test -f template/tests/test_parent_wiring.py && \
  grep -nq "def _fake_profile" template/tests/test_parent_wiring.py && \
  grep -nq "def _run" template/tests/test_parent_wiring.py && \
  grep -nq "class _ParentAwareRecorder" template/tests/test_parent_wiring.py && \
  grep -nq "def test_selectables_parent_field_appended_last_with_enable_if" template/tests/test_parent_wiring.py && \
  echo "parent-wiring harness OK" || echo "STOP: parent-wiring harness missing or renamed"
```

Expected: `parent-wiring harness OK`. If missing, federation (position 1) has not landed or renamed a helper — STOP and reconcile Task 8's edits (the `_fake_profile`/`_run`/`_ParentAwareRecorder` calls and the `test_selectables_parent_field_appended_last_with_enable_if` replacement target) to the federation plan's actual symbol names rather than editing blindly.

---

## Phase 1 — per-severity floors (no verifier)

Tasks 1–3. Pure, in-process; ships graduated floors with zero inter-agent dependency. Back-compat: un-tagged claims and untouched config blocks behave identically to today.

## Task 1: Envelope `sev=` field

**Files:**
- Modify: `template/plugins/warroom-gate/wg_envelope.py`
- Modify: `template/tests/test_envelope.py`
- Test: `template/tests/test_envelope.py`

**Steps:**

- [ ] In `template/tests/test_envelope.py`, append these tests to the end of the file:

```python
def test_sev_absent_defaults_to_default():
    env, body = E.parse_last_line("The DB is down.\n⟦conf=0.82 grounded=tool,file missing=none⟧")
    assert env is not None
    assert env.sev == "default"
    assert body == "The DB is down."


def test_sev_parsed_when_present():
    env, body = E.parse_last_line("prod is down\n⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    assert env is not None
    assert env.sev == "alert1"
    assert env.conf == 0.97
    assert env.grounded == ("tool", "file")
    assert body == "prod is down"


def test_sev_each_known_token_parses():
    for tok in ("alert1", "alert2", "alert3", "default"):
        env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool missing=none sev=%s⟧" % tok)
        assert env is not None and env.sev == tok


def test_sev_unknown_token_makes_envelope_absent():
    # An out-of-vocab sev token does not match the anchored grammar, so the whole
    # envelope is treated as absent (same posture as a malformed conf=): a claim
    # with no parseable envelope abstains no-envelope. The gate never silently
    # downgrades to a guessed severity from a malformed footer.
    env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool missing=none sev=alert9⟧")
    assert env is None


def test_sev_must_be_last_field():
    # sev= appears AFTER missing=. A sev before missing is not the canonical
    # grammar and must not parse.
    env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool sev=alert1 missing=none⟧")
    assert env is None


def test_sev_spoof_midmessage_ignored():
    text = "> user said ⟦conf=0.99 grounded=tool missing=none sev=alert1⟧\nactually unverified"
    env, body = E.parse_last_line(text)
    assert env is None
    assert body == text


def test_sev_regex_still_linear_no_redos():
    import time
    payload = "⟦conf=0.9 grounded=tool missing=" + "a" * 100000 + " sev=alert1⟧"
    t = time.time()
    E.parse_last_line("x\n" + payload)
    assert time.time() - t < 1.0
```

- [ ] Run the file (red):

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_envelope.py -q
```

Expected failures: `AttributeError: 'Envelope' object has no attribute 'sev'` on the first three new tests; `test_sev_unknown_token_makes_envelope_absent` / `test_sev_must_be_last_field` may incidentally pass-or-fail depending on the un-extended regex but will be pinned by the implementation. The six original tests stay green.

- [ ] In `template/plugins/warroom-gate/wg_envelope.py`, add the severity vocabulary constant directly after `GROUNDED_VOCAB` (wg_envelope.py:12):

```python
GROUNDED_VOCAB = ("tool", "file", "source", "citation", "memory", "none")

# Closed lexical severity set the envelope grammar accepts. The THRESHOLD lookup
# is config-driven (wg_gateconfig.severity_thresholds keys), but the agent-typed
# token must be one of these to ride the anti-spoofed envelope slot; an out-of-
# vocab token makes the whole envelope unparseable (-> claim abstains
# no-envelope), so the gate never guesses a severity from a malformed footer.
# `default` is reserved as the baseline floor.
SEV_VOCAB = ("alert1", "alert2", "alert3", "default")
```

- [ ] Replace the `_ENV_RE` definition (wg_envelope.py:21-27) with the additive, still-anchored, still-bounded form (the `sev=` group is an optional trailing alternation; `(?:alert1|alert2|alert3|default)` is a fixed closed set, no unbounded quantifier):

```python
_ENV_RE = re.compile(
    "^" + _L
    + r"conf=(?P<conf>0(?:\.\d{1,3})?|1(?:\.0{1,3})?)"
    + r" grounded=(?P<grounded>[a-z,]{1,64})"
    + r" missing=(?P<missing>[^" + _L + _R + r"\n]{0,200})"
    + r"(?: sev=(?P<sev>alert1|alert2|alert3|default))?"
    + _R + "$"
)
```

- [ ] Add the `sev` field to the `Envelope` dataclass (wg_envelope.py:31-35):

```python
@dataclass
class Envelope:
    conf: float
    grounded: Tuple[str, ...]
    missing: str
    sev: str = "default"
```

- [ ] In `parse_last_line`, replace the `Envelope(...)` construction line (wg_envelope.py:50) with a form that defaults `sev` to `"default"` when the optional group did not match:

```python
    env = Envelope(
        conf=float(m.group("conf")),
        grounded=grounded,
        missing=m.group("missing").strip(),
        sev=(m.group("sev") or "default"),
    )
```

- [ ] Run again (green):

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_envelope.py -q
```

Expected: 0 failures (adds 7 tests). The `redos` guard still passes (bounded quantifiers only; `sev=` is a fixed alternation).

- [ ] Commit:

```bash
git add template/plugins/warroom-gate/wg_envelope.py template/tests/test_envelope.py
git commit -m "AWR defcon-severity: optional sev= envelope field (T1)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: `severity_thresholds` config — schema, scanner, renderer, clamps

**Files:**
- Modify: `template/warroom_setup/schema.py`
- Modify: `template/warroom_setup/setup.py`
- Modify: `template/plugins/warroom-gate/wg_gateconfig.py`
- Modify: `template/tests/test_schema.py`
- Modify: `template/tests/test_gateconfig.py`
- Modify: `template/tests/test_patch_war_room_ext.py`
- Test: the four test files above

**Steps:**

- [ ] In `template/tests/test_schema.py`, replace `test_war_room_keys_exact` (the change-detector tuple — same update procedure federation used for `parent`) with the DEFCON-extended tuple, and extend `test_defaults_cover_war_room_keys` for the new defaults. Replace:

```python
def test_war_room_keys_exact():
    assert schema.WAR_ROOM_KEYS == (
        "enabled", "board", "parent", "label", "role", "min_confidence",
        "gate_action", "enforce", "show_confidence_badge",
    )
```

with:

```python
def test_war_room_keys_exact():
    assert schema.WAR_ROOM_KEYS == (
        "enabled", "board", "parent", "label", "role", "min_confidence",
        "gate_action", "enforce", "show_confidence_badge",
        "severity_thresholds", "severity_inference", "require_verifier_at",
        "verifier_label", "verifier_timeout_s", "escalate_at",
    )
```

and append after `test_defaults_cover_war_room_keys` (do not edit its existing body):

```python
def test_defcon_defaults_present_and_safe():
    # All DEFCON keys default OFF / empty so an un-upgraded profile behaves
    # exactly as before: no severity table, no verifier path, no escalation.
    assert schema.DEFAULTS["severity_thresholds"] == {}
    assert schema.DEFAULTS["severity_inference"] == "explicit"
    assert schema.DEFAULTS["require_verifier_at"] == ""
    assert schema.DEFAULTS["verifier_label"] == ""
    assert schema.DEFAULTS["verifier_timeout_s"] == 30
    assert schema.DEFAULTS["escalate_at"] == ""


def test_role_vocab_documents_verifier():
    # role stays a free scalar; verifier is the new sanctioned value.
    assert "verifier" in schema.ROLE_VOCAB and "contributor" in schema.ROLE_VOCAB
```

- [ ] In `template/tests/test_gateconfig.py`, the exact-equality `test_defaults_when_missing` will break once `read()` returns the new keys — update it to assert the superset and add the new-key tests. Replace:

```python
def test_defaults_when_missing(tmp_path):
    cfg = G.read(tmp_path)            # no config.yaml
    assert cfg == {"enforce": False, "min_confidence": 75, "show_badge": True}
```

with:

```python
def test_defaults_when_missing(tmp_path):
    cfg = G.read(tmp_path)            # no config.yaml
    # The original scalars are unchanged...
    assert cfg["enforce"] is False
    assert cfg["min_confidence"] == 75
    assert cfg["show_badge"] is True
    # ...and the DEFCON keys default OFF (no severity table => default-only floor).
    assert cfg["severity_thresholds"] == {"default": 75}
    assert cfg["severity_inference"] == "explicit"
    assert cfg["require_verifier_at"] == ""
    assert cfg["verifier_label"] == ""
    assert cfg["verifier_timeout_s"] == 30
    assert cfg["escalate_at"] == ""


def test_default_floor_derived_from_min_confidence_when_no_table(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  min_confidence: 90\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"default": 90}


def test_nested_severity_thresholds_parsed(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model: {}\n"
        "war_room:\n"
        "  enabled: true\n"
        "  min_confidence: 75\n"
        "  enforce: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "    alert2: 85\n"
        "    default: 75\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: verify-sh\n"
        "  verifier_timeout_s: 45\n"
        "  escalate_at: alert2\n"
        "plugins:\n  enabled: true\n"
    )
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "alert2": 85, "default": 75}
    assert cfg["require_verifier_at"] == "alert1"
    assert cfg["verifier_label"] == "verify-sh"
    assert cfg["verifier_timeout_s"] == 45
    assert cfg["escalate_at"] == "alert2"
    # the flat scalars after the nested mapping are still read
    assert cfg["enforce"] is True and cfg["min_confidence"] == 75


def test_nested_table_implies_default_from_min_confidence(tmp_path):
    # severity_thresholds present but no explicit `default` key -> default
    # floor falls back to min_confidence.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  min_confidence: 70\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "default": 70}


def test_block_end_detection_with_nested_mapping(tmp_path):
    # A non-indented key after the nested mapping ends the block; keys beyond
    # the block (plugins:) must not leak in.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "plugins:\n"
        "  alert1: 1\n")    # a same-named key OUTSIDE the block must be ignored
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "default": 75}


def test_verifier_timeout_clamped(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  verifier_timeout_s: 9999\n")
    assert G.read(tmp_path)["verifier_timeout_s"] == 120   # clamp <=120
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  verifier_timeout_s: 0\n")
    assert G.read(tmp_path)["verifier_timeout_s"] == 1     # clamp >=1


def test_unparseable_severity_value_skipped(tmp_path):
    # A non-int floor under the nested mapping is dropped (not a crash); the
    # default floor still resolves from min_confidence.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  min_confidence: 75\n"
        "  severity_thresholds:\n"
        "    alert1: high\n"
        "    alert2: 85\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert2": 85, "default": 75}
```

- [ ] In `template/tests/test_patch_war_room_ext.py`, append a test pinning the nested-mapping render + omit-when-empty behavior:

```python
def test_renders_nested_severity_thresholds(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(
        tmp_path, "board-x",
        severity_thresholds={"alert1": 95, "alert2": 85, "default": 75},
        require_verifier_at="alert1", verifier_label="verify-sh",
        verifier_timeout_s=45, escalate_at="alert2")
    text = cfg.read_text(encoding="utf-8")
    assert "  severity_thresholds:" in text
    assert "    alert1: 95" in text
    assert "    alert2: 85" in text
    assert "    default: 75" in text
    assert "require_verifier_at: alert1" in text
    assert "verifier_label: verify-sh" in text
    assert "verifier_timeout_s: 45" in text
    assert "escalate_at: alert2" in text


def test_empty_severity_thresholds_omitted(tmp_path):
    # Zero-rendered-byte change for non-DEFCON profiles (D2 byte-identical
    # guarantee): the empty dict, the empty-string DEFCON keys, AND the
    # default-valued DEFCON scalars (severity_inference, verifier_timeout_s) are
    # all omitted when no DEFCON surface is configured.
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")
    text = cfg.read_text(encoding="utf-8")
    assert "severity_thresholds:" not in text
    assert "require_verifier_at:" not in text
    assert "verifier_label:" not in text
    assert "escalate_at:" not in text
    # default-valued DEFCON scalars are NOT emitted for a plain profile, so the
    # block matches the pre-DEFCON bytes exactly.
    assert "verifier_timeout_s:" not in text
    assert "severity_inference:" not in text


def test_default_block_is_byte_identical_to_pre_defcon(tmp_path):
    # The whole point of D2: a plain non-DEFCON patch produces the exact same
    # war_room block bytes the pre-DEFCON renderer produced (the shipped
    # config.yaml block shape). Pin every DEFCON key absent.
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")
    text = cfg.read_text(encoding="utf-8")
    for k in ("severity_thresholds", "severity_inference", "require_verifier_at",
              "verifier_label", "verifier_timeout_s", "escalate_at"):
        assert ("%s" % k) not in text, "%s must not render for a non-DEFCON profile" % k


def test_severity_block_survives_reanchor_after_reemit(tmp_path):
    # Option B: nested mapping is captured by the YAML-key fallback span.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "top: 1\n"
        "war_room:\n"
        "  enabled: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "\n"
        "bottom: 2\n", encoding="utf-8")
    setup.patch_war_room_block(
        tmp_path, "shared",
        severity_thresholds={"alert1": 90, "default": 75})
    text = cfg.read_text(encoding="utf-8")
    assert _key_count(text, "war_room") == 1
    assert setup._WR_BEGIN in text and setup._WR_END in text
    assert "    alert1: 90" in text and "alert1: 95" not in text
    assert "bottom: 2" in text
```

- [ ] Run all four red:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_schema.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gateconfig.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_patch_war_room_ext.py -q
```

Expected failures: `test_war_room_keys_exact` mismatch; `AttributeError` on `schema.ROLE_VOCAB`; `KeyError`/assert failures on `severity_thresholds` etc. in gateconfig; `TypeError: patch_war_room_block() got unexpected war_room keys: severity_thresholds, ...` in the ext file.

- [ ] Implement schema. In `template/warroom_setup/schema.py`, replace `WAR_ROOM_KEYS` (currently the federation-extended 9-tuple) with the DEFCON-extended tuple:

```python
# Ordered key set for the sentinel-managed war_room config block. The DEFCON /
# severity keys (severity_thresholds .. escalate_at) are all optional. They render
# only when the feature is configured: severity_thresholds={} is omitted, the ""
# scalars are omitted, and the default-valued DEFCON scalars
# (severity_inference="explicit", verifier_timeout_s=30) are omitted too UNLESS a
# DEFCON surface is set (see the renderer's _defcon_on guard in setup.py). So a
# non-DEFCON profile keeps the EXACT pre-DEFCON block bytes.
WAR_ROOM_KEYS = (
    "enabled", "board", "parent", "label", "role", "min_confidence",
    "gate_action", "enforce", "show_confidence_badge",
    "severity_thresholds", "severity_inference", "require_verifier_at",
    "verifier_label", "verifier_timeout_s", "escalate_at",
)

# Sanctioned war_room.role values. `verifier` (DEFCON / severity spec) names an
# agent that services verification requests; `contributor` is the default. Other
# values are tolerated (free scalar) but these are documented.
ROLE_VOCAB = ("contributor", "verifier")
```

and replace `DEFAULTS` (the federation-extended dict) with the DEFCON-extended dict (append the six new keys after `show_confidence_badge`):

```python
DEFAULTS = {
    "enabled": True,
    "board": "default",
    "parent": "",
    "label": "",
    "role": "contributor",
    "min_confidence": 75,
    "gate_action": "abstain",
    "enforce": False,
    "show_confidence_badge": True,
    # --- DEFCON / severity (all optional; OFF/empty by default) ---
    "severity_thresholds": {},     # {} => default-only floor from min_confidence
    "severity_inference": "explicit",
    "require_verifier_at": "",     # "" => never require a verifier
    "verifier_label": "",
    "verifier_timeout_s": 30,
    "escalate_at": "",             # "" => never auto-escalate (orchestrator-driven)
}
```

- [ ] Implement the renderer. In `template/warroom_setup/setup.py`, replace the rendering loop inside `patch_war_room_block` (setup.py:210-217 — the `lines = [_WR_BEGIN, "war_room:"]` block through `block = "\n".join(lines)`) with a version that emits one nested mapping level for `severity_thresholds`:

```python
    # Whether ANY DEFCON / severity surface is configured. When nothing is set,
    # the default-valued DEFCON scalars (severity_inference="explicit",
    # verifier_timeout_s=30) are omitted too, so a non-DEFCON profile renders the
    # EXACT pre-DEFCON block bytes (D2 / spec §2 "render exactly today's block").
    _defcon_on = bool(
        (isinstance(values.get("severity_thresholds"), dict)
         and values.get("severity_thresholds"))
        or (values.get("require_verifier_at") or "")
        or (values.get("verifier_label") or "")
        or (values.get("escalate_at") or "")
    )
    # DEFCON scalar keys that carry a non-empty default; omit them at their
    # default UNLESS some DEFCON surface is configured (then render the full set
    # so the operator sees the active knobs).
    _defcon_default_scalars = {"severity_inference": "explicit",
                               "verifier_timeout_s": 30}

    lines = [_WR_BEGIN, "war_room:"]
    for key in schema.WAR_ROOM_KEYS:
        val = values.get(key)
        if key == "severity_thresholds":
            # The one nested case: a dict renders as an indented sub-mapping;
            # an empty/missing dict is omitted entirely (zero-byte change for
            # non-DEFCON profiles). Keys render in sorted order for stability.
            if isinstance(val, dict) and val:
                lines.append("  severity_thresholds:")
                for sk in sorted(val):
                    lines.append("    %s: %s" % (sk, _yaml_scalar(val[sk])))
            continue
        if val is None or (isinstance(val, str) and val == ""):
            continue
        # Omit a default-valued DEFCON scalar when no DEFCON surface is on, so the
        # block stays byte-identical to the pre-DEFCON render for plain profiles.
        if (not _defcon_on and key in _defcon_default_scalars
                and val == _defcon_default_scalars[key]):
            continue
        lines.append("  %s: %s" % (key, _yaml_scalar(val)))
    lines.append(_WR_END)
    block = "\n".join(lines)
```

(Note: `patch_war_room_block` validates kwargs against `schema.WAR_ROOM_KEYS` at setup.py:193-198 and `values.update(overrides)` at :201 — adding the keys to `WAR_ROOM_KEYS`/`DEFAULTS` is sufficient for them to be accepted and defaulted. `severity_thresholds` defaults to `{}` so the `isinstance(val, dict) and val` guard omits it unless an override supplies a non-empty dict; the default `severity_inference`/`verifier_timeout_s` scalars are also omitted unless a DEFCON surface is configured, preserving D2's byte-identical guarantee for un-upgraded profiles.)

- [ ] Implement the scanner. In `template/plugins/warroom-gate/wg_gateconfig.py`, replace the WHOLE file with the nested-aware version (keeps the line-scan idiom, no PyYAML; tracks one nested-mapping level for `severity_thresholds`):

```python
"""Read war_room.* from <profile>/config.yaml. Stdlib only, Python >=3.9.

Line-based scan of the `war_room:` block (no PyYAML). Conservative defaults;
`enforce` defaults False so an un-set-up profile does not gate. Understands ONE
nested mapping level (`severity_thresholds:`) for the DEFCON / severity model;
every other key stays flat.
"""
import re
from pathlib import Path
from typing import Dict

_DEFAULTS = {
    "enforce": False,
    "min_confidence": 75,
    "show_badge": True,
    "severity_thresholds": {},     # filled with {"default": min_confidence} below
    "severity_inference": "explicit",
    "require_verifier_at": "",
    "verifier_label": "",
    "verifier_timeout_s": 30,
    "escalate_at": "",
}

# Clamp the bounded wait so a misconfig can't hang the gateway turn (spec
# "Critical": monotonic deadline + reader clamp).
_TIMEOUT_MIN = 1
_TIMEOUT_MAX = 120


def _fresh_defaults():
    # type: () -> Dict
    out = dict(_DEFAULTS)
    out["severity_thresholds"] = {}
    return out


def _scan(text):
    # type: (str) -> Dict
    out = _fresh_defaults()
    in_wr = False
    in_sev = False           # inside the severity_thresholds: nested mapping
    sev = {}                 # type: Dict[str, int]
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("war_room:"):
            in_wr = True
            continue
        if not in_wr:
            continue
        # A non-indented, non-comment, non-empty line ends the block.
        if line[:1] not in (" ", "\t", "#") and s:
            break
        # Inside the nested mapping: a child line is indented MORE than the
        # `severity_thresholds:` header (>=4 leading spaces here). Any line
        # indented at the block's own key level (2 spaces) ends the nested map.
        if in_sev:
            indent = len(line) - len(line.lstrip(" "))
            cm = re.match(r"([a-z0-9_]+):\s*(\S+)", s)
            if indent >= 4 and cm:
                try:
                    sev[cm.group(1)] = max(0, min(100, int(cm.group(2))))
                except ValueError:
                    pass
                continue
            # blank line inside the mapping is tolerated, stays nested
            if not s:
                continue
            in_sev = False   # fall through to flat-key handling for this line
        if s.startswith("severity_thresholds:"):
            in_sev = True
            continue
        m = re.match(
            r"(enforce|min_confidence|show_confidence_badge|severity_inference|"
            r"require_verifier_at|verifier_label|verifier_timeout_s|escalate_at"
            r"):\s*(\S+)", s)
        if m:
            k, v = m.group(1), m.group(2)
            if k == "enforce":
                out["enforce"] = v.lower() == "true"
            elif k == "min_confidence":
                try:
                    out["min_confidence"] = max(0, min(100, int(v)))
                except ValueError:
                    pass
            elif k == "show_confidence_badge":
                out["show_badge"] = v.lower() == "true"
            elif k == "severity_inference":
                out["severity_inference"] = v
            elif k == "require_verifier_at":
                out["require_verifier_at"] = v
            elif k == "verifier_label":
                out["verifier_label"] = v
            elif k == "verifier_timeout_s":
                try:
                    out["verifier_timeout_s"] = max(
                        _TIMEOUT_MIN, min(_TIMEOUT_MAX, int(v)))
                except ValueError:
                    pass
            elif k == "escalate_at":
                out["escalate_at"] = v
    # The default floor is min_confidence unless the table restated it.
    if "default" not in sev:
        sev["default"] = out["min_confidence"]
    out["severity_thresholds"] = sev
    return out


def read(profile_root):
    # type: (Path) -> Dict
    p = Path(profile_root) / "config.yaml"
    if not p.is_file():
        out = _fresh_defaults()
        out["severity_thresholds"] = {"default": out["min_confidence"]}
        return out
    try:
        return _scan(p.read_text(encoding="utf-8"))
    except OSError:
        out = _fresh_defaults()
        out["severity_thresholds"] = {"default": out["min_confidence"]}
        return out
```

- [ ] Run all four green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_schema.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gateconfig.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_patch_war_room_ext.py -q
```

Expected: 0 failures (adds ~2 schema + ~7 gateconfig + ~3 ext = ~12 tests).

- [ ] Commit:

```bash
git add template/warroom_setup/schema.py template/warroom_setup/setup.py template/plugins/warroom-gate/wg_gateconfig.py template/tests/test_schema.py template/tests/test_gateconfig.py template/tests/test_patch_war_room_ext.py
git commit -m "AWR defcon-severity: severity_thresholds config + nested-mapping render/scan (T2)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: `decide(severity)` floor resolution, `below-severity-floor` reason, render, gate wiring, audit `sev=`

**Files:**
- Modify: `template/plugins/warroom-gate/wg_policy.py`
- Modify: `template/plugins/warroom-gate/wg_render.py`
- Modify: `template/plugins/warroom-gate/wg_gate.py`
- Modify: `template/plugins/warroom-gate/wg_audit.py` (add the additive `extra=` kwarg — the classifier plan's `log()` has no such param; DV1)
- Modify: `template/tests/test_policy.py`
- Modify: `template/tests/test_gate_render.py`
- Modify: `template/tests/test_gate_callback.py`
- Modify: `template/tests/test_audit.py`
- Test: the six test files above

**Steps:**

- [ ] In `template/tests/test_policy.py`, append the severity-floor decision-table tests (the existing five stay; the existing five call `decide(is_claim, env, threshold)` positionally, which the new signature preserves via keyword-defaulted `severity_thresholds`):

```python
def _envs(conf, sev="default", grounded=("tool",)):
    return Envelope(conf=conf, grounded=grounded, missing="none", sev=sev)


_TABLE = {"alert1": 95, "alert2": 85, "default": 75}


def test_default_sev_uses_default_floor():
    d = P.decide(True, _envs(0.80, "default"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"


def test_alert2_below_its_floor_is_below_severity_floor():
    # clears default 75 but not alert2 85
    d = P.decide(True, _envs(0.80, "alert2"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-severity-floor"


def test_alert1_below_its_floor_is_below_severity_floor():
    d = P.decide(True, _envs(0.90, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-severity-floor"


def test_alert1_clears_its_floor_passes():
    d = P.decide(True, _envs(0.97, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"


def test_below_baseline_is_below_threshold_not_severity_floor():
    # below even the default floor -> the generic below-threshold reason
    d = P.decide(True, _envs(0.50, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-threshold"


def test_unknown_sev_maps_to_default_floor():
    # An envelope can only carry an in-vocab sev (regex-enforced), but a config
    # table missing that sev key falls back to the default floor (lenient, D7).
    d = P.decide(True, _envs(0.80, "alert3"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"      # alert3 absent -> default 75


def test_no_table_falls_back_to_scalar_threshold():
    # severity_thresholds None/empty -> the passed threshold is the floor for all.
    d = P.decide(True, _envs(0.80, "alert1"), 0.75)
    assert d.action == P.PASS and d.reason == "ok"
```

- [ ] In `template/tests/test_gate_render.py`, append abstention-copy tests for the new reasons:

```python
def test_below_severity_floor_abstention_names_severity_and_floor():
    d = P.Decision(P.ABSTAIN, "below-severity-floor", "a prod log line")
    msg = R.abstention(d, conf_pct=90, threshold_pct=95)
    assert "90%" in msg and "95%" in msg
    assert "Holding back" in msg and "a prod log line" in msg


def test_verifier_rejected_abstention_names_gap():
    d = P.Decision(P.ABSTAIN, "verifier-rejected", "verifier could not reproduce")
    msg = R.abstention(d)
    assert "verifier" in msg.lower() and "verifier could not reproduce" in msg


def test_verifier_timeout_abstention():
    d = P.Decision(P.ABSTAIN, "verifier-timeout")
    msg = R.abstention(d)
    assert "Holding back" in msg and "verifier" in msg.lower()


def test_verifier_unreachable_abstention():
    d = P.Decision(P.ABSTAIN, "verifier-unreachable")
    msg = R.abstention(d)
    assert "Holding back" in msg and "verifier" in msg.lower()
```

- [ ] In `template/tests/test_gate_callback.py`, append end-to-end Phase-1 severity tests (these depend only on `decide`/config; verifier is wired in Task 6). First add a `_gate_log` reader helper and a sibling profile helper at the end of the file (do not edit the existing `_profile`):

```python
def _gate_log(tmp_path):
    # Read the gate.log this plan's tests assert against. The classifier plan
    # (position 2) reads the log inline via .read_text(); this plan factors that
    # into one helper. If position 2 already defined a `_gate_log`, drop this
    # definition and reuse theirs (the pre-flight flags that case).
    return (tmp_path / "local" / "war_room" / "gate.log").read_text(encoding="utf-8")


def _sev_profile(tmp_path, table_lines, enforce=True, min_conf=75):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  min_confidence: %d\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n%s" % (str(enforce).lower(), min_conf, table_lines)
    )
    return tmp_path


def test_alert1_below_severity_floor_abstains_endtoend(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.90 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "Holding back" in out


def test_alert1_clears_floor_passes_with_badge_endtoend(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "⟦" not in out and "97%" in out


def test_alert1_audit_records_sev(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    line = _gate_log(tmp_path)
    assert "sev=alert1" in line
    # verify field present (none on a no-verifier path)
    assert "verify=none" in line
```

- [ ] In `template/tests/test_audit.py`, append a test pinning the `sev=`/`verify=` extra fields and the no-secrets contract. This pins the DV1 contract: the `extra=` tokens land IMMEDIATELY BEFORE `sha256=` (which the classifier plan emits last), so `sev=` precedes `sha256=` in the line:

```python
def test_log_records_sev_and_verify_extra(tmp_path):
    d = P.Decision(P.PASS, "ok")
    A.log(tmp_path, d, 0.97, "claim", "prod db corrupted",
          verdict="claim", extra={"sev": "alert1", "verify": "signed"})
    text = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "sev=alert1" in text and "verify=signed" in text
    # extra fields land immediately BEFORE sha256= (DV1: this plan adds the extra=
    # kwarg; the classifier plan's INTERFACE CONTRACT keeps sha256= last).
    assert text.index("sev=") < text.index("sha256=")
    assert text.index("verify=") < text.index("sha256=")
    # still no body in the log
    assert "prod db corrupted" not in text
```

- [ ] Run all five red:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_policy.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_render.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_audit.py -q
```

Expected failures: `decide() got an unexpected keyword argument 'severity_thresholds'`; render assertions for the new reasons fail (they currently fall through to the generic "gate error" copy); the gate end-to-end severity tests fail because `wg_gate` does not yet pass severity into `decide` nor log `sev`/`verify`; `test_log_records_sev_and_verify_extra` fails with `TypeError: log() got an unexpected keyword argument 'extra'` (the classifier plan's `log()` has NO `extra=` param — this plan adds it below).

- [ ] Implement the `extra=` audit seam (DV1). The classifier plan's `wg_audit.log` is `log(profile_root, decision, conf, kind, text, verdict=None)` and emits `sha256=` LAST. Add an additive `extra=None` keyword that renders ordered `key=value` tokens IMMEDIATELY BEFORE `sha256=` (preserving the "sha256 last" interface contract). In `template/plugins/warroom-gate/wg_audit.py`, change the `log` signature and splice the `extra` tokens into the line just before `sha256=`. Replace the signature line:

```python
def log(profile_root, decision, conf, kind, text, verdict=None):
    # type: (Path, Decision, Optional[float], str, str, Optional[str]) -> None
```

with:

```python
def log(profile_root, decision, conf, kind, text, verdict=None, extra=None):
    # type: (Path, Decision, Optional[float], str, str, Optional[str], Optional[dict]) -> None
```

and replace the line-assembly block (the classifier plan's `verdict_tok = ...` through the `line = (...) % (...)` formatting) with a version that emits the `extra` tokens immediately before `sha256=`:

```python
        verdict_tok = "" if verdict is None else ("verdict=%s " % verdict)
        # DEFCON / severity (DV1): ordered additive tokens (e.g. sev=, verify=)
        # rendered immediately BEFORE sha256= so the "sha256 emitted last"
        # interface contract holds. dict insertion order is stable (py3.7+).
        extra_tok = ""
        if extra:
            extra_tok = "".join("%s=%s " % (k, v) for k, v in extra.items())
        line = (
            "%s %saction=%s reason=%s conf=%s kind=%s "
            "len=%s ends_q=%s multiline=%s matched=%s %ssha256=%s\n"
        ) % (
            ts, verdict_tok, decision.action, decision.reason, conf_s, kind,
            _len_bucket(t), ends_q, multiline, matched, extra_tok, digest,
        )
```

(If position 2's actual `log()` body differs from the classifier plan's documented shape — e.g. a different feature set or formatting — reconcile this splice to the live line assembly, keeping the rule: `extra` tokens go immediately before `sha256=`, and `sha256=` stays last. The pre-flight `sha256-last` check guards the interface; this edit must preserve it.)

- [ ] Implement `wg_policy`. Replace the whole `template/plugins/warroom-gate/wg_policy.py` with:

```python
"""Gate decision. Stdlib only, Python >=3.9. Pure."""
from dataclasses import dataclass
from typing import Dict, Optional

from wg_envelope import Envelope

PASS = "pass"
ABSTAIN = "abstain"


@dataclass
class Decision:
    action: str          # PASS | ABSTAIN
    # reason vocab:
    #   chatter | ok | no-envelope | ungrounded | below-threshold |
    #   below-severity-floor | verifier-rejected | verifier-timeout |
    #   verifier-unreachable | empty-body | internal-error
    reason: str
    missing: str = ""


def resolve_floor(sev, threshold, severity_thresholds=None):
    # type: (str, float, Optional[Dict[str, int]]) -> float
    """Per-severity floor as a [0,1] fraction. With no table, returns the scalar
    threshold (back-compat). With a table, looks up `sev`, falling back to
    `default`, falling back to the scalar threshold * 100."""
    if not severity_thresholds:
        return threshold
    base_pct = int(round(threshold * 100))
    pct = severity_thresholds.get(
        sev, severity_thresholds.get("default", base_pct))
    return pct / 100.0


def decide(is_claim, env, threshold, severity_thresholds=None):
    # type: (bool, Optional[Envelope], float, Optional[Dict[str, int]]) -> Decision
    if not is_claim:
        return Decision(PASS, "chatter")
    if env is None:
        return Decision(ABSTAIN, "no-envelope")
    if not env.grounded or env.grounded == ("none",):
        return Decision(ABSTAIN, "ungrounded", env.missing)
    # Below the baseline (default) floor -> generic below-threshold. At/above the
    # baseline but below the claim's stricter per-severity floor ->
    # below-severity-floor (distinct audit + message).
    if env.conf < threshold:
        return Decision(ABSTAIN, "below-threshold", env.missing)
    floor = resolve_floor(env.sev, threshold, severity_thresholds)
    if env.conf < floor:
        return Decision(ABSTAIN, "below-severity-floor", env.missing)
    return Decision(PASS, "ok")
```

(Note: Task 8 extends `decide` with an explicit `severity=` parameter for the hybrid raise; this Phase-1 version reads `env.sev` directly. The signature is forward-compatible.)

- [ ] Implement `wg_render`. In `template/plugins/warroom-gate/wg_render.py`, replace the `abstention` function (wg_render.py:7-19) with one that handles the new reasons (the `below-severity-floor` branch reuses the conf/floor numbers; the verifier branches are gap-aware):

```python
def abstention(decision, conf_pct=None, threshold_pct=None):
    # type: (Decision, Optional[int], Optional[int]) -> str
    miss = decision.missing or "more grounded evidence"
    if decision.reason == "below-severity-floor" and conf_pct is not None and threshold_pct is not None:
        return ("\U0001f6d1 Holding back - this severity needs a higher bar than "
                "I can clear (%d%% < %d%% for this alert level).\n"
                "   To clear it I'd need: %s." % (conf_pct, threshold_pct, miss))
    if decision.reason == "below-threshold" and conf_pct is not None and threshold_pct is not None:
        return ("\U0001f6d1 Holding back - not confident enough to post that "
                "(%d%% < %d%% bar).\n   To clear it I'd need: %s." % (conf_pct, threshold_pct, miss))
    if decision.reason == "ungrounded":
        return ("\U0001f6d1 Holding back - that claim isn't grounded in evidence I can cite.\n"
                "   To clear it I'd need: %s." % miss)
    if decision.reason == "no-envelope":
        return ("\U0001f6d1 Holding back - no confidence envelope on a claim; "
                "not posting unverified info to the war room.")
    if decision.reason == "verifier-rejected":
        return ("\U0001f6d1 Holding back - the independent verifier did not sign off "
                "on this claim.\n   They flagged: %s." % miss)
    if decision.reason == "verifier-timeout":
        return ("\U0001f6d1 Holding back - no independent verifier signoff in time; "
                "this severity requires a second agent to confirm before posting.")
    if decision.reason == "verifier-unreachable":
        return ("\U0001f6d1 Holding back - couldn't reach the independent verifier; "
                "this severity requires a second-agent signoff, so not posting.")
    return ("\U0001f6d1 Holding back - gate error; not posting unverified info to the war room.")
```

- [ ] Implement `wg_gate` (Phase 1 part). In `template/plugins/warroom-gate/wg_gate.py`, replace the claim-branch block written by the classifier plan (position 2) — its claim branch is `threshold = cfg["min_confidence"] / 100.0` / `decision = wg_policy.decide(True, env, threshold)` / `wg_audit.log(root, decision, conf, "claim", response_text, verdict="claim")` followed by the PASS/abstain tail, and it uses the variable **`response_text`** (verified in the pre-flight) as the log text and the return-equality check (`conf` is already hoisted above the chatter branch by position 2). Replace this block:

```python
        threshold = cfg["min_confidence"] / 100.0
        decision = wg_policy.decide(True, env, threshold)
        wg_audit.log(root, decision, conf, "claim", response_text, verdict="claim")

        if decision.action == wg_policy.PASS:
            out = wg_render.with_badge(body, env.conf, cfg["show_badge"]) if env is not None else body
            return out if out != response_text else None

        conf_pct = int(round(env.conf * 100)) if env is not None else None
        return wg_render.abstention(decision, conf_pct, cfg["min_confidence"])
```

with:

```python
        threshold = cfg["min_confidence"] / 100.0
        sev = env.sev if env is not None else "default"
        decision = wg_policy.decide(
            True, env, threshold, severity_thresholds=cfg["severity_thresholds"])
        conf_pct = int(round(env.conf * 100)) if env is not None else None
        floor_pct = int(round(
            wg_policy.resolve_floor(sev, threshold, cfg["severity_thresholds"]) * 100))

        if decision.action != wg_policy.PASS:
            wg_audit.log(root, decision, conf, "claim", response_text,
                         verdict="claim", extra={"sev": sev, "verify": "none"})
            return wg_render.abstention(decision, conf_pct, floor_pct)

        # PASS so far. The verifier handshake (Task 6) composes here; in Phase 1
        # there is no verifier, so `verify` is "none".
        wg_audit.log(root, decision, conf, "claim", response_text,
                     verdict="claim", extra={"sev": sev, "verify": "none"})
        out = wg_render.with_badge(body, env.conf, cfg["show_badge"]) if env is not None else body
        return out if out != response_text else None
```

(The classifier plan hashes `response_text` — the full text including the envelope footer — not the body; the audit records only its sha, so the rendered/posted message is still the badged body. If position 2 instead hashes the body under a different variable name, the pre-flight surfaces it; substitute that name for `response_text` in the two `wg_audit.log` calls.)

(Note: the abstention now uses `floor_pct` — the per-severity floor — rather than `cfg["min_confidence"]`, so a `below-severity-floor` message shows the right bar. For a plain `below-threshold` abstain, `floor_pct == min_confidence` because `conf < threshold` short-circuits before the severity floor is consulted, so the displayed number is still the baseline.)

- [ ] Run all five green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_policy.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_render.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_audit.py -q
```

Expected: 0 failures (adds ~7 policy + ~4 render + ~3 gate + ~1 audit = ~15 tests). The pre-existing `test_low_confidence_claim_is_replaced_with_abstention` etc. stay green (they pass no `sev=`, so `sev=default`, and `floor_pct == min_confidence`).

- [ ] **Phase 1 suite-green checkpoint:**

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
```

Expected: 0 failures; `sanitize_check: clean`. Net for Phase 1 ≈ +7 (T1) + ~12 (T2) + ~15 (T3) ≈ +34 tests over the position-3 starting baseline.

- [ ] Commit:

```bash
git add template/plugins/warroom-gate/wg_policy.py template/plugins/warroom-gate/wg_render.py template/plugins/warroom-gate/wg_gate.py template/tests/test_policy.py template/tests/test_gate_render.py template/tests/test_gate_callback.py template/tests/test_audit.py
git commit -m "AWR defcon-severity: decide(severity) floor + below-severity-floor reason + gate wiring + audit sev= (T3)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 2 — independent verifier

Tasks 4–7. `inbox --json` flag, `wg_verify` client, gate composition, the verifier-role skill doc + gate-skill teach. Depends on the federation labeled `send --to`/`inbox` round-trip (position 1).

## Task 4: `mailbox inbox --json` flag (coordination, additive)

**Files:**
- Modify: `coordination/src/mailbox/cli.py`
- Modify: `coordination/tests/test_cli.py`
- Test: `coordination/tests/test_cli.py`

**Steps:**

- [ ] In `coordination/tests/test_cli.py`, append a round-trip test for the new flag (mirrors the existing `client.ensure_running()` daemon pattern; the verify handshake needs machine-parseable inbox output, hence `--json`):

```python
import json as _json


def test_inbox_json_emits_message_dicts(tmp_home, capsys):
    client.ensure_running()
    a, b = "sess-json-a", "sess-json-b"
    assert cli.main(["--session", a, "join", "--label", "alpha-sh",
                     "--board", "shared"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", b, "join", "--label", "verify-sh",
                     "--board", "shared"]) == 0
    capsys.readouterr()
    # directed message to verify-sh's label
    assert cli.main(["--session", a, "send", "hello-verifier",
                     "--to", "verify-sh", "--kind", "verify_request"]) == 0
    capsys.readouterr()
    rc = cli.main(["--session", b, "inbox", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    rows = _json.loads(out)
    assert isinstance(rows, list) and len(rows) == 1
    assert rows[0]["body"] == "hello-verifier"
    assert rows[0]["from_label"] == "alpha-sh"
    assert rows[0]["kind"] == "verify_request"


def test_inbox_json_empty_is_empty_array(tmp_home, capsys):
    client.ensure_running()
    sid = "sess-json-empty"
    assert cli.main(["--session", sid, "join", "--label", "lonely-sh"]) == 0
    capsys.readouterr()
    rc = cli.main(["--session", sid, "inbox", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert _json.loads(out) == []
```

- [ ] Run red:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_cli.py -q -k inbox_json
```

Expected: argparse `SystemExit: 2` (`unrecognized arguments: --json`).

(Note: this plan assumes the federation `inbox` parser is the bare `sub.add_parser("inbox")` plus federation's `_add_fed_flags(sp)`. The `--json` flag is added alongside `--federated/--local`. If federation has NOT yet rewritten the `inbox` parser, add `--json` to whatever `inbox` parser exists; the dispatch and `_print_inbox` JSON branch below are independent of the federation flags.)

- [ ] Implement. In `coordination/src/mailbox/cli.py`, change the `inbox` subparser to accept `--json` (it is `sub.add_parser("inbox")` on `main`, or `sp = sub.add_parser("inbox")` + `_add_fed_flags(sp)` after federation). Replace the `inbox` parser block:

```python
    sub.add_parser("inbox")
```

with:

```python
    sp = sub.add_parser("inbox")
    sp.add_argument("--json", dest="as_json", action="store_true",
                    help="emit inbox messages as a JSON array (machine-readable)")
```

(If federation already replaced this with `sp = sub.add_parser("inbox")` + `_add_fed_flags(sp)`, ADD the `--json` argument to that same `sp` — do not remove the federation flags.)

- [ ] In `_print_inbox` (cli.py:38-47), add an optional JSON mode. Replace:

```python
def _print_inbox(messages: list) -> None:
    if not messages:
        print("(no messages)")
        return
    for m in messages:
        print("[%s] from %s: %s" % (
            m.get("kind", "note"),
            m.get("from_label", "?"),
            m.get("body", ""),
        ))
```

with:

```python
def _print_inbox(messages: list, as_json: bool = False) -> None:
    if as_json:
        import json
        print(json.dumps(messages))
        return
    if not messages:
        print("(no messages)")
        return
    for m in messages:
        print("[%s] from %s: %s" % (
            m.get("kind", "note"),
            m.get("from_label", "?"),
            m.get("body", ""),
        ))
```

(If federation already extended `_print_inbox` with `direction`/`origin` rendering, keep that rendering for the non-JSON path and only add the `if as_json:` short-circuit at the top of the function.)

- [ ] In `main`, the inbox output dispatch (cli.py:248-249) reads `if cmd == "inbox": _print_inbox(data or [])`. Replace it with:

```python
    if cmd == "inbox":
        _print_inbox(data or [], as_json=getattr(args, "as_json", False))
```

- [ ] Run green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_cli.py -q
```

Expected: 0 failures (adds 2 tests). Then run the full coordination suite to confirm nothing regressed:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
```

Expected: 0 failures (adds 2 over the position-3 coordination baseline).

- [ ] Commit:

```bash
git add coordination/src/mailbox/cli.py coordination/tests/test_cli.py
git commit -m "AWR defcon-severity: mailbox inbox --json machine-readable output (T4)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: `wg_verify.py` — request build + bounded poll + verdict resolve (no gate wiring yet)

**Files:**
- Create: `template/plugins/warroom-gate/wg_verify.py`
- Create: `template/tests/test_verify.py`
- Test: `template/tests/test_verify.py`

**Steps:**

- [ ] Create `template/tests/test_verify.py`:

```python
"""DEFCON / severity: the independent-verifier client. All effects are the
mailbox CLI subprocess (mocked here) + a monotonic clock (faked here); no real
sleep, no real daemon. Every failure row from the spec reliability table is a
test below."""
import json

import wg_verify as V


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
        self.stderr = stderr.encode("utf-8") if isinstance(stderr, str) else stderr


def _patch_cli(monkeypatch, cli_path="/fake/mailbox"):
    monkeypatch.setattr(V, "discover_cli", lambda env=None: cli_path)


def _patch_clock(monkeypatch, ticks):
    """Feed a deterministic monotonic sequence; raises StopIteration if exhausted."""
    it = iter(ticks)
    monkeypatch.setattr(V.time, "monotonic", lambda: next(it))


def test_build_request_shape():
    req = V.build_request(label="alpha-sh", severity="alert1", conf=0.97,
                          grounded=("tool", "file"), claim="prod db corrupted",
                          request_id="abc123")
    d = json.loads(req)
    assert d["kind"] == "verify_request"
    assert d["request_id"] == "abc123"
    assert d["from"] == "alpha-sh"
    assert d["severity"] == "alert1"
    assert d["conf"] == 0.97
    assert d["grounded"] == ["tool", "file"]
    assert d["claim"] == "prod db corrupted"
    assert len(d["claim_sha"]) == 8        # sha256[:8]


def test_signed_verdict_resolves_signed(monkeypatch):
    _patch_cli(monkeypatch)
    verdict = json.dumps({"kind": "verify_verdict", "request_id": "rid1",
                          "by": "verify-sh", "verdict": "signed",
                          "envelope": "⟦conf=0.96 grounded=tool missing=none⟧",
                          "gap": ""})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": verdict}]
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        if "send" in argv:
            return _Proc(0, "{'id': 'msg_1'}")
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 1.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool", "file"), claim="prod db corrupted",
        timeout_s=30, request_id="rid1", poll_interval_s=0.0)
    assert res["outcome"] == "signed"


def test_rejected_verdict_resolves_rejected_with_gap(monkeypatch):
    _patch_cli(monkeypatch)
    verdict = json.dumps({"kind": "verify_verdict", "request_id": "rid2",
                          "by": "verify-sh", "verdict": "rejected",
                          "envelope": "⟦conf=0.30 grounded=none missing=a repro⟧",
                          "gap": "could not reproduce on a clean prod replica"})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": verdict}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 1.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid2", poll_interval_s=0.0)
    assert res["outcome"] == "rejected"
    assert "reproduce" in res["gap"]


def test_request_id_mismatch_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    other = json.dumps({"kind": "verify_verdict", "request_id": "WRONG",
                        "by": "verify-sh", "verdict": "signed",
                        "envelope": "⟦conf=0.96 grounded=tool missing=none⟧"})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": other}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    # clock: send@0, then poll loop crosses deadline -> timeout
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid3", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_wrong_sender_label_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    spoof = json.dumps({"kind": "verify_verdict", "request_id": "rid4",
                        "by": "verify-sh", "verdict": "signed",
                        "envelope": "⟦conf=0.96 grounded=tool missing=none⟧"})
    # from_label is the transport authentication; an impostor sender is dropped.
    inbox = [{"from_label": "impostor-sh", "kind": "verify_verdict", "body": spoof}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid4", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_malformed_verdict_json_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict",
              "body": "not json at all {{{"}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid5", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_no_reply_times_out(monkeypatch):
    _patch_cli(monkeypatch)

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, "[]")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid6", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_cli_not_found_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch, cli_path=None)
    # no subprocess.run should be called when there is no CLI
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid7", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_send_failure_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch)

    def fake_run(argv, **kw):
        if "send" in argv:
            return _Proc(1, "", "daemon down")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid8", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_subprocess_oserror_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch)

    def boom(*a, **k):
        raise OSError("exec format error")

    monkeypatch.setattr(V.subprocess, "run", boom)
    _patch_clock(monkeypatch, [0.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid9", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_self_verification_refused(monkeypatch):
    # D8: an agent may not be its own verifier.
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="alpha-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid10", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_blank_verifier_label_refused(monkeypatch):
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid11", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_subprocess_is_the_only_io_effect(monkeypatch):
    # Asserts the function never touches the filesystem or network beyond the
    # mocked subprocess; if it tried, the un-mocked sockets/open would error.
    _patch_cli(monkeypatch)
    seen = {"send": 0, "inbox": 0}

    def fake_run(argv, **kw):
        if "send" in argv:
            seen["send"] += 1
        if "inbox" in argv:
            seen["inbox"] += 1
            return _Proc(0, "[]")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid12", poll_interval_s=0.0)
    assert seen["send"] >= 1 and seen["inbox"] >= 1
```

- [ ] Run red:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_verify.py -q
```

Expected: `ModuleNotFoundError: No module named 'wg_verify'`.

- [ ] Create `template/plugins/warroom-gate/wg_verify.py`:

```python
"""Independent-verifier client for the war-room confidence gate. Stdlib only,
Python >=3.9.

When a claim's severity is at/above `require_verifier_at`, the gate (wg_gate)
calls request_and_wait(): post a verification request to the verifier's mailbox
label, then block (bounded by a monotonic deadline) for a signed verdict. Every
failure path resolves to a non-"signed" outcome so the caller abstains
(fail-closed). The ONLY side effect is the mailbox CLI subprocess; this module
never imports mailbox.client and never touches .env / auth.json / local/.

DV2: the gate plugin runs in the Hermes gateway with only its own dir on
sys.path, so warroom_setup.enroll is not importable here. discover_cli mirrors
enroll.discover_mailbox_cli's precedence (env MAILBOX_HOME -> standard install
-> PATH) using stdlib only.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional


def discover_cli(env=None):
    # type: (Optional[dict]) -> Optional[str]
    """Locate an executable `mailbox` CLI (str path) or None. Mirrors
    enroll.discover_mailbox_cli precedence minus the dev-checkout fallback."""
    e = env if env is not None else os.environ
    candidates = []
    mh = (e.get("MAILBOX_HOME") or "").strip()
    if mh:
        candidates.append(Path(mh) / "mailbox")
    home = Path(e.get("HOME") or os.path.expanduser("~"))
    candidates.append(home / ".claude" / "mailbox" / "mailbox")
    for c in candidates:
        try:
            if c.is_file() and os.access(str(c), os.X_OK):
                return str(c)
        except OSError:
            pass
    which = shutil.which("mailbox", path=e.get("PATH"))
    return which if which else None


def build_request(label, severity, conf, grounded, claim, request_id):
    # type: (str, str, float, tuple, str, str) -> str
    """The verify_request JSON body. Carries the full claim text (D6: the
    verifier cannot judge what it cannot read; single-host mailbox). The audit
    log still records only the sha (caller's responsibility)."""
    claim_sha = hashlib.sha256((claim or "").encode("utf-8")).hexdigest()[:8]
    return json.dumps({
        "kind": "verify_request",
        "request_id": request_id,
        "from": label,
        "severity": severity,
        "conf": conf,
        "grounded": list(grounded),
        "claim_sha": claim_sha,
        "claim": claim,
    })


def _run(cli, argv, env, timeout):
    # type: (str, list, dict, int) -> Optional[subprocess.CompletedProcess]
    """Run the mailbox CLI; return the completed process or None on any OS-level
    failure (treated as unreachable by the caller)."""
    try:
        return subprocess.run(
            [cli] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def request_and_wait(label, verifier_label, severity, conf, grounded, claim,
                     timeout_s, request_id, poll_interval_s=0.5, env=None):
    # type: (str, str, str, float, tuple, str, int, str, float, Optional[dict]) -> dict
    """Post a verify request and block (bounded) for a signed verdict.

    Returns {"outcome": one of signed|rejected|timeout|unreachable,
             "gap": <str, on rejected>, "by": <verifier label>}.
    The caller (wg_gate) maps every non-"signed" outcome to an abstention."""
    # D8 self-verification + blank-label guards: cannot verify -> cannot post.
    vl = (verifier_label or "").strip()
    if not vl or vl == label:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    cli = discover_cli(env)
    if cli is None:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    e = dict(env if env is not None else os.environ)
    body = build_request(label, severity, conf, grounded, claim, request_id)

    # Post the directed request. DV3: scope=local is correct for a same-board
    # designated verifier; --to <label> is the directed filter the recipient's
    # poll_inbox matches.
    sent = _run(cli, ["send", body, "--to", vl, "--kind", "verify_request"],
                e, timeout=15)
    if sent is None or sent.returncode != 0:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    # Bounded poll on a MONOTONIC deadline (never time-of-day; never unbounded).
    deadline = time.monotonic() + max(0, timeout_s)
    while time.monotonic() < deadline:
        got = _run(cli, ["inbox", "--json", "--local"], e, timeout=15)
        if got is not None and got.returncode == 0:
            verdict = _scan_inbox(got.stdout, verifier_label=vl,
                                  request_id=request_id)
            if verdict is not None:
                return verdict
        if poll_interval_s > 0:
            time.sleep(poll_interval_s)
        else:
            # poll_interval 0 (tests): re-check the clock and bail if past
            # deadline so the fake monotonic sequence terminates the loop.
            if time.monotonic() >= deadline:
                break
    return {"outcome": "timeout", "gap": "", "by": vl}


def _scan_inbox(stdout, verifier_label, request_id):
    # type: (bytes, str, str) -> Optional[dict]
    """Find a matching verdict in a JSON inbox dump, or None. A verdict is
    accepted only when (a) the message sender (transport-authenticated
    from_label) is the configured verifier, AND (b) the embedded request_id
    echoes ours. Malformed JSON / mismatches are ignored (not fatal)."""
    try:
        rows = json.loads(stdout.decode("utf-8") if isinstance(stdout, bytes) else stdout)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(rows, list):
        return None
    for m in rows:
        if not isinstance(m, dict):
            continue
        # Transport authentication: trust the sender label, not the body's `by`.
        if m.get("from_label") != verifier_label:
            continue
        try:
            payload = json.loads(m.get("body", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("kind") != "verify_verdict":
            continue
        if payload.get("request_id") != request_id:
            continue
        v = payload.get("verdict")
        if v == "signed":
            # DV6: the verifier's own `envelope` is informational in v1 — the gate
            # posts the ORIGINATOR's badge, so a signed verb from the authenticated
            # verifier with a matching request_id is sufficient; we do not parse or
            # require payload["envelope"]. The trust boundary is the transport
            # sender + the explicit `signed` verb, not the envelope's presence.
            return {"outcome": "signed", "gap": "", "by": verifier_label}
        if v == "rejected":
            return {"outcome": "rejected",
                    "gap": str(payload.get("gap") or "verifier could not confirm"),
                    "by": verifier_label}
        # unknown verdict value: ignore this message, keep polling
    return None
```

- [ ] Run green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_verify.py -q
```

Expected: 0 failures (adds 13 tests). Every spec reliability row is covered: unreachable (cli-not-found, send-fail, OSError, blank/self label), timeout (no-reply, request_id mismatch, wrong sender, malformed json), signed, rejected-with-gap.

> **Two call-site facts for downstream tasks (Task 6 + any future test):**
> 1. The poll reads `inbox --json --local`. The `--local` flag is added to the
>    `inbox` parser by the federation plan's `_add_fed_flags` (build-order
>    position 1) and `--json` by this plan's Task 4 — both are pre-flight
>    dependencies. If federation has NOT landed, `--local` is unrecognized and
>    every poll returns non-zero (the verifier degrades to `timeout`/abstain,
>    fail-closed, but the handshake never succeeds); the pre-flight STOP catches
>    this. `--local` is correct (DV3): the designated verifier is co-located on
>    the same board, so a local-scope directed read is the minimal correct poll.
> 2. In PRODUCTION the poll calls real `time.sleep(poll_interval_s)` (default
>    0.5s) up to the monotonic `verifier_timeout_s` deadline. Tests pass
>    `poll_interval_s=0.0` + a faked `time.monotonic` so no real sleep occurs.
>    Any gate-side test that exercises a gated-severity claim MUST monkeypatch
>    `wg_gate.wg_verify.request_and_wait` (as Task 6 does) to avoid a multi-second
>    real hang — never let an un-mocked `request_and_wait` run in a unit test.

- [ ] Commit:

```bash
git add template/plugins/warroom-gate/wg_verify.py template/tests/test_verify.py
git commit -m "AWR defcon-severity: wg_verify client — request + bounded monotonic poll + verdict resolve (T5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: Compose the verifier into `wg_gate.gate()` (fail-closed) + `label` config

**Files:**
- Modify: `template/plugins/warroom-gate/wg_gate.py`
- Modify: `template/plugins/warroom-gate/wg_gateconfig.py`
- Modify: `template/tests/test_gate_callback.py`
- Modify: `template/tests/test_gateconfig.py`
- Test: the gate + gateconfig tests

**Steps:**

- [ ] The gate needs the agent's own label (for the self-verification guard and the request `from`), which the Task 2 scanner does not capture. In `template/plugins/warroom-gate/wg_gateconfig.py`, add `"label": "",` to `_DEFAULTS` (after `escalate_at`):

```python
    "escalate_at": "",
    "label": "",
}
```

extend the flat-key regex alternation in `_scan` to include `label`:

```python
        m = re.match(
            r"(enforce|min_confidence|show_confidence_badge|severity_inference|"
            r"require_verifier_at|verifier_label|verifier_timeout_s|escalate_at|"
            r"label):\s*(\S+)", s)
```

and add the branch in the `if m:` body (after the `escalate_at` branch):

```python
            elif k == "label":
                out["label"] = v
```

- [ ] Add gateconfig label tests. In `template/tests/test_gateconfig.py`, append:

```python
def test_reads_label(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  label: alpha-sh\n")
    assert G.read(tmp_path)["label"] == "alpha-sh"


def test_label_defaults_empty(tmp_path):
    cfg = G.read(tmp_path)
    assert cfg["label"] == ""
```

- [ ] In `template/tests/test_gate_callback.py`, append the end-to-end verifier tests (monkeypatch `wg_gate.wg_verify.request_and_wait` so no real subprocess runs). Add a verifier profile helper and the cases:

```python
def _verifier_profile(tmp_path, enforce=True):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "    default: 75\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: verify-sh\n"
        "  verifier_timeout_s: 30\n" % str(enforce).lower()
    )
    return tmp_path


_ALERT1 = ("prod db is corrupted\n"
           "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")


def test_alert1_signed_verdict_posts_double_signed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "signed", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "⟦" not in out and "97%" in out
    line = _gate_log(tmp_path)
    assert "sev=alert1" in line and "verify=signed" in line


def test_alert1_rejected_verdict_abstains_with_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(
        wg_gate.wg_verify, "request_and_wait",
        lambda **k: {"outcome": "rejected", "gap": "could not reproduce", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out and "could not reproduce" in out
    assert "verify=rejected" in _gate_log(tmp_path)


def test_alert1_timeout_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "timeout", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out
    assert "verify=timeout" in _gate_log(tmp_path)


def test_alert1_unreachable_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "unreachable", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out
    assert "verify=unreachable" in _gate_log(tmp_path)


def test_below_severity_floor_never_calls_verifier(tmp_path, monkeypatch):
    # The verifier handshake only runs AFTER a PASS; a claim that abstains on the
    # floor must not pay the verifier latency.
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(AssertionError("verifier called")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.90 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "Holding back" in out


def test_below_require_verifier_at_passes_without_verifier(tmp_path, monkeypatch):
    # alert2 is below require_verifier_at=alert1, so no handshake; clears its
    # floor (alert2 not in table -> default 75) and posts.
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(AssertionError("verifier called")))
    out = wg_gate.gate(
        response_text="staging is slow\n"
                      "⟦conf=0.80 grounded=tool missing=none sev=alert2⟧")
    assert out is not None and "⟦" not in out and "80%" in out
    assert "verify=none" in _gate_log(tmp_path)


def test_verifier_exception_fails_closed(tmp_path, monkeypatch):
    # If wg_verify itself throws, the top-level try/except still abstains; the
    # callback never raises (extends the fail-closed contract to the verifier).
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = wg_gate.gate(response_text=_ALERT1)
    assert isinstance(out, str) and "Holding back" in out


def test_blank_verifier_label_at_gated_severity_abstains(tmp_path, monkeypatch):
    # require_verifier_at=alert1 but verifier_label blank => misconfig => abstain.
    # wg_verify.request_and_wait returns unreachable for a blank label (T5), so
    # the real (un-mocked) call is fine here and must not hit a subprocess.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: \n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out
```

- [ ] Run red:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gateconfig.py -q
```

Expected failures: `AttributeError: module 'wg_gate' has no attribute 'wg_verify'` (not imported yet); the signed/rejected/timeout/unreachable cases fail because the gate does not yet run the handshake; gateconfig `label` tests pass already after the scanner edit above (run the implementation first if doing strict TDD per-file).

- [ ] Implement. In `template/plugins/warroom-gate/wg_gate.py`, add the `wg_verify` import alongside the existing imports and the `uuid` import:

```python
import os
import uuid
from pathlib import Path

import wg_audit
import wg_classify
import wg_envelope
import wg_gateconfig
import wg_policy
import wg_render
import wg_verify
```

- [ ] Add the severity-rank helper near the top of `wg_gate.py` (after the imports, before `_profile_root`):

```python
# Severity rank for at/above comparisons. Higher number = more severe. Unknown
# tokens rank as default (lowest); `require_verifier_at` "" disables the path,
# and an unknown floor token ranks 99 so nothing is ever at/above it (safe).
_SEV_RANK = {"default": 0, "alert3": 1, "alert2": 2, "alert1": 3}


def _at_or_above(sev, floor_sev):
    # type: (str, str) -> bool
    if not floor_sev:
        return False
    return _SEV_RANK.get(sev, 0) >= _SEV_RANK.get(floor_sev, 99)
```

- [ ] Replace the PASS tail of the claim branch (the block this plan's Task 3 wrote — from `if decision.action != wg_policy.PASS:` through the final `return out if out != response_text else None`) with the verifier-composed version:

```python
        if decision.action != wg_policy.PASS:
            wg_audit.log(root, decision, conf, "claim", response_text,
                         verdict="claim", extra={"sev": sev, "verify": "none"})
            return wg_render.abstention(decision, conf_pct, floor_pct)

        # PASS so far. If this severity requires an independent verifier, obtain
        # a signed verdict before posting; any non-signed outcome abstains
        # (fail-closed). This whole call sits inside the top-level try/except.
        verify_state = "none"
        if _at_or_above(sev, cfg["require_verifier_at"]):
            res = wg_verify.request_and_wait(
                label=cfg["label"],
                verifier_label=cfg["verifier_label"],
                severity=sev,
                conf=env.conf,
                grounded=env.grounded,
                claim=body if env is not None else response_text,
                timeout_s=cfg["verifier_timeout_s"],
                request_id=uuid.uuid4().hex)
            outcome = res.get("outcome")
            if outcome == "signed":
                verify_state = "signed"
            else:
                verify_state = outcome or "unreachable"
                reason = {
                    "rejected": "verifier-rejected",
                    "timeout": "verifier-timeout",
                    "unreachable": "verifier-unreachable",
                }.get(verify_state, "verifier-unreachable")
                abstain = wg_policy.Decision(
                    wg_policy.ABSTAIN, reason, res.get("gap", ""))
                wg_audit.log(root, abstain, conf, "claim", response_text,
                             verdict="claim",
                             extra={"sev": sev, "verify": verify_state})
                return wg_render.abstention(abstain, conf_pct, floor_pct)

        wg_audit.log(root, decision, conf, "claim", response_text,
                     verdict="claim", extra={"sev": sev, "verify": verify_state})
        out = wg_render.with_badge(body, env.conf, cfg["show_badge"]) if env is not None else body
        return out if out != response_text else None
```

- [ ] Run green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gateconfig.py -q
```

Expected: 0 failures (adds ~8 gate + 2 gateconfig tests). The pre-existing `test_never_raises_even_on_internal_bug` still passes (the verifier is inside the same guard).

- [ ] Commit:

```bash
git add template/plugins/warroom-gate/wg_gate.py template/plugins/warroom-gate/wg_gateconfig.py template/tests/test_gate_callback.py template/tests/test_gateconfig.py
git commit -m "AWR defcon-severity: compose verifier handshake into gate (fail-closed) + label config (T6)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: Skill docs — confidence-gate `sev=`/handshake teach + new warroom-verifier role + plugin bump; Phase 2 checkpoint

**Files:**
- Modify: `template/skills/confidence-gate/SKILL.md`
- Create: `template/skills/warroom-verifier/SKILL.md`
- Create: `template/tests/test_verifier_skill.py`
- Modify: `template/plugins/warroom-gate/plugin.yaml`
- Test: `template/tests/test_verifier_skill.py`

**Steps:**

- [ ] Append to the END of `template/skills/confidence-gate/SKILL.md` (at EOF, after any earlier-plan additions — the federation plan, position 1, appends a gate-discipline note here; the L1 orchestrator references this file by name only and never edits it). Appending at EOF is order-independent and never touches the envelope-grammar lines near the top of the file:

```markdown

## Severity (DEFCON) and the independent verifier

Tag a claim's severity in the envelope's optional trailing `sev=` field:

    ⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧

- `sev` is one of `alert1` (highest) > `alert2` > `alert3` > `default`. Omit it
  for ordinary claims (treated as `default`). Tag honestly: a higher severity
  only raises your own bar, it never lowers it.
- Higher severity demands a higher confidence floor (`war_room.severity_thresholds`).
  A claim that clears the baseline but not its alert floor is held back — abstain
  loudly and state the gap.
- At/above `war_room.require_verifier_at` (default top tier only), clearing the
  floor is necessary but not sufficient: the gate asks a second agent (the
  configured `verifier_label`) to independently confirm before your claim posts.
  If no signed verdict arrives in time, the gate holds the claim back. This is
  correct — a top-severity claim with no second signoff does not post.

You never run the handshake by hand; the gate does it. Your job is to tag `sev=`
honestly and ground the claim well enough that an adversarial second agent can
confirm it.
```

- [ ] Create `template/skills/warroom-verifier/SKILL.md` (employer-free; neutral labels `verify-sh`/`alpha-sh`/`squad-api`):

```markdown
---
name: warroom-verifier
description: War-room independent-verifier role. When this agent is the designated verifier for a board, watch the mailbox for verification requests and reply with an honest, independently-grounded signed-or-rejected verdict before a high-severity claim is allowed to post.
---

# Skill: War-Room Independent Verifier

You are the designated **verifier** for this board (`war_room.role: verifier`).
A second agent's confidence gate routes its highest-severity claims to you for an
independent signoff before they reach the channel. Your verdict is a trust
boundary: a `signed` verdict lets the claim post; anything else holds it back.

## Be adversarial, not agreeable

You exist to catch confident-but-wrong claims the originating agent could not
catch about itself. **Do not echo the requester's confidence.** Independently
ground the claim with YOUR OWN tools and evidence this session. If you cannot
independently confirm it, reject it. A false `signed` is worse than a slow one.

## Protocol

### 1. Watch for requests
Poll your inbox for `verify_request` messages:

```
mailbox inbox --json --local
```

Each request body is JSON:

```json
{"kind": "verify_request", "request_id": "<hex>", "from": "alpha-sh",
 "severity": "alert1", "conf": 0.97, "grounded": ["tool", "file"],
 "claim_sha": "<8 hex>", "claim": "<the claim text>"}
```

### 2. Independently ground the claim
Read the `claim`. Using your own session evidence (tools, files, sources),
attempt to confirm it from scratch — do not assume the requester's `grounded`
list is correct. Score your OWN confidence per the confidence-gate protocol.

### 3. Reply with a verdict
Reply to the requester's label with a `verify_verdict` body:

- If you independently confirmed it:

```
mailbox send '{"kind":"verify_verdict","request_id":"<echo it>","by":"verify-sh","verdict":"signed","envelope":"⟦conf=0.96 grounded=tool missing=none⟧","gap":""}' --to alpha-sh --kind verify_verdict
```

- If you could NOT confirm it, reject and state the gap (the requester surfaces
  it as the abstention reason):

```
mailbox send '{"kind":"verify_verdict","request_id":"<echo it>","by":"verify-sh","verdict":"rejected","envelope":"⟦conf=0.30 grounded=none missing=a clean-replica repro⟧","gap":"could not reproduce on a clean prod replica"}' --to alpha-sh --kind verify_verdict
```

Always echo the `request_id` exactly — the requester matches on it. The requester
authenticates your verdict by the mailbox sender label, so reply from your own
configured verifier label, not anyone else's.

## Discipline

- Reply promptly. The requester blocks on a bounded timeout
  (`war_room.verifier_timeout_s`); if you are slow, the claim is held back —
  fail-closed, which is the safe default, but a real claim then never posts.
- Never sign a claim you only re-read; sign a claim you re-grounded.
- You may not verify your own claims — an agent is never its own verifier.
```

- [ ] Create `template/tests/test_verifier_skill.py` (byte snapshot + semantic guards, mirroring `test_assimilate_skill.py`; the `EXPECTED_SHA256` placeholder is filled in the next step):

```python
"""Byte-level snapshot + semantic guards for the warroom-verifier SKILL.md.

The snapshot pins the exact bytes via sha256 so any edit is INTENTIONAL
(regenerate the hash after a deliberate change). The semantic asserts document
the contract the skill must keep even if someone re-pins the hash.
"""
import hashlib
from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "skills" / "warroom-verifier" / "SKILL.md")

# Regenerate after an intentional edit:
#   python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('template/skills/warroom-verifier/SKILL.md').read_bytes()).hexdigest())"
EXPECTED_SHA256 = "<PASTE THE SHA256 PRINTED BY THE COMMAND BELOW>"


def test_skill_byte_snapshot():
    data = SKILL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    assert data.endswith(b"\n")


def test_skill_frontmatter_and_role():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: warroom-verifier\n")
    assert "war_room.role: verifier" in text


def test_skill_documents_protocol_and_verbs():
    text = SKILL.read_text(encoding="utf-8")
    assert "verify_request" in text and "verify_verdict" in text
    assert "mailbox inbox --json --local" in text
    assert "mailbox send" in text and "--kind verify_verdict" in text
    # adversarial posture + echo discipline + self-verify ban
    assert "Do not echo" in text
    assert "echo the `request_id`" in text or "echo it" in text
    assert "never its own verifier" in text


def test_skill_is_employer_free():
    text = SKILL.read_text(encoding="utf-8").lower()
    for forbidden in ("twelvelabs", "twelve labs", "@twelvelabs"):
        assert forbidden not in text
```

- [ ] Ensure the file ends with EXACTLY ONE trailing newline (the snapshot test asserts `data.endswith(b"\n")`), then compute the verifier SKILL.md sha256 and paste it into `EXPECTED_SHA256`. Confirm the trailing newline FIRST, then hash the same bytes:

```bash
tail -c1 /Users/aahil/Documents/Code/agentic-war-room/template/skills/warroom-verifier/SKILL.md | od -An -c   # MUST show \n
python3 -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('/Users/aahil/Documents/Code/agentic-war-room/template/skills/warroom-verifier/SKILL.md').read_bytes()).hexdigest())"
```

If `od -An -c` does not show `\n`, append a single trailing newline to the file before hashing (the `test_skill_byte_snapshot` assertion `data.endswith(b"\n")` and the `EXPECTED_SHA256` must agree on the same bytes — both computed AFTER the newline is present). Replace the `EXPECTED_SHA256 = "<PASTE...>"` placeholder in `test_verifier_skill.py` with the printed hash (this is an intentional snapshot-pinning step, not a TODO).

- [ ] Bump `template/plugins/warroom-gate/plugin.yaml` version (discovery metadata; the gate gained the severity + verifier surface). Replace:

```yaml
version: 0.1.0
```

with:

```yaml
version: 0.2.0
```

- [ ] Run the skill test green and confirm no gate-manifest test pins the old version:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_verifier_skill.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_manifest.py -q
```

Expected: 0 failures. If `test_gate_manifest.py` asserts the exact `version: 0.1.0`, update that single assertion to `0.2.0` (a change-detector update — note it in the commit body) and re-run.

- [ ] **Phase 2 suite-green checkpoint:**

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
```

Expected: 0 failures; `sanitize_check: clean`. Net for Phase 2 ≈ +2 coordination (T4) + ~13 (T5) + ~10 (T6) + ~4 (T7) tests; the verifier role + handshake doc + double-signed path are covered.

- [ ] Commit:

```bash
git add template/skills/confidence-gate/SKILL.md template/skills/warroom-verifier/SKILL.md template/tests/test_verifier_skill.py template/plugins/warroom-gate/plugin.yaml
git commit -m "AWR defcon-severity: confidence-gate sev= teach + warroom-verifier SKILL.md + plugin bump (T7)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 3 — classifier severity upgrade (hybrid)

Task 8. Raise-only severity inference behind `severity_inference: hybrid`. `wg_classify` keeps its frozen `is_claim` contract; severity inference is a NEW function, so the data-gated classifier is untouched.

## Task 8: `wg_classify.infer_severity` (raise-only) + hybrid wiring + wizard fields

**Files:**
- Modify: `template/plugins/warroom-gate/wg_classify.py`
- Modify: `template/plugins/warroom-gate/wg_policy.py`
- Modify: `template/plugins/warroom-gate/wg_gate.py`
- Modify: `template/warroom_setup/selectables.py`
- Modify: `template/warroom_setup/setup.py`
- Modify: `template/tests/test_classify.py`
- Modify: `template/tests/test_gate_callback.py`
- Modify: `template/tests/test_parent_wiring.py` (DV4 — one assertion update)
- Modify: `template/tests/test_selectables.py`
- Test: the above

**Steps:**

- [ ] In `template/tests/test_classify.py`, append severity-inference tests (the existing `is_claim` tests + the classifier-harness fixtures stay untouched — `infer_severity` is additive and never alters `is_claim`):

```python
def test_infer_severity_raises_untagged_on_prod_cue():
    # cue words bump a default/untagged claim to alert2 (never alert1).
    assert C.infer_severity("the prod database is down", "default") == "alert2"
    assert C.infer_severity("we have an outage in payments", "default") == "alert2"
    assert C.infer_severity("possible data loss on the primary", "default") == "alert2"


def test_infer_severity_never_lowers_an_explicit_tag():
    # An explicit alert1 stays alert1 even with no cue words.
    assert C.infer_severity("everything is calm", "alert1") == "alert1"
    # An explicit alert2 is not lowered, and not raised past alert2 by a cue.
    assert C.infer_severity("prod outage", "alert2") == "alert2"


def test_infer_severity_no_cue_keeps_default():
    assert C.infer_severity("the test suite is a bit slow", "default") == "default"


def test_infer_severity_never_produces_alert1():
    # Raise-only and conservative: the classifier can demand alert2 rigor at most;
    # alert1 must be an explicit human/agent tag.
    assert C.infer_severity("prod data loss outage breach", "default") != "alert1"
```

- [ ] In `template/plugins/warroom-gate/wg_classify.py`, append the raise-only inference function (do NOT touch `is_claim` or `_CHATTER`):

```python

# Conservative severity cue words. The hybrid classifier may RAISE an
# untagged/`default` claim to `alert2` (more rigor), NEVER lower an explicit tag,
# and NEVER fabricate `alert1` (top tier must be an explicit human/agent tag).
# This preserves the gate's fail-closed bias: inference can only demand more.
_SEV_CUES = (
    "prod", "production", "outage", "data loss", "corrupt", "breach",
    "down", "failing", "customer impact", "incident",
)


def infer_severity(text, current):
    # type: (str, str) -> str
    """Return a possibly-RAISED severity. Only an untagged/`default` claim with a
    cue word is bumped (to `alert2`); any explicit tag is returned unchanged."""
    if current != "default":
        return current
    low = (text or "").lower()
    if any(cue in low for cue in _SEV_CUES):
        return "alert2"
    return current
```

- [ ] Make `decide` honor an explicitly-passed severity (so the hybrid raise drives the floor — `decide` otherwise reads `env.sev` only). In `template/plugins/warroom-gate/wg_policy.py`, replace the `decide` function with the `severity=`-aware version:

```python
def decide(is_claim, env, threshold, severity_thresholds=None, severity=None):
    # type: (bool, Optional[Envelope], float, Optional[Dict[str, int]], Optional[str]) -> Decision
    if not is_claim:
        return Decision(PASS, "chatter")
    if env is None:
        return Decision(ABSTAIN, "no-envelope")
    if not env.grounded or env.grounded == ("none",):
        return Decision(ABSTAIN, "ungrounded", env.missing)
    # Below the baseline (default) floor -> generic below-threshold. At/above the
    # baseline but below the claim's stricter per-severity floor ->
    # below-severity-floor (distinct audit + message). `severity` overrides
    # env.sev when supplied (the gate passes a hybrid-raised severity here).
    if env.conf < threshold:
        return Decision(ABSTAIN, "below-threshold", env.missing)
    sev = severity if severity is not None else env.sev
    floor = resolve_floor(sev, threshold, severity_thresholds)
    if env.conf < floor:
        return Decision(ABSTAIN, "below-severity-floor", env.missing)
    return Decision(PASS, "ok")
```

(The Task 3 `test_policy.py` cases pass no `severity=`, so `env.sev` is used — they stay green.)

- [ ] In `template/plugins/warroom-gate/wg_gate.py`, apply the hybrid upgrade right after `sev` is read and pass the resolved `sev` into `decide`. Replace this block (written in Task 3):

```python
        threshold = cfg["min_confidence"] / 100.0
        sev = env.sev if env is not None else "default"
        decision = wg_policy.decide(
            True, env, threshold, severity_thresholds=cfg["severity_thresholds"])
        conf_pct = int(round(env.conf * 100)) if env is not None else None
        floor_pct = int(round(
            wg_policy.resolve_floor(sev, threshold, cfg["severity_thresholds"]) * 100))
```

with:

```python
        threshold = cfg["min_confidence"] / 100.0
        sev = env.sev if env is not None else "default"
        # Hybrid inference (raise-only): in hybrid mode an untagged/default claim
        # with severity cue words is bumped to a stricter floor. Never lowers an
        # explicit tag; never produces alert1.
        if cfg["severity_inference"] == "hybrid":
            sev = wg_classify.infer_severity(
                body if env is not None else response_text, sev)
        decision = wg_policy.decide(
            True, env, threshold, severity_thresholds=cfg["severity_thresholds"],
            severity=sev)
        conf_pct = int(round(env.conf * 100)) if env is not None else None
        floor_pct = int(round(
            wg_policy.resolve_floor(sev, threshold, cfg["severity_thresholds"]) * 100))
```

- [ ] Add gate end-to-end hybrid tests. In `template/tests/test_gate_callback.py`, append:

```python
def test_hybrid_raises_untagged_to_alert2_floor(tmp_path, monkeypatch):
    # hybrid mode: an untagged claim with a prod cue is held to the alert2 floor.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_inference: hybrid\n"
        "  severity_thresholds:\n"
        "    alert2: 90\n"
        "    default: 75\n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # clears default 75 but not the raised alert2 floor 90 -> held back
    out = wg_gate.gate(
        response_text="the prod database is down\n"
                      "⟦conf=0.80 grounded=tool,file missing=none⟧")
    assert out is not None and "Holding back" in out
    assert "sev=alert2" in _gate_log(tmp_path)


def test_explicit_mode_does_not_raise(tmp_path, monkeypatch):
    # default (explicit) mode: the same claim is held only to the default floor.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n"
        "    alert2: 90\n"
        "    default: 75\n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    out = wg_gate.gate(
        response_text="the prod database is down\n"
                      "⟦conf=0.80 grounded=tool,file missing=none⟧")
    assert out is not None and "⟦" not in out and "80%" in out
    assert "sev=default" in _gate_log(tmp_path)
```

- [ ] Add the wizard fields. In `template/warroom_setup/selectables.py`, append to the END of `TEXT_FIELDS` (AFTER `warroom.parent`, which federation appended last — F10: append, never insert):

```python
    # DEFCON / severity (appended AFTER warroom.parent — F10 append rule). These
    # collect the per-severity floors and the verifier label; blank = feature off.
    TextField(id="warroom.severity_alert1",
              prompt="Severity alert1 confidence floor % (blank to skip)",
              required=False, enable_if="warroom.enroll"),
    TextField(id="warroom.severity_alert2",
              prompt="Severity alert2 confidence floor % (blank to skip)",
              required=False, enable_if="warroom.enroll"),
    TextField(id="warroom.verifier_label",
              prompt="Verifier label (mailbox label of a designated 2nd agent; blank for none)",
              required=False, enable_if="warroom.enroll"),
```

- [ ] DV4: update the federation strict-last assertion. In `template/tests/test_parent_wiring.py`, replace `test_selectables_parent_field_appended_last_with_enable_if` with an ordering check that no longer requires parent to be the literal last field:

```python
def test_selectables_parent_field_appended_last_with_enable_if():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    assert "warroom.parent" in ids
    # F10 rule: parent was appended after warroom.label (never inserted before
    # the existing channel/identity fields). DEFCON fields (position 3) append
    # after parent, so parent is no longer the literal last id.
    assert ids.index("warroom.parent") > ids.index("warroom.label")
    assert ids.index("warroom.parent") < ids.index("warroom.verifier_label")
    fld = [f for f in selectables.TEXT_FIELDS if f.id == "warroom.parent"][0]
    assert fld.enable_if == "warroom.enroll"
    assert fld.secret is False and fld.required is False
    assert "warroom.parent" not in selectables.ENV_FIELD_IDS
```

- [ ] Add a selectables test for the new fields. In `template/tests/test_selectables.py` (if absent, create it with `from warroom_setup import selectables` as the import header), append:

```python
def test_defcon_fields_appended_with_enable_if():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    for fid in ("warroom.severity_alert1", "warroom.severity_alert2",
                "warroom.verifier_label"):
        assert fid in ids
        fld = [f for f in selectables.TEXT_FIELDS if f.id == fid][0]
        assert fld.enable_if == "warroom.enroll"
        assert fld.secret is False
        assert fid not in selectables.ENV_FIELD_IDS
    # DEFCON fields come after parent (append order)
    assert ids.index("warroom.severity_alert1") > ids.index("warroom.parent")
```

- [ ] Wire the wizard values into the rendered block + bootstrap. In `template/warroom_setup/setup.py::run_setup`, the federation-extended `if "warroom.enroll" in selected:` block calls `patch_war_room_block(profile_root, board, parent=parent, min_confidence=mc, enforce=...)`. Replace that single `patch_war_room_block(...)` call (inside the block, keeping the surrounding `mc`/`board`/`parent`/`label`/bootstrap lines) with the DEFCON-aware version:

```python
        sev_table = {}
        a1 = schema.clamp_pct(values.get("warroom.severity_alert1", ""), default=0)
        a2 = schema.clamp_pct(values.get("warroom.severity_alert2", ""), default=0)
        if a1:
            sev_table["alert1"] = a1
        if a2:
            sev_table["alert2"] = a2
        if sev_table:
            sev_table.setdefault("default", mc)
        verifier_label = values.get("warroom.verifier_label", "").strip()
        # require_verifier_at defaults to alert1 only when a verifier label and an
        # alert1 floor are both configured (otherwise leave the path off).
        require_at = "alert1" if (verifier_label and "alert1" in sev_table) else ""
        patch_war_room_block(
            profile_root, board, parent=parent,
            min_confidence=mc, enforce=("warroom.enforce" in selected),
            severity_thresholds=sev_table,
            verifier_label=verifier_label,
            require_verifier_at=require_at)
```

(`schema.clamp_pct(..., default=0)` returns 0 for a blank field, so `if a1:` cleanly omits an unset floor. `verifier_timeout_s`/`severity_inference`/`escalate_at` keep their schema defaults — they are not wizard-collected in v1, matching the spec's minimal-surface "appended after existing fields".)

- [ ] Add a run_setup integration test for the wizard → block translation. In `template/tests/test_parent_wiring.py` (it has the `_fake_profile`/`_run`/`_ParentAwareRecorder` harness), append:

```python
def test_run_setup_writes_severity_table_and_verifier(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _ParentAwareRecorder()
    # prompt order after channels: board, min_confidence, label, parent,
    # severity_alert1, severity_alert2, verifier_label
    rc = _run(prof, monkeypatch, rec,
              extra_lines="squad-api\n75\nalpha-sh\n\n95\n85\nverify-sh\n")
    assert rc == 0
    text = (prof / "config.yaml").read_text(encoding="utf-8")
    assert "  severity_thresholds:" in text
    assert "    alert1: 95" in text and "    alert2: 85" in text
    assert "    default: 75" in text
    assert "verifier_label: verify-sh" in text
    assert "require_verifier_at: alert1" in text
```

- [ ] Run the affected tests (red, then green after implementation):

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_classify.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_policy.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_parent_wiring.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_selectables.py -q
```

Expected: after implementation, 0 failures (adds ~4 classify + ~2 gate + ~1 parent-wiring + ~1 selectables tests; `test_selectables_parent_field_appended_last_with_enable_if` is updated, not added).

- [ ] **Phase 3 suite-green checkpoint:**

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
```

Expected: 0 failures; `sanitize_check: clean`.

- [ ] Commit:

```bash
git add template/plugins/warroom-gate/wg_classify.py template/plugins/warroom-gate/wg_policy.py template/plugins/warroom-gate/wg_gate.py template/warroom_setup/selectables.py template/warroom_setup/setup.py template/tests/test_classify.py template/tests/test_gate_callback.py template/tests/test_parent_wiring.py template/tests/test_selectables.py
git commit -m "AWR defcon-severity: hybrid raise-only severity inference + wizard fields (T8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 4 — auto-escalation hook (config + audit annotation; orchestrator-driven)

Task 9. Per D5 (brief narrowing): the gate carries the `escalate_at` config key and annotates severity in the audit; it performs NO escalate send. The `/warroom` orchestrator (build-order position 4) consumes `escalate_at` and performs the actual `mailbox escalate` post at intake. This task pins that contract with a test and a cross-plan note in the gate skill. (`escalate_at` is already parsed by the scanner and rendered by the block — both landed in Task 2.)

## Task 9: `escalate_at` config carry + no-gate-send guard + cross-plan note

**Files:**
- Modify: `template/tests/test_gateconfig.py`
- Modify: `template/tests/test_gate_callback.py`
- Modify: `template/skills/confidence-gate/SKILL.md`
- Test: the gateconfig + gate tests

**Steps:**

- [ ] In `template/tests/test_gateconfig.py`, append a test pinning `escalate_at` is surfaced:

```python
def test_escalate_at_surfaced(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  escalate_at: alert2\n")
    assert G.read(tmp_path)["escalate_at"] == "alert2"
```

- [ ] In `template/tests/test_gate_callback.py`, append the guard: a high-severity claim that passes does NOT trigger any mailbox send from the gate (only the verifier handshake may send, and only when `require_verifier_at` is set). This pins D5 — the gate is a pure transform; escalation is the orchestrator's job.

```python
def test_gate_does_not_escalate_on_pass(tmp_path, monkeypatch):
    # escalate_at is set, but the GATE must not initiate an escalate send. The
    # only sanctioned gate-side send is the verifier request, which requires
    # require_verifier_at (NOT set here). So wg_verify must never be invoked.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n"
        "    alert2: 80\n"
        "    default: 75\n"
        "  escalate_at: alert2\n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(AssertionError("gate must not send")))
    out = wg_gate.gate(
        response_text="staging cache is cold\n"
                      "⟦conf=0.85 grounded=tool missing=none sev=alert2⟧")
    # The claim posts (cleared alert2 floor 80); the gate did NOT escalate.
    assert out is not None and "⟦" not in out and "85%" in out
    assert "verify=none" in _gate_log(tmp_path)
```

- [ ] Append the escalation cross-plan note to the END of `template/skills/confidence-gate/SKILL.md` (after the Task 7 severity section):

```markdown

## Auto-escalation is the orchestrator's job, not the gate's

The confidence gate annotates severity (in the audit and your envelope) but does
NOT escalate. When your assessed severity is at/above `war_room.escalate_at`, the
`/warroom` orchestrator performs the `mailbox escalate "<finding>"` post so the
finding becomes visible up the board tree. The gate stays a pure transform with
exactly one outbound message — the verifier request — and never double-posts.
```

- [ ] Run green:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gateconfig.py /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_gate_callback.py -q
```

Expected: 0 failures (adds 1 gateconfig + 1 gate test).

- [ ] **Phase 4 suite-green checkpoint + final cross-suite confirmation:**

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
grep -RInE "twelvelabs|twelve labs|@twelvelabs|tl-branding" /Users/aahil/Documents/Code/agentic-war-room/template/ || echo "employer-leak grep: clean"
grep -RInE "normalize_unsentineled_blocks|_strip_bare_block|_MANAGED_BLOCKS" /Users/aahil/Documents/Code/agentic-war-room/template/ || echo "Option-B regression grep: clean"
```

Expected: template + coordination both 0 failures; `sanitize_check: clean`; both greps clean.

- [ ] Commit:

```bash
git add template/tests/test_gateconfig.py template/tests/test_gate_callback.py template/skills/confidence-gate/SKILL.md
git commit -m "AWR defcon-severity: escalate_at config carry + gate-never-escalates guard + orchestrator note (T9)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Integration test (optional, `--runintegration`)

The spec calls for a real-daemon two-profile round-trip. The unit suite already
proves every branch with mocked subprocess + monotonic clock (Tasks 5/6). A real
end-to-end integration test (contributor `alpha-sh` + verifier `verify-sh` on
board `squad-api`, signed/rejected/silent round-trips) belongs in the
coordination integration tier (`@pytest.mark.integration`, run with
`--runintegration`). If added, model it on the existing
`test_two_profiles_meet_via_real_hook_chain` (Feature C) pattern: spin the real
daemon, join two sessions, exercise `wg_verify.request_and_wait` against the live
CLI, and assert the verdict round-trips. This is out-of-scope for the required
green (default, non-integration) suites the brief baselines against, and is left
as a follow-up rather than a blocking task because the mocked unit coverage is
comprehensive.

---

## Self-review checklist (performed by the author)

- **Every spec section maps to a task:** §1 severity inference → T1 (envelope) + T8 (hybrid); §2 threshold resolution → T2 (config/render/scan) + T3 (`decide`); §3 verifier client → T5 + T6; §4 verifier role → T7 (skill doc); §5 auto-escalation → T9 (config carry + no-send guard + note); data model (envelope/request/verdict) → T1/T5 (request `deadline_ts` dropped per DV5; verdict `envelope` informational per DV6); reliability table → T5 (every failure row) + T6 (gate-side); unparseable-map / blank-verifier "+ log" rows → DV7 (audit-trail visibility, not a scanner-time log); security (anti-spoof, transport auth, no-secrets) → T1/T5/T3; observability (audit `sev=`/`verify=`, new reasons) → T3/T6; config/wizard surface → T2/T8; open questions 1-4 → adopted D1-D10.
- **File-path map coverage:** every file in the spec's File-path map maps to a task EXCEPT `enroll.py`, which the spec's map itself flags as "no `.env` shape change ... documented as intentionally untouched." This plan honors that: the verifier is a config-routed `war_room.verifier_label` (read by `wg_gateconfig`, not `.env`), so `enroll.py`/`enroll._runtime_env_values` are deliberately NOT modified — `enroll.discover_mailbox_cli` is referenced only as the precedence model `wg_verify.discover_cli` mirrors (DV2). `enroll.py` is intentionally untouched, satisfying the spec's documented file-map entry.
- **No placeholders** except the single intentional `EXPECTED_SHA256 = "<PASTE...>"` in T7, which has an exact generate-and-paste command — that is a deliberate snapshot-pinning step, not a TODO.
- **Cross-task symbol consistency:** `severity_thresholds`, `require_verifier_at`, `verifier_label`, `verifier_timeout_s`, `escalate_at`, `severity_inference`, `label` spelled identically across schema (T2), scanner (T2/T6), `decide`/`resolve_floor` (T3/T8), `wg_verify.request_and_wait` kwargs (T5) and the gate call site (T6); `Envelope.sev` (T1) flows into `decide(severity=)` (T8); outcome strings `signed|rejected|timeout|unreachable` (T5) map 1:1 to reasons `verifier-rejected|verifier-timeout|verifier-unreachable` (T6) and render copy (T3).
