# AWR Follow-ups + Feature A — Build Order

Date: 2026-06-09. Branch off main → `awr-followups`. Synthesis + Option B plan below; Feature A plan in sibling doc `2026-06-08-awr-feature-a.md`.

Generated via a 3-agent workflow (2 parallel planners + 1 cross-review/synthesizer).

---

## Synthesis (cross-review, unified build order, DoD)

Now I have both plans in full. Let me cross-review.

# Cross-Review

## Option B — issues

1. **Test count math is wrong.** §6 says "net +9" — claims `+4 sentinel + 6 patch_war_room - 1 installer_execute = +9`. That's `+4 + 6 - 1 = 9`, correct arithmetically — BUT §4 also says `test_execute_stages_survive_hermes_yaml_reemit` is *rewritten*, not deleted. Rewriting doesn't change count. So the math holds, but the "rewrites 1" line in §6 reads as if it also subtracts. Tighten the acceptance line: "1 deleted, 1 rewritten in place, net +9." Cite §6 bullet 4 and §8 T4.

2. **Fallback regex eats trailing blank lines that belong to the *next* block.** The continuation `(?:[ \t].*\n|[ \t]*\n)*` greedily consumes blank lines AFTER the bare key span — those blank lines visually belong between blocks but get swallowed into the replaced span. Replacement is `new_body + "\n"`, so you lose the separator between the new sentinelled block and `next_top:`. Plan's `test_fallback_preserves_indented_continuation` doesn't actually assert on the blank-line gap to `next_top`. Either trim trailing blank lines from the match (use a lazy/anchored variant) or emit `new_body + "\n\n"` when consumed-blanks > 0.

3. **`import re` dead-check in §5 is half-done.** Plan says "Check whether `import re` (line 23) has any remaining uses — if not, drop it." That's a runtime decision baked into a plan; should be resolved now by grep, not deferred. Cite §5 third bullet.

## Feature A — issues

1. **§7 vs §3 contradict on `_already_assimilated`.** §3 defines it as "has `_WR_BEGIN` block AND `local/warroom-enroll.json`". §7 risk-1 mitigation says "if a sentinel line exists but `local/warroom-enroll.json` is absent, refuse with exit 4." Those are two different policies for the same state (`sentinel + no enroll.json`): §3 returns False (proceeds), risk-1 returns exit 4. Pick one. Recommend exit 4 — orphan sentinel without enroll state is suspicious.

2. **Step 5c ordering breaks the "no clobber" promise.** §8 step 5d writes walkthrough creds to `.env` AFTER step 5c, which is `enroll.bootstrap` (which itself writes `MAILBOX_BOARD/LABEL` to `.env`). If `bootstrap` fails partway, you've already written war_room + persona + mailbox config + enroll state but never wrote the Discord token. Order should be: walkthrough creds → war_room block → persona → enroll.bootstrap → audit trail. Move 5d before 5c.

3. **Scope creep in risk-3 mitigation.** "have `enroll.bootstrap` return `state.status='ok'` only if … daemon ping … succeeded" — that mutates `enroll.bootstrap`'s contract, which is owned by Feature C / shared-core, not Feature A. Either drop the mitigation (post-flight text-only) or land the bootstrap change in a separate PR. As written, T5 silently inherits a shared-core API change.

# Cross-feature dependency check

**Feature A depends on Option B.** Two load-bearing reasons:

- A's Risk-1 mitigation explicitly worries about sentinel-collision on foreign yaml — the smarter sentinel block (B's fallback re-anchoring) is exactly what makes assimilate safe on a foreign profile whose comments were stripped by any prior tooling.
- A calls `patch_war_room_block` and `patch_mailbox_block` on profiles where sentinels may have been stripped by a Hermes re-emit before assimilate even runs. Without B, those calls duplicate blocks.

**Lock order: Option B first, then Feature A.**

# Unified build order

1. **T1** (B) — `_replace_sentinel_block` signature + fallback branch + both `patch_*_block` call sites + 4 fallback tests in `test_sentinel_replace.py`. Green.
2. **T2** (B) — 6 regression tests in `test_patch_war_room_ext.py`. Green.
3. **T3** (B) — Remove installer workaround: delete `_strip_bare_block`, `normalize_unsentineled_blocks`, `_MANAGED_BLOCKS`, Stage-4 call site, dead `import re`; rewrite reemit test, delete normalize test in `test_installer_execute.py`. Green.
4. **T4** (B) — Full-suite run `pytest template/tests/ -x -q`; confirm net +9. Commit if green-only-after-T3 changes need it (else fold into T3).
5. **T5** (A) — `assimilate.py` with `_classify` + `_detect_channels` + `_already_assimilated` helpers + 3 fixtures + classify tests. No CLI reachability yet.
6. **T6** (A) — CLI subparser + dispatch, dry-run prints classify report.
7. **T7** (A) — Orchestrator steps 1-3 + 5a (war_room) + 5b (persona) + idempotency + `--reconfigure` + exit-3 + exit-2 tests. Resolve §3↔§7 contradiction in favor of exit 4 for orphan sentinel.
8. **T8** (A) — Walkthrough integration (step 4) + `.env` merge (step 5d) — **write creds BEFORE enroll.bootstrap**. Skip-on-existing-creds + `--no-walkthrough` tests.
9. **T9** (A) — `enroll.bootstrap` call (step 5c) + audit trail (5e). Drop the bootstrap-API-mutation from risk-3; post-flight text only.
10. **T10** (A) — `template/skills/assimilate-warroom/SKILL.md` + byte-level snapshot test.
11. **T11** (A) — Exit-code matrix tests + `sanitize_check` on full diff + `MAILBOX_BOARD` overwrite-confirm test.
12. **T12** (A) — `aahil_like` fixture + end-to-end smoke + non-warroom-files byte-identical assertion.

# Definition of done (combined, 8 gates)

1. `pytest template/tests/ -x -q` green; net `+9` from B + new A tests all pass.
2. `grep -r normalize_unsentineled_blocks template/` returns zero hits in code (docs may persist historically).
3. `warroom assimilate <foreign-fixture> --dry-run` exits 0 and writes zero bytes (hash-compare before/after).
4. Double-run `warroom assimilate <fixture> --yes --no-walkthrough` → second run exits 2 without `--reconfigure`; with `--reconfigure` produces zero file-content diff.
5. Smoke: `aahil_like` fixture run leaves all non-warroom files byte-identical; `config.yaml` has exactly one `war_room:` and one `mailbox:` top-level key; `.env` retains pre-existing `DISCORD_BOT_TOKEN` value.
6. Exit code matrix (0/1/2/3/4) all covered by tests.
7. `sanitize_check` clean on full diff; no employer names, no real handles, no real channel IDs in fixtures or new code.
8. Manual: foreign profile assimilate → restart session → `mailbox ps` shows peer (recorded as a manual smoke step in the PR, not gated in CI).

# Estimated wall-clock

- Option B (T1-T4): **2-3 hours**. Mostly tests; the regex and call-site edits are <30 LoC.
- Feature A (T5-T12): **6-8 hours**. ~150-200 LoC orchestrator + 14 unit tests + 3 fixtures + smoke fixture + SKILL.md + sanitization sweep.

**Total: ~1 working day (8-11 hours).** Single dev, sequential. If T5-T12 are parallelized across two devs after B lands (T5+T6 can fan out from T7+T8), shave ~2 hours.

Files referenced (absolute):
- /Users/aahil/Documents/Code/agentic-war-room/template/warroom_setup/setup.py
- /Users/aahil/Documents/Code/agentic-war-room/template/scripts/installer/in_process_orchestrator.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_sentinel_replace.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_patch_war_room_ext.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_installer_execute.py
- /Users/aahil/Documents/Code/agentic-war-room/docs/superpowers/plans/2026-06-08-awr-feature-a.md

---

## Option B Plan — Sentinel YAML-key fallback

I have enough grounding. The plan is concrete and ready.

---

# Plan — Option B: YAML-Key Fallback in `_replace_sentinel_block`

## 1. Goal
Make `setup._replace_sentinel_block` re-anchor onto a bare top-level YAML key span when sentinels are absent, so PyYAML re-emits no longer cause duplicate `war_room:`/`mailbox:` blocks — and retire the installer's `normalize_unsentineled_blocks` workaround.

## 2. Files / functions to modify
- `template/warroom_setup/setup.py`
  - `_replace_sentinel_block` (lines 55–74) — add `yaml_key=None` parameter, add fallback branch.
  - `patch_war_room_block` (line 197) — pass `yaml_key="war_room"`.
  - `patch_mailbox_block` (line 233) — pass `yaml_key="mailbox"`.
- `template/scripts/installer/in_process_orchestrator.py`
  - Delete `_strip_bare_block` (lines 173–181), `normalize_unsentineled_blocks` (lines 184–213), the `_MANAGED_BLOCKS` constant (lines 51–54) if unused elsewhere, the call site at line 345 and surrounding comment (lines 342–345), and the `import re` if it becomes dead.
- `template/tests/test_installer_execute.py`
  - Delete `test_normalize_strips_only_bare_unsentineled_blocks` (lines 304–344) and rewrite `test_execute_stages_survive_hermes_yaml_reemit` to skip the normalize call (lines 277–301).
- `template/tests/test_sentinel_replace.py` — new fallback tests appended.
- `template/tests/test_patch_war_room_ext.py` — add the four regression cases.

## 3. Code patches

**setup.py — replace lines 55–74:**

```python
def _replace_sentinel_block(text, begin, end, new_body, yaml_key=None):
    # type: (str, str, str, str, Optional[str]) -> str
    """Replace the region delimited by the `begin`/`end` sentinel LINES with
    `new_body`. If sentinels are absent AND `yaml_key` is supplied, fall back to
    matching the bare top-level key span (`^<key>:` line plus indented/blank
    continuation lines, up to the next top-level key or EOF) — this re-sentinels
    a YAML block whose comments were stripped by a PyYAML re-emit. Else append.

    Anchored on a bare mapping header (`^key:`) so `mailboxes_other:` does not
    match `mailbox`. Replacement is supplied via a function to avoid backref
    interpretation of `\\g`/`\\1` in `new_body`.
    """
    pattern = re.compile(
        r"^%s$.*?^%s$" % (re.escape(begin), re.escape(end)),
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(lambda _m: new_body, text)
    if yaml_key:
        bare = re.compile(
            r"(?m)^%s:[ \t]*\n(?:[ \t].*\n|[ \t]*\n)*" % re.escape(yaml_key)
        )
        if bare.search(text):
            replaced = bare.sub(lambda _m: new_body + "\n", text, count=1)
            return replaced if replaced.endswith("\n") else replaced + "\n"
    if text.strip():
        return text.rstrip("\n") + "\n\n" + new_body + "\n"
    return new_body + "\n"
```

(Add `from typing import Optional` to the existing typing import at line 14 if not already present — it is.)

**setup.py line 197 (war_room):**
```python
new = _replace_sentinel_block(text, _WR_BEGIN, _WR_END, block, yaml_key="war_room")
```

**setup.py line 233 (mailbox):**
```python
new = _replace_sentinel_block(text, _MB_BEGIN, _MB_END, block, yaml_key="mailbox")
```

Rationale on the regex: `(?m)^key:[ \t]*\n` requires the key to start a line and end the line (so `war_room_other:` doesn't match — it has trailing chars before newline). Continuation `(?:[ \t].*\n|[ \t]*\n)*` consumes indented content and blank lines but stops at the next non-indented non-blank line (next top-level key) or EOF.

## 4. Tests

**`template/tests/test_sentinel_replace.py`** — append 4 tests:
- `test_fallback_replaces_bare_yaml_key_block` — text `"top: 1\nmailbox:\n  board: shared\n  label: x\n\nother: 2\n"`; call `_replace_sentinel_block(text, MB_B, MB_E, new_mb, yaml_key="mailbox")`; assert exactly one `mailbox:` line, sentinels present, `top: 1` and `other: 2` preserved.
- `test_fallback_does_not_match_lookalike_key` — input has `mailboxes_other:` only; assert it is NOT matched and the call appends (test that `mailboxes_other:` text survives untouched and one new sentinelled `mailbox:` block is appended).
- `test_fallback_preserves_indented_continuation` — bare block with nested map + blank line inside (`mailbox:\n  board: shared\n  nested:\n    deep: 1\n\n  more: 2\nnext_top: 3\n`); fallback strips the whole bare span and stops at `next_top`.
- `test_fallback_ignored_when_sentinels_present` — sentinelled block AND a stray bare `mailbox:` (pathological); since sentinels match first, only the sentinelled block is replaced; bare one survives (caller's responsibility, but documents behavior). Assert count of `mailbox:` lines is still 2 — establishes that fallback is strictly secondary.

**`template/tests/test_patch_war_room_ext.py`** — add a new test class `TestPatchYamlKeyFallback` with:
- `test_war_room_sentinels_intact_in_place_update` — write a sentinelled `war_room:` block to `config.yaml`, call `patch_war_room_block(prof, "shared", min_confidence=70)`, assert one `war_room:` line, `board: shared`, `min_confidence: 70`.
- `test_war_room_sentinels_stripped_block_present_resentineled` — write a config where sentinels have been removed but `war_room:` survives; one patch call; assert exactly one `war_room:` line AND `# >>> warroom-managed` header present.
- `test_war_room_block_absent_appends` — empty config.yaml; patch; assert one block appended with sentinels.
- `test_mailbox_re_sentinels_after_simulated_reemit` — copy `template/config.yaml`, strip ALL `# ` comment lines (mimic PyYAML re-emit), call `patch_mailbox_block(prof, board="shared", label="alpha-sh")` ONCE; assert one `mailbox:` line, sentinels back, no `mailbox:` duplication.
- `test_mailbox_lookalike_not_clobbered` — config with bare `mailbox:` AND `mailboxes_other:` keys; patch mailbox; assert `mailboxes_other:` survives verbatim, mailbox count is 1.
- `test_double_patch_idempotent_after_reemit` — strip sentinels, patch twice; final state has exactly one block.

**`template/tests/test_installer_execute.py`** — rewrite `test_execute_stages_survive_hermes_yaml_reemit` (lines 277–301) to omit the `orch.normalize_unsentineled_blocks(cfg)` call entirely (proves shared-core handles it now); delete `test_normalize_strips_only_bare_unsentineled_blocks` (lines 304–344) entirely. Existing assertions on `_key_count == 1` and sentinel presence remain.

## 5. Removal of installer workaround
In `template/scripts/installer/in_process_orchestrator.py`:
- Delete lines 51–54 (`_MANAGED_BLOCKS` dict) if not referenced elsewhere — grep confirms it's only used in `normalize_unsentineled_blocks`.
- Delete lines 170–213 (`_strip_bare_block`, `normalize_unsentineled_blocks`, and the section banner).
- At Stage 4 (lines 341–345), delete the comment block (lines 342–344) and the `normalize_unsentineled_blocks(...)` call (line 345). Keep the `patch_war_room_block` / `patch_mailbox_block` calls.
- Check whether `import re` (line 23) has any remaining uses — if not, drop it.

In `template/tests/test_installer_execute.py`:
- Delete the two tests cited above. No other test file references the workaround (grep confirmed).

## 6. Acceptance criteria
Run `python -m pytest template/tests/ -x -q` from repo root. Expected (literal):
- `test_sentinel_replace.py` — was 4 tests, now 8 tests, all pass.
- `test_patch_war_room_ext.py` — gains 6 new tests, all pass.
- `test_installer_execute.py` — drops 1 test, rewrites 1; remaining suite passes.
- `test_installer_e2e.py`, `test_installer_headless.py`, `test_installer_subprocess.py`, `test_installer_sidecar.py`, `test_installer_rollback.py`, `test_installer_uninstall.py` — all still pass (workaround removal is behaviorally transparent).
- Final summary line: `==== N passed in M.MMs ====` with N == prior_count + 9 (6 added in patch_war_room_ext + 4 added in sentinel_replace – 1 deleted in installer_execute = +9).
- `grep -r normalize_unsentineled_blocks template/ docs/` returns zero hits in code paths (docs may still cite it historically).

## 7. Risks / unknowns
1. **Lookalike key edge case** — `war_room_other:` shouldn't match `war_room:`. The `^key:[ \t]*\n` anchor requires the very next char after the key to be `:` then only whitespace+newline. A key like `war_roomy:` is rejected because `:` doesn't immediately follow `war_room`. Verified by `test_fallback_does_not_match_lookalike_key`.
2. **Block followed by another indented block** — if Hermes' YAML re-emit produces `mailbox:\n  ...\nwar_room:\n  ...` (no blank between), our continuation regex `[ \t].*` correctly stops at `war_room:` (no leading space). Verified by `test_execute_stages_survive_hermes_yaml_reemit`.
3. **Persisted historic configs** — if any user has a config.yaml with BOTH a sentinelled and a stray bare `mailbox:` (from the bug pre-Feature-B), sentinel match wins and the bare one persists. Acceptable — the duplicate is pre-existing user data; the installer's prior `normalize_unsentineled_blocks` only stripped when sentinels were absent, matching this new behavior. Documented in `test_fallback_ignored_when_sentinels_present`.

## 8. Atomic commit ordering
- **T1** — `setup._replace_sentinel_block` signature + fallback branch. Update both `patch_*_block` call sites. New tests in `test_sentinel_replace.py` (4 fallback tests). Run `pytest template/tests/test_sentinel_replace.py -x -q` → green.
- **T2** — New tests in `test_patch_war_room_ext.py` (6 regression tests). Run `pytest template/tests/test_patch_war_room_ext.py -x -q` → green.
- **T3** — Remove installer workaround: delete `_strip_bare_block`, `normalize_unsentineled_blocks`, `_MANAGED_BLOCKS`, the Stage-4 call site + comment, dead `import re`. Update `test_installer_execute.py` (rewrite reemit test, delete normalize test).
- **T4** — Full-suite run: `pytest template/tests/ -x -q`. Confirm net +9 tests pass, all installer tests green. Commit.

Each T is a single atomic commit; T3 depends on T1 landing (shared-core fallback must work before workaround is removed).

Files referenced (absolute):
- /Users/aahil/Documents/Code/agentic-war-room/template/warroom_setup/setup.py
- /Users/aahil/Documents/Code/agentic-war-room/template/scripts/installer/in_process_orchestrator.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_sentinel_replace.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_patch_war_room_ext.py
- /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_installer_execute.py

---

## Feature A Plan

See `docs/superpowers/plans/2026-06-08-awr-feature-a.md` (290 lines, comprehensive — written by the planning agent directly).

Key deltas after the synthesis cross-review (must be applied during the build):
- **§3 vs §7 contradiction on `_already_assimilated`** → pick exit 4 (orphan sentinel without enroll.json is suspicious).
- **Step 5c/5d ordering** → write walkthrough creds to `.env` BEFORE `enroll.bootstrap`, not after.
- **Risk-3 scope creep** → drop the `enroll.bootstrap`-API mutation; post-flight text only.
