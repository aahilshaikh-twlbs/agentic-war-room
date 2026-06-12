# Skill Pre-Brief Packs + Propagation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make the war-room pre-brief pack a real, versioned, propagating artifact — a pack doc (`template/shared/prebrief/warroom.md`) anchored to the existing `/warroom` bundle + member skills, injected into SOUL.md / Claude-head at persona-sync time, ownable/pinnable by the operator via `local/prebrief/`, and inspectable/announceable through a `warroom prebrief` CLI.

**Architecture:** A pack is a trio — loader (`skill-bundles/warroom.yaml`), bodies (`skills/{warroom,confidence-gate}/SKILL.md`), and a briefing/version-anchor doc (`shared/prebrief/warroom.md`). Startup load is persona-injection (a "War-room pre-brief" section in both persona-sync outputs via a new `optional` + `local_override` manifest field), never a `settings.json` hook; full bodies stay a `/warroom` bundle expansion. Propagation reuses Hermes' two pull channels (`hermes profile update` primary; `hermes skills tap`/`update` documented for foreign profiles), with an opt-in mailbox nudge (`warroom prebrief announce`) and a `local/prebrief/` pin that survives updates.

**Tech Stack:** Python 3.9+ stdlib only (`argparse`, `re`, `subprocess`, `pathlib`, `json`), pytest via the existing `template/.venv`. Sentinel/atomic-write conventions from `warroom_setup/setup.py` and `warroom_setup/runtime_state.py`. No new deps; no Hermes code changes; no `coordination/` changes.

Spec: `docs/superpowers/specs/2026-06-09-awr-skill-prebrief-packs-design.md`. Position 5 (last) in the five-sub-project sequence — multi-board-federation, classifier-tuning-harness, DEFCON severity (position 3, ships `skills/warroom-verifier/`), and the L1 orchestrator (position 4, rewrites the bundle `instruction:` to name the intake order) are designed to land BEFORE this plan.

> **BRANCH-STATE PRECONDITION (read first — positions 1–4 may NOT be landed yet).** This plan was authored assuming positions 1–4 land first, but it does NOT hard-depend on them. The two touch points are made self-contained below: Task 13 authors the full bundle `instruction:` text itself (so it works whether or not L1 has landed), and Task 14's README references `skills/warroom-verifier/` only as forward documentation (the dir need not exist). Run **Phase 0 (Task 0)** first to record the actual branch state; the per-task checkpoints assert only RELATIVE test-count deltas (never an absolute total), so they hold regardless of whether positions 1–4 added tests.

## Adopted decisions

- **D-1 (what a pack IS):** option (c) — a curated trio: bundle loader + member skills + `shared/prebrief/<pack>.md` knowledge doc.
- **D-2 (pack doc home):** `template/shared/prebrief/` — rides the existing persona-sync source home (`shared/org.md` precedent); no new top-level dir.
- **D-3 (startup load):** option (a) — briefing summary + condensed gate contract injected into SOUL/head via persona-sync; full bodies via `/warroom`. No auto-fire hook (the mailbox-hook nudge stays out of scope; the P-2 nudge is the `announce` verb).
- **D-4 (pin mechanism in manifest):** explicit `local_override` key on persona-sync sections (declarative in `manifest.json`, not a path rule in `setup.py`). A sibling `optional` key expresses graceful omission when the doc is absent (see Deviations).
- **D-5 (first-party hub repo):** DEFERRED. No hub-repo files are created anywhere. The skills-tap channel is documented in README for foreign/assimilated profiles only.
- **P-1 (primary propagation):** distribution-update (`hermes profile update`) is primary for template-born agents; hub-tap is the documented secondary channel for foreign/assimilated profiles.
- **P-2 (push vs pull):** stay pull; ship the opt-in mailbox nudge `warroom prebrief announce [--version <v>]` which shells out to the discovered mailbox CLI to post a board broadcast, fail-soft when the CLI/daemon/session is unavailable.
- **V-1 (pin granularity):** option (a) — whole-pack pin via `local/prebrief/<pack>.md`; `prebrief pin`/`--unpin` create/remove it atomically (temp + `os.replace`); persona-sync prefers it via `local_override`.
- **Open Q1 (slug collision):** KEEP the `warroom` bundle + `warroom` skill collision (verified bundle-wins, `agent/skill_bundles.py:27-31`); document it in README so nobody "fixes" it.
- **Open Q2 (gate-contract source):** the briefing summary + condensed gate contract are AUTHORED in the pack doc (short enough that drift from `confidence-gate/SKILL.md` is review-obvious). `pack_version` is mirrored as a literal `Pack version: <v>` line in the doc body; `prebrief verify` fails on frontmatter↔body version mirror drift.
- **Open Q3 (fleet update UX):** README documents the `for p in ...; do hermes profile update "$p"; done` recipe; cron is the operator's call.
- **Open Q4 (head-agent reload):** the *guarantee* rests on SOUL.md (Hermes-confirmed always-loaded); the Claude head file gets the same section best-effort. Whether Claude Code re-reads `~/.claude/agents/<name>.md` each session is an operator-verified manual check (noted in the final checkpoint), not a CI assertion.

## Deviations

- **`sanitize_check.py` needs NO code change.** Verified at planning time: the walker scans `shared/**` already — `EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "tests", "node_modules"}` (no `shared`) at `template/scripts/sanitize_check.py:29-31` and `.md` is in `SCAN_SUFFIXES` at `:35-38`. The spec's "extend scan scope to `shared/prebrief/**`" therefore lands as a lock-in regression test (Task 3) + a `SANITIZATION.md` note, NOT a scanner edit. If a future change ever removes `shared/**` from the walked tree, Task 3's test fails loudly.
- **Persona-sync render lives in `persona_sync.py`, not `setup.py`.** The spec's file-map said "wire the render in `setup.py`". Verified: the section machinery (`_render_output`, `_read`, `render_section`) is entirely in `template/warroom_setup/persona_sync.py:53-114`; `setup.run_setup` only *calls* `persona_sync.run`. All render/override/omission logic in this plan is in `persona_sync.py`; `setup.py` is untouched.
- **`schema.py` is untouched.** V-1 uses the `local/prebrief/` pin, no new config keys. The spec confirms schema is unchanged for v1.
- **Integration smoke (T15) is SIMULATION-based, not a live `hermes profile install`.** The spec's integration block says "real Hermes, gated like the existing `--runintegration` smoke." Verified at planning time: the installed Hermes (`/Users/aahil/.hermes/hermes-agent`) requires Python 3.10+ (PEP 604 `X | Y` unions at import in `hermes_constants.py`), but the shipped `template/.venv` is 3.9, so `hermes_cli.profile_distribution` is NOT importable under the test interpreter and a live in-process `hermes profile install` cannot run. The existing Feature-B smokes (`test_installer_e2e.py:1-8`) handle the identical constraint by SIMULATING the install/update subprocess and materializing a real profile tree. T15 follows that idiom: it reproduces the verified `_copy_dist_payload` copy contract (catch-all `staged.iterdir()`, skip `USER_OWNED_EXCLUDE` incl. `local`, preserve `config.yaml` on update — `profile_distribution.py:560-570`, also documented in VERIFY-AGAINST-HERMES #2) and asserts all four spec assertions against the resulting tree. This is the most conservative realization of the spec's intent given the interpreter mismatch; the assertions are identical to what a live `_copy_dist_payload` would produce, and the task notes that on a 3.10+ interpreter the real function MAY be driven instead.
- **Tasks 13/14 are self-contained against positions 1–4 NOT being landed.** The plan was authored assuming positions 1–4 (incl. L1 orchestrator at position 4 and DEFCON `warroom-verifier` at position 3) land first, but the live branch has none of them (verified: bundle is the one-liner `War-room protocol. Follow confidence-gate before posting any claim to the channel.`; no `test_bundle_instruction_names_intake_order`; no `skills/warroom-verifier/`; baseline is exactly 409+10=419). To remove the contradiction without narrowing scope: (a) Phase 0 / Task 0 records the real branch state and every checkpoint asserts only relative deltas; (b) Task 13 authors the full intake-order instruction text itself (byte-identical to L1's designed final text at `awr-l1-orchestrator.md:552-554`), so it is correct whether or not L1 has landed, with a STOP-and-surface only if a landed L1 shipped DIFFERENT wording; (c) Task 14's README references `skills/warroom-verifier/` as forward documentation only — no test asserts the dir exists.
- **`announce` cannot post from a bare operator shell without a session.** Verified: `mailbox send` requires a session id resolved from `--session` or `$MAILBOX_SESSION_ID` (`coordination/src/mailbox/cli.py:9-15, 124-154`) and returns 1 ("no session id…") otherwise. `announce` therefore synthesizes a deterministic announcer session id (`warroom-prebrief-announce`) passed via `--session`, shells out through the discovered mailbox CLI, and FAILS SOFT (warn + non-fatal return) on any non-zero exit, missing CLI, or missing daemon — it never raises and never blocks the pack. This is the closest workable realization of P-2 against the live CLI contract.

---

## VERIFY-AGAINST-HERMES results (run 2026-06-09 against `/Users/aahil/.hermes/hermes-agent/`)

All three mandatory checks PASS. The startup-load and propagation designs rest on these; re-verify on a Hermes version bump.

1. **Bundles do NOT auto-load on SessionStart (only on `/<slug>` dispatch).** PASS. `build_bundle_invocation_message` has exactly two real (non-test, non-re-export) callers, both inside slash-command dispatch branches gated on a typed command (a thin re-export wrapper also exists at `cli.py:2865` — NOT a SessionStart path):
   - `cli.py:8983` — `elif base_cmd in skill_bundles:` (command dispatch loop), comment "Skill bundles take precedence over individual skills — /<bundle> loads multiple skills at once."
   - `gateway/run.py:8223-8229` — `if command:` → `resolve_bundle_command_key(command)` → `build_bundle_invocation_message(...)`, comment "Mirrors CLI dispatch."
   No SessionStart path invokes it. The whole startup-load design (SOUL injection, not bundle auto-load) is therefore sound.
2. **`_copy_dist_payload`'s catch-all copies non-`distribution_owned` top-level dirs.** PASS. `hermes_cli/profile_distribution.py` iterates `staged.iterdir()` (the `for entry in staged.iterdir():` loop begins at line 560) and copies everything NOT in `USER_OWNED_EXCLUDE` (`if name in USER_OWNED_EXCLUDE: continue` at line 563). It does NOT consult `manifest.owned_paths()` in the copy loop (`owned_paths()` exists at `:238` but is unused there). So `skill-bundles/` and `shared/` propagate today regardless of the manifest. `config.yaml` is preserved unless `--force-config`; `local` is in `USER_OWNED_EXCLUDE` (`:118`) so pins survive. `update_distribution` re-applies the same copy. The spec's `distribution_owned` additions are contract-correctness/future-proofing (a latent break if Hermes ever switches the loop to `owned_paths()`), not a behavior change — exactly why Task 2 declares them.
3. **The bundles scan path for an installed profile is `<HERMES_HOME>/skill-bundles`.** PASS. `_bundles_dir()` returns `get_hermes_home() / "skill-bundles"` (`agent/skill_bundles.py:66-75`), honoring `HERMES_BUNDLES_DIR` for tests. Per handoff §0, `<profile>` IS `HERMES_HOME` when the profile is active, so the shipped `template/skill-bundles/warroom.yaml` lands at the scanned path.

No fallback adaptations were required.

## Verified source anchors (re-verify line numbers at execution; positions 1–4 land first and may shift them)

| Fact | Where (verified 2026-06-09) |
|---|---|
| Bundle ships `skills: [warroom, confidence-gate]` + `instruction:` block scalar. **Live (positions 1–4 not landed):** instruction is the one-liner `War-room protocol. Follow confidence-gate before posting any claim to the channel.` L1 (position 4) is *designed* to rewrite it to name the intake order, but Task 13 authors the full intake-order text itself (matching L1's final text verbatim at `docs/superpowers/plans/2026-06-09-awr-l1-orchestrator.md:552-554`), so this plan does not depend on L1 having landed | `template/skill-bundles/warroom.yaml`; L1 final text `docs/superpowers/plans/2026-06-09-awr-l1-orchestrator.md:546-554` |
| Persona-sync section render: `_render_output` builds `header + preamble + sections + trailer`; `_read` RAISES `FileNotFoundError` on a missing source (no omission today); `render_section(title, body)` → `"## {title}\n\n{body}"` | `template/warroom_setup/persona_sync.py:53-83` |
| Manifest = 2 outputs (`claude_head`, `hermes_soul`), sections each `{"title","source"}`; `Org context` sourced from `shared/org.md` | `template/manifest.json:9-30` |
| `setup.run_setup` calls `persona_sync.run(...)` for both `--sync` and full setup | `template/warroom_setup/setup.py:382-387, 445` |
| Atomic write helper | `setup._atomic_write_text` `template/warroom_setup/setup.py:99-113` |
| Atomic JSON state write | `runtime_state.save_state` `template/warroom_setup/runtime_state.py:16-44` |
| CLI dispatch lives in `cli.py::_build_parser` + `cli.py::main`; `__main__.py` only calls `cli.main`. `setup`/`enroll`/`assimilate` registered as subparsers there | `template/warroom_setup/cli.py:11-47, 112-130`; `template/warroom_setup/__main__.py:1-4` |
| Mailbox CLI discovery (precedence ladder) | `enroll.discover_mailbox_cli(env, repo_search_start)` `template/warroom_setup/enroll.py:74-100` |
| `mailbox send <body> [--to *] [--kind note]` needs a session id (`--session`/`$MAILBOX_SESSION_ID`); returns 1 with "no session id…" otherwise | `coordination/src/mailbox/cli.py:9-15, 124-127, 147-154` |
| `distribution_owned` today: `SOUL.md, config.yaml, skills, cron, distribution.yaml`; `version: 0.1.0`; `skill-bundles`+`shared` ABSENT | `template/distribution.yaml:3-4, 30-35` |
| `sanitize_check` walks `shared/` (`.md` scanned; `shared` not excluded) | `template/scripts/sanitize_check.py:29-31, 35-38, 41-72` |
| Existing bundle tests that MUST stay green | `template/tests/test_warroom_bundle.py`, `template/tests/test_confidence_gate.py` |
| Existing persona-sync test idiom (`AgentIdentity`, tmp manifest, `run(...)`); `test_shipped_manifest_compiles_against_seeded_overlay` copies `persona/templates/shared` into the profile | `template/tests/test_persona_sync.py:6-92` |
| Exit-code-matrix test idiom to MIRROR | `template/tests/test_assimilate.py::test_exit_code_matrix` `:519-550`; whole file `:1-668` |
| Byte-snapshot guard idiom (sha256 pin) | `template/tests/test_assimilate_skill.py:18-21` |
| `warroom-verifier/SKILL.md` lands at position 3 (DEFCON) — **forward-referenced; NOT required for this plan's tests.** Task 14's README names it as a deliberate non-member, but no task asserts the dir exists; the dir is absent on a branch where position 3 has not landed | `docs/superpowers/plans/2026-06-09-awr-defcon-severity.md:1961` |

**Baselines (verified by running):**
- `template/.venv/bin/python -m pytest template -q` → **409 passed, 10 skipped** (419 collected) on the CURRENT branch, where positions 1–4 are NOT landed. If positions 1–4 land before this plan runs, the absolute count will be HIGHER. Task 0 captures the real number at execution time; every checkpoint asserts only the RELATIVE delta from this plan's own tasks, so the contradiction between "positions 1–4 designed to land first" and "419 today" is harmless — never assert an absolute total.
- This plan touches NO `coordination/` files, so no coordination baseline applies.

---

## Phase 0 — branch-state baseline (record, do not gate-fail)

### Task 0: Capture the real baseline + the live bundle/verifier state

Files:
- Test: whole `template/` suite (read-only; nothing modified)

#### Steps

- [ ] **Capture the current baseline test count.** This is the number every later checkpoint's RELATIVE delta is measured against — record it; do NOT compare it to the plan's prose "409 + 10".

  ```bash
  template/.venv/bin/python -m pytest template -q 2>&1 | tail -3
  ```

  Record the printed `N passed, M skipped`. On a branch with NONE of positions 1–4 landed this is `409 passed, 10 skipped`; if positions 1–4 landed it is higher. EITHER is fine — note the number you saw.

- [ ] **Record whether the L1 bundle rewrite landed (position 4).** This tells you which Task-13 path applies:

  ```bash
  grep -n "test_bundle_instruction_names_intake_order" template/tests/test_warroom_bundle.py 2>/dev/null && echo "L1 LANDED" || echo "L1 NOT landed — Task 13 authors the intake text itself"
  ```

  Either outcome is supported. Task 13 is self-contained: if L1 has NOT landed, Task 13 authors the full intake-order instruction; if L1 HAS landed, Task 13 keeps L1's verbatim wording and appends only the pre-brief sentence (the two are identical text, so no conflict either way).

- [ ] **Record whether `skills/warroom-verifier/` landed (position 3).** Task 14 references it as forward documentation only — it need not exist:

  ```bash
  ls -d template/skills/warroom-verifier 2>/dev/null && echo "verifier present" || echo "verifier absent — fine; README forward-references it"
  ```

- [ ] **No commit** (read-only baseline capture; nothing changed).

---

## Phase 1 — pack format + manifest correctness

### Task 1: Create the pre-brief pack doc

Files:
- Create: `template/shared/prebrief/warroom.md`
- Create: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`

#### Steps

- [ ] **Write the failing test.** Create `template/tests/test_prebrief.py` with exactly:

  ```python
  """Pre-brief pack: doc parse, persona-sync injection, pin override, verify CLI.

  Accretes across Tasks 1, 5, 6, 8, 9, 10, 11. Stdlib + pytest only.
  """
  import io
  import json
  import re
  from pathlib import Path

  ROOT = Path(__file__).resolve().parents[1]
  PACK_DOC = ROOT / "shared" / "prebrief" / "warroom.md"

  _SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


  def _frontmatter(text):
      """Return the raw frontmatter block (between the first two '---' lines)."""
      lines = text.split("\n")
      assert lines and lines[0].strip() == "---", "doc must open with YAML frontmatter"
      out = []
      for line in lines[1:]:
          if line.strip() == "---":
              return "\n".join(out)
          out.append(line)
      raise AssertionError("unclosed frontmatter")


  # --------------------------------------------------------------------------- #
  # Task 1 -- pack doc shape
  # --------------------------------------------------------------------------- #
  def test_pack_doc_exists_and_opens_with_frontmatter():
      assert PACK_DOC.is_file()
      text = PACK_DOC.read_text(encoding="utf-8")
      assert text.startswith("---\n")
      assert text.endswith("\n")


  def test_pack_doc_frontmatter_has_required_keys():
      fm = _frontmatter(PACK_DOC.read_text(encoding="utf-8"))
      assert re.search(r"^pack:\s*warroom\s*$", fm, re.M)
      assert re.search(r"^pack_version:\s*\S+", fm, re.M)
      assert re.search(r"^summary:\s*>", fm, re.M)
      assert re.search(r"^members:\s*$", fm, re.M)
      members = re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)
      assert members == ["confidence-gate", "warroom"]


  def test_pack_doc_version_is_semver():
      fm = _frontmatter(PACK_DOC.read_text(encoding="utf-8"))
      m = re.search(r"^pack_version:\s*(\S+)\s*$", fm, re.M)
      assert m and _SEMVER.match(m.group(1)), "pack_version must be semver"


  def test_pack_doc_body_mirrors_version_and_points_to_warroom():
      text = PACK_DOC.read_text(encoding="utf-8")
      fm = _frontmatter(text)
      ver = re.search(r"^pack_version:\s*(\S+)\s*$", fm, re.M).group(1)
      # version mirrored into the body so a running agent can state its pack
      assert ("Pack version: %s" % ver) in text
      assert "/warroom" in text  # points at the full-protocol expansion
      assert "confidence-gate" in text  # names the gate contract member
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q
  ```

  Expected: all four tests fail (the first with `AssertionError` on `PACK_DOC.is_file()`, the rest with `FileNotFoundError`) because `template/shared/prebrief/warroom.md` does not exist.

- [ ] **Create the pack doc.** Write `template/shared/prebrief/warroom.md` with exactly:

  ```markdown
  ---
  pack: warroom
  pack_version: 1.0.0
  summary: >
    Every war-room agent has read this. Ground every claim, score your
    confidence, abstain below the board threshold, and coordinate on the
    shared board via the mailbox before you act.
  members:
    - confidence-gate
    - warroom
  ---

  # War-room pre-brief

  Pack version: 1.0.0

  You are a war-room agent. Before your first message you have read this
  briefing. It is the condensed contract; run `/warroom` to load the full
  protocol bodies (the `warroom` and `confidence-gate` skills) into context.

  ## The gate contract (one paragraph)

  Ground every factual claim in a tool result, a file you read, or a cited
  source — never in recall alone. Score your confidence and emit it in the
  envelope the `confidence-gate` skill defines. If your confidence is below
  the board's `min_confidence` threshold, abstain: say what you would need to
  raise it, and do not post the claim. Higher severity demands a stricter bar.

  ## The coordination contract (one paragraph)

  You share a board with other agents. Run `mailbox ps` to see who is here and
  `mailbox claims --all` before you touch a file a peer may be editing. Claim a
  work-lane (`mailbox claim-lane <lane>`) before starting, post findings with
  `mailbox send`, read with `mailbox inbox`, and release lanes when done. Route
  to the right board: keep local work local, escalate cross-team findings, and
  broadcast only subtree-wide announcements.

  ## Load the full protocol

  Run `/warroom` to expand the bundle (the `warroom` orchestration protocol +
  the `confidence-gate` rules) into context when you need the verbatim commands.
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q
  ```

  Expected: 0 failures; adds 4 tests.

- [ ] **Commit:**

  ```bash
  git add template/shared/prebrief/warroom.md template/tests/test_prebrief.py
  git commit -m "AWR prebrief: pack doc shared/prebrief/warroom.md + shape tests (T1)"
  ```

### Task 2: Declare `skill-bundles` + `shared` as distribution-owned; bump version

Files:
- Modify: `template/distribution.yaml`
- Modify: `template/tests/test_template_content.py`
- Test: `template/tests/test_template_content.py`

#### Steps

- [ ] **Write the failing test.** Append to the END of `template/tests/test_template_content.py` (the file already imports `re` and defines `ROOT`):

  ```python
  # ---- Pre-brief pack: distribution ownership is explicit (contract fix) ----

  def test_distribution_owns_skill_bundles_and_shared():
      dist = (ROOT / "distribution.yaml").read_text(encoding="utf-8")
      owned = re.findall(r"^\s*-\s*([A-Za-z0-9_.-]+)\s*$", dist, re.M)
      for name in ("skill-bundles", "shared"):
          assert name in owned, "%s must be declared distribution_owned" % name
      # the originals must survive the edit
      for name in ("SOUL.md", "config.yaml", "skills", "cron", "distribution.yaml"):
          assert name in owned, "%s ownership regressed" % name


  def test_distribution_version_bumped_past_initial():
      dist = (ROOT / "distribution.yaml").read_text(encoding="utf-8")
      m = re.search(r"^version:\s*(\S+)\s*$", dist, re.M)
      assert m, "distribution.yaml must carry a version"
      assert m.group(1) != "0.1.0", "version must be bumped on a pack change"
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_template_content.py -q
  ```

  Expected: `2 failed` — `test_distribution_owns_skill_bundles_and_shared` (skill-bundles/shared absent) and `test_distribution_version_bumped_past_initial` (still `0.1.0`).

- [ ] **Edit `distribution.yaml` — bump the version.** Replace this line:

  ```yaml
  version: 0.1.0
  ```

  with:

  ```yaml
  version: 0.2.0
  ```

- [ ] **Edit `distribution.yaml` — declare the two new owned paths.** Replace this block:

  ```yaml
  distribution_owned:
    - SOUL.md
    - config.yaml
    - skills
    - cron
    - distribution.yaml
  ```

  with (NO inline `# comments` on the list items — the Task-2 test regex
  `^\s*-\s*([A-Za-z0-9_.-]+)\s*$` anchors on `$` after the name, so a trailing
  comment would defeat the capture; `skill-bundles` carries the pre-brief pack
  loader `warroom.yaml`, `shared` carries the pack doc `prebrief/` + `org.md`):

  ```yaml
  distribution_owned:
    - SOUL.md
    - config.yaml
    - skills
    - skill-bundles
    - shared
    - cron
    - distribution.yaml
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_template_content.py \
      template/tests/test_distribution.py -q
  ```

  Expected: 0 failures; adds 2 tests. `test_distribution.py` (top-key presence) still passes.

- [ ] **Commit:**

  ```bash
  git add template/distribution.yaml template/tests/test_template_content.py
  git commit -m "AWR prebrief: declare skill-bundles + shared distribution_owned, bump version (T2)"
  ```

### Task 3: Pack-integrity tests + sanitize scope lock-in + SANITIZATION.md note

Files:
- Modify: `template/tests/test_warroom_bundle.py`
- Modify: `template/SANITIZATION.md`
- Test: `template/tests/test_warroom_bundle.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_warroom_bundle.py` (the file already imports `re`, `from pathlib import Path`, and defines `ROOT = Path(__file__).resolve().parents[1]`):

  ```python
  # ---- Pre-brief pack ↔ bundle ↔ skills consistency ----

  def _pack_members():
      text = (ROOT / "shared" / "prebrief" / "warroom.md").read_text(encoding="utf-8")
      fm = text.split("---", 2)[1]  # frontmatter between the first two '---'
      return re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)


  def _bundle_skills():
      bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text(encoding="utf-8")
      # skills: list only — stop at the next top-level key (e.g. instruction:)
      m = re.search(r"^skills:\s*\n((?:\s+-\s*.*\n)+)", bundle, re.M)
      assert m, "bundle must carry a skills: list"
      return re.findall(r"-\s*([a-z][a-z0-9-]*)", m.group(1))


  def test_pack_members_each_resolve_to_a_skill_dir():
      for member in _pack_members():
          skill = ROOT / "skills" / member / "SKILL.md"
          assert skill.is_file(), "pack member %r has no skills/%s/SKILL.md" % (member, member)


  def test_pack_members_equal_bundle_skills_as_sets():
      # no orphan in either direction: every member is in the bundle and vice versa
      assert set(_pack_members()) == set(_bundle_skills())


  def test_pack_doc_lists_exactly_warroom_and_confidence_gate():
      assert set(_pack_members()) == {"warroom", "confidence-gate"}


  def test_sanitize_check_scans_shared_prebrief():
      # The pack doc lands under shared/prebrief/; lock in that the sanitizer walks
      # it (shared is NOT excluded; .md IS a scan suffix). If a future change drops
      # shared/** from the walked tree this fails loudly (the spec's "extend scope").
      import sys
      sys.path.insert(0, str(ROOT))
      from scripts import sanitize_check
      assert "shared" not in sanitize_check.EXCLUDE_DIRS
      assert ".md" in sanitize_check.SCAN_SUFFIXES
      scanned = list(sanitize_check._iter_files(str(ROOT / "shared")))
      assert any(p.endswith("prebrief/warroom.md") for p in scanned)
  ```

- [ ] **Run — expect green for integrity, confirm the sanitize lock-in passes.**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_warroom_bundle.py -q
  ```

  Expected: 0 failures. (The pack doc from Task 1 and the existing `skill-bundles/warroom.yaml` already satisfy these; this task LOCKS the contract so the rest of the plan cannot break it.) `test_sanitize_check_scans_shared_prebrief` passes because `shared/prebrief/warroom.md` exists and is walked. If `test_pack_members_each_resolve_to_a_skill_dir` fails, a pack member skill dir is missing — STOP and surface to lead (do not delete the test).

- [ ] **Add the SANITIZATION.md note.** In `template/SANITIZATION.md`, insert this new section immediately AFTER the `## Files to drop entirely (never ship)` section (i.e. before `## Skills folders hard-excluded`):

  ```markdown
  ## Pre-brief pack docs (`shared/prebrief/**`)

  The pre-brief pack doc (`shared/prebrief/<pack>.md`) is injected verbatim into
  the always-loaded `SOUL.md` and the Claude head agent file via persona-sync, so
  it is a public, distribution-owned surface. `sanitize_check.py` already scans it
  (`shared/` is not in `EXCLUDE_DIRS` and `.md` is a scanned suffix), and the test
  `test_warroom_bundle.py::test_sanitize_check_scans_shared_prebrief` locks that
  in. No employer/operator name, channel ID, or secret may appear in a pack doc.
  ```

- [ ] **Run sanitize + the bundle suite — expect clean:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_warroom_bundle.py -q
  python3 template/scripts/sanitize_check.py template/
  ```

  Expected: 0 test failures; adds 4 tests. `sanitize_check` prints `sanitize_check: clean (template/)` and exits 0.

- [ ] **Commit:**

  ```bash
  git add template/tests/test_warroom_bundle.py template/SANITIZATION.md
  git commit -m "AWR prebrief: pack-bundle-skills integrity + sanitize-scope lock-in (T3)"
  ```

### Task 4: Phase 1 checkpoint — full suite green + sanitize

Files:
- Test: whole `template/` suite

#### Steps

- [ ] **Run the full suite + sanitize:**

  ```bash
  template/.venv/bin/python -m pytest template -q
  python3 template/scripts/sanitize_check.py template/
  ```

  Expected: 0 failures (baseline + 10 tests added across Tasks 1-3). `sanitize_check` exits 0. Only "0 failures" and the +10 delta from THIS plan's Tasks 1-3 are load-bearing — the absolute count may differ if positions 1-4 added tests.

- [ ] **No commit** (checkpoint only; nothing changed since Task 3).

---

## Phase 2 — startup load via persona-sync

### Task 5: Persona-sync gains `optional` + `local_override`; manifest declares the pre-brief section

Files:
- Modify: `template/warroom_setup/persona_sync.py`
- Modify: `template/manifest.json`
- Modify: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`, `template/tests/test_persona_sync.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_prebrief.py`:

  ```python
  # --------------------------------------------------------------------------- #
  # Task 5 -- persona-sync injection (present / pinned / omitted)
  # --------------------------------------------------------------------------- #
  from warroom_setup import persona_sync  # noqa: E402
  from warroom_setup.agent_model import AgentIdentity  # noqa: E402

  _IDENT = AgentIdentity(
      agent_name="aria", handle="aria-sh", display_name="Aria",
      model="opus", specialist_prefix="aria", agent_fingerprint="aria-xyz",
  )


  def _prebrief_fixture(tmp_path, *, override_body=None, omit_source=False):
      """A minimal profile with one output whose sections include a prebrief
      section (source = shared/prebrief/warroom.md, local_override =
      local/prebrief/warroom.md, optional = true)."""
      (tmp_path / "shared" / "prebrief").mkdir(parents=True)
      (tmp_path / "templates").mkdir()
      (tmp_path / "templates" / "soul-preamble.md").write_text(
          "# {{display_name}} - Persona\n", encoding="utf-8")
      if not omit_source:
          (tmp_path / "shared" / "prebrief" / "warroom.md").write_text(
              "---\npack: warroom\npack_version: 1.0.0\n---\n"
              "# War-room pre-brief\n\nShared briefing body.\n", encoding="utf-8")
      if override_body is not None:
          (tmp_path / "local" / "prebrief").mkdir(parents=True)
          (tmp_path / "local" / "prebrief" / "warroom.md").write_text(
              override_body, encoding="utf-8")
      manifest = {
          "header": "<!-- gen for {{handle}} -->",
          "outputs": [
              {"name": "soul",
               "target": str(tmp_path / "out" / "{{handle}}" / "SOUL.md"),
               "preamble": "templates/soul-preamble.md", "trailer": "",
               "sections": [
                   {"title": "War-room pre-brief",
                    "source": "shared/prebrief/warroom.md",
                    "local_override": "local/prebrief/warroom.md",
                    "optional": True},
               ]},
          ],
      }
      (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
      return tmp_path


  def test_prebrief_section_injected_from_shared(tmp_path):
      root = _prebrief_fixture(tmp_path)
      rc = persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
      assert rc == 0
      out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
      assert "## War-room pre-brief" in out
      assert "Shared briefing body." in out
      assert "{{" not in out


  def test_prebrief_local_override_wins(tmp_path):
      root = _prebrief_fixture(
          tmp_path, override_body="---\npack: warroom\n---\n# Pinned\n\nPinned body.\n")
      persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
      out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
      assert "Pinned body." in out
      assert "Shared briefing body." not in out  # override wins over source


  def test_prebrief_section_omitted_when_optional_source_absent(tmp_path):
      root = _prebrief_fixture(tmp_path, omit_source=True)
      rc = persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
      assert rc == 0  # optional + absent -> graceful omit, SOUL still valid
      out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
      assert "## War-room pre-brief" not in out
      assert "# Aria - Persona" in out  # preamble still rendered; SOUL is valid


  def test_nonoptional_missing_source_still_raises(tmp_path):
      # regression guard: a NON-optional missing source must still raise (existing
      # _read contract for the persona sections must not be loosened globally)
      import pytest
      (tmp_path / "templates").mkdir()
      (tmp_path / "templates" / "soul-preamble.md").write_text("# x\n", encoding="utf-8")
      manifest = {
          "header": "h", "outputs": [
              {"name": "soul", "target": str(tmp_path / "o" / "SOUL.md"),
               "preamble": "templates/soul-preamble.md", "trailer": "",
               "sections": [{"title": "Role", "source": "local/persona/role.md"}]}]}
      (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
      with pytest.raises(FileNotFoundError):
          persona_sync.run(tmp_path / "manifest.json", tmp_path, _IDENT, check=False)
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q \
      -k "prebrief_section or override or omitted or nonoptional"
  ```

  Expected: `test_prebrief_section_injected_from_shared`, `test_prebrief_local_override_wins`, and `test_prebrief_section_omitted_when_optional_source_absent` FAIL — the first two raise `FileNotFoundError` (no `local/prebrief` handling and the override path is ignored), the omit test raises because today's `_read` raises on the absent source instead of omitting. `test_nonoptional_missing_source_still_raises` passes already (documents the unchanged contract).

- [ ] **Edit `persona_sync.py` — teach `_render_output` about `local_override` + `optional`.** Replace the existing `_render_output` function (`template/warroom_setup/persona_sync.py:73-83`) with:

  ```python
  def _resolve_section_source(repo_root, sec):
      # type: (Path, dict) -> Optional[str]
      """Resolve a section body honoring an optional local_override.

      Precedence: `local_override` (user-owned pin) wins over `source` when the
      override file exists on disk. Returns the raw text, or None when the
      section is `optional` and neither path resolves (graceful omission). A
      non-optional missing source raises FileNotFoundError (unchanged contract).
      """
      override = sec.get("local_override")
      if override and (repo_root / override).is_file():
          return _read(repo_root, override)
      source = sec.get("source")
      if source and (repo_root / source).is_file():
          return _read(repo_root, source)
      if sec.get("optional"):
          return None
      # non-optional: preserve the original loud failure on a missing source.
      return _read(repo_root, source)


  def _render_output(entry, header, repo_root):
      # type: (dict, str, Path) -> str
      parts = [header]
      if entry.get("preamble"):
          parts.append(_read(repo_root, entry["preamble"]).rstrip())
      for sec in entry["sections"]:
          raw = _resolve_section_source(repo_root, sec)
          if raw is None:
              continue  # optional section, source absent -> omit
          body = strip_related(strip_frontmatter_and_h1(raw))
          parts.append(render_section(sec["title"], body))
      if entry.get("trailer"):
          parts.append(_read(repo_root, entry["trailer"]).rstrip())
      return "\n\n".join(parts)
  ```

- [ ] **Edit `manifest.json` — add the pre-brief section to BOTH outputs.** Overwrite `template/manifest.json` with exactly (the `War-room pre-brief` section is prepended to BOTH outputs' `sections`):

  ```json
  {
    "header": "<!-- DO NOT EDIT. Generated from local/persona/ by `warroom setup --sync`. Edit local/persona/*.md, then re-run. -->",
    "outputs": [
      {
        "name": "claude_head",
        "target": "~/.claude/agents/{{agent_name}}.md",
        "preamble": "templates/claude-head-frontmatter.md",
        "trailer": "templates/claude-head-trailer.md",
        "sections": [
          {"title": "War-room pre-brief", "source": "shared/prebrief/warroom.md", "local_override": "local/prebrief/warroom.md", "optional": true},
          {"title": "Org context", "source": "shared/org.md"},
          {"title": "Role", "source": "local/persona/role.md"},
          {"title": "Team", "source": "local/persona/team.md"},
          {"title": "Communication style", "source": "local/persona/communication.md"},
          {"title": "Decision making", "source": "local/persona/decisions.md"},
          {"title": "Voice", "source": "local/persona/voice.md"}
        ]
      },
      {
        "name": "hermes_soul",
        "target": "~/.hermes/profiles/{{handle}}/SOUL.md",
        "preamble": "templates/soul-preamble.md",
        "trailer": "",
        "sections": [
          {"title": "War-room pre-brief", "source": "shared/prebrief/warroom.md", "local_override": "local/prebrief/warroom.md", "optional": true},
          {"title": "Voice", "source": "local/persona/voice.md"},
          {"title": "Communication", "source": "local/persona/communication.md"},
          {"title": "Decision Heuristics", "source": "local/persona/decisions.md"},
          {"title": "Team", "source": "local/persona/team.md"},
          {"title": "Org context", "source": "shared/org.md"}
        ]
      }
    ]
  }
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py \
      template/tests/test_persona_sync.py -q
  ```

  Expected: 0 failures; adds 4 tests. `test_persona_sync.py` stays green (its fixtures' sections have no `optional`/`local_override`, so the non-optional path is unchanged; `test_shipped_manifest_compiles_against_seeded_overlay` copies `shared/` into the profile so the new shipped section resolves — and that test cleans up the real `~/.hermes`/`~/.claude` files it writes in its `finally`, unchanged behavior).

- [ ] **Commit:**

  ```bash
  git add template/warroom_setup/persona_sync.py template/manifest.json template/tests/test_prebrief.py
  git commit -m "AWR prebrief: persona-sync optional + local_override; manifest pre-brief section (T5)"
  ```

### Task 6: Persona-sync injection tests against the SHIPPED manifest + pack doc

Files:
- Modify: `template/tests/test_persona_sync.py`
- Test: `template/tests/test_persona_sync.py`

> **NOTE on the injected briefing vs. the YAML `summary:` field (spec :245, :512-516).** The spec names the injected section content as "the pack doc's `summary` + the condensed gate contract + the `/warroom` pointer". In this plan the surfaced briefing is the pack-doc BODY (everything after frontmatter + H1), because `strip_frontmatter_and_h1` (`persona_sync.py:19-34`) drops the YAML block that holds `summary:`. This is intentional and equivalent: the body's first paragraph ("You are a war-room agent. Before your first message you have read this briefing…") restates the summary's substance, so the body is the single source of truth for the injected text and the YAML `summary:` is doc-metadata only (read by `prebrief show`/`verify`, never injected). The Task-6 assertions therefore check the body's gate-contract sentence, the `/warroom` pointer, and the `Pack version:` mirror — NOT the literal frontmatter `summary:`. Reviewers: the `summary` requirement is met by the body prose, not narrowed away.

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_persona_sync.py` (the file already imports `json`, `Path`, `persona_sync`, `AgentIdentity`, and defines `IDENT`):

  ```python
  # ---- Pre-brief: shipped manifest injects the pack section into both outputs ----

  def test_shipped_prebrief_section_in_both_outputs(tmp_path):
      import shutil
      src = Path(__file__).resolve().parents[1]
      prof = tmp_path / "prof"
      for d in ("persona", "templates", "shared"):
          shutil.copytree(src / d, prof / d)
      shutil.copy2(src / "manifest.json", prof / "manifest.json")
      (prof / "local").mkdir()
      shutil.copytree(prof / "persona", prof / "local" / "persona")
      # Redirect both manifest targets under tmp so the real ~/.hermes /
      # ~/.claude are never touched.
      manifest = json.loads((prof / "manifest.json").read_text(encoding="utf-8"))
      for out in manifest["outputs"]:
          if out["name"] == "hermes_soul":
              out["target"] = str(prof / "out" / "soul" / "{{handle}}.md")
          else:
              out["target"] = str(prof / "out" / "head" / "{{agent_name}}.md")
      (prof / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

      rc = persona_sync.run(prof / "manifest.json", prof, IDENT, check=False)
      assert rc == 0
      soul = (prof / "out" / "soul" / "aria-sh.md").read_text(encoding="utf-8")
      head = (prof / "out" / "head" / "aria.md").read_text(encoding="utf-8")
      for text in (soul, head):
          assert "## War-room pre-brief" in text
          assert "Ground every factual claim" in text   # gate contract sentence
          assert "/warroom" in text                       # full-protocol pointer
          assert "Pack version: 1.0.0" in text            # version observability
          assert "{{" not in text


  def test_shipped_prebrief_omitted_when_doc_deleted(tmp_path):
      import shutil
      src = Path(__file__).resolve().parents[1]
      prof = tmp_path / "prof"
      for d in ("persona", "templates", "shared"):
          shutil.copytree(src / d, prof / d)
      shutil.copy2(src / "manifest.json", prof / "manifest.json")
      (prof / "local").mkdir()
      shutil.copytree(prof / "persona", prof / "local" / "persona")
      (prof / "shared" / "prebrief" / "warroom.md").unlink()  # operator removed the pack
      manifest = json.loads((prof / "manifest.json").read_text(encoding="utf-8"))
      for out in manifest["outputs"]:
          out["target"] = str(prof / "out" / out["name"] / "x.md")
      (prof / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
      rc = persona_sync.run(prof / "manifest.json", prof, IDENT, check=False)
      assert rc == 0  # optional source absent -> omit, no crash
      for name in ("hermes_soul", "claude_head"):
          text = (prof / "out" / name / "x.md").read_text(encoding="utf-8")
          assert "## War-room pre-brief" not in text
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_persona_sync.py -q
  ```

  Expected: 0 failures; adds 2 tests. (Both pass on the Task-5 code + the Task-1 shipped pack doc; targets are redirected under `tmp_path` so no real `~/.hermes`/`~/.claude` write occurs.)

- [ ] **Commit:**

  ```bash
  git add template/tests/test_persona_sync.py
  git commit -m "AWR prebrief: shipped-manifest injects pre-brief into SOUL + head; omit-on-delete (T6)"
  ```

### Task 7: Phase 2 checkpoint — full suite green + sanitize

Files:
- Test: whole `template/` suite

#### Steps

- [ ] **Run the full suite + sanitize:**

  ```bash
  template/.venv/bin/python -m pytest template -q
  python3 template/scripts/sanitize_check.py template/
  ```

  Expected: 0 failures (Phase 1 total + 6 tests from Tasks 5-6). `sanitize_check` exits 0.

- [ ] **No commit** (checkpoint only).

---

## Phase 3 — operator surface + versioning/pinning

### Task 8: `prebrief.py` core — `parse_pack` + `show` + `verify`

Files:
- Create: `template/warroom_setup/prebrief.py`
- Modify: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_prebrief.py`:

  ```python
  # --------------------------------------------------------------------------- #
  # Task 8 -- prebrief.py: parse_pack, show, verify
  # --------------------------------------------------------------------------- #
  from warroom_setup import prebrief  # noqa: E402


  def _profile_with_pack(tmp_path, *, members=("confidence-gate", "warroom"),
                         pack_version="1.0.0", with_skills=True,
                         with_bundle=True, with_doc=True, body_version=None):
      """Build a tmp profile with a pack doc, member skills, and a bundle."""
      if body_version is None:
          body_version = pack_version
      if with_doc:
          (tmp_path / "shared" / "prebrief").mkdir(parents=True)
          ml = "\n".join("  - %s" % m for m in members)
          (tmp_path / "shared" / "prebrief" / "warroom.md").write_text(
              "---\npack: warroom\npack_version: %s\nsummary: >\n  s\nmembers:\n%s\n---\n"
              "# War-room pre-brief\n\nPack version: %s\n" % (pack_version, ml, body_version),
              encoding="utf-8")
      if with_skills:
          for m in members:
              (tmp_path / "skills" / m).mkdir(parents=True)
              (tmp_path / "skills" / m / "SKILL.md").write_text(
                  "---\nname: %s\ndescription: d\n---\n# %s\n" % (m, m), encoding="utf-8")
      if with_bundle:
          (tmp_path / "skill-bundles").mkdir(parents=True)
          sk = "\n".join("  - %s" % m for m in members)
          (tmp_path / "skill-bundles" / "warroom.yaml").write_text(
              "name: warroom\ndescription: d\nskills:\n%s\ninstruction: |\n  x\n" % sk,
              encoding="utf-8")
      return tmp_path


  def test_parse_pack_reads_frontmatter(tmp_path):
      root = _profile_with_pack(tmp_path)
      pack = prebrief.parse_pack(root, "warroom")
      assert pack["pack"] == "warroom"
      assert pack["pack_version"] == "1.0.0"
      assert pack["members"] == ["confidence-gate", "warroom"]


  def test_parse_pack_missing_doc_raises(tmp_path):
      root = _profile_with_pack(tmp_path, with_doc=False)
      import pytest
      with pytest.raises(FileNotFoundError):
          prebrief.parse_pack(root, "warroom")


  def test_show_prints_version_members_and_install_status(tmp_path):
      root = _profile_with_pack(tmp_path)
      out = io.StringIO()
      rc = prebrief.show(root, "warroom", out=out)
      assert rc == 0
      text = out.getvalue()
      assert "pack: warroom" in text and "version: 1.0.0" in text
      assert "confidence-gate" in text and "warroom" in text
      assert "installed" in text  # member install status column


  def test_show_reports_pin_gap(tmp_path):
      root = _profile_with_pack(tmp_path, pack_version="1.2.0")
      (root / "local" / "prebrief").mkdir(parents=True)
      (root / "local" / "prebrief" / "warroom.md").write_text(
          "---\npack: warroom\npack_version: 1.0.0\n---\n# x\nPack version: 1.0.0\n",
          encoding="utf-8")
      out = io.StringIO()
      prebrief.show(root, "warroom", out=out)
      text = out.getvalue()
      assert "pinned: 1.0.0" in text and "available: 1.2.0" in text


  def test_verify_passes_on_healthy_pack(tmp_path):
      root = _profile_with_pack(tmp_path)
      out = io.StringIO()
      assert prebrief.verify(root, "warroom", out=out) == 0
      assert "OK" in out.getvalue()


  def test_verify_fails_on_missing_member_skill(tmp_path):
      root = _profile_with_pack(tmp_path, with_skills=False)
      out = io.StringIO()
      assert prebrief.verify(root, "warroom", out=out) == 1
      assert "does not resolve" in out.getvalue()


  def test_verify_fails_on_bundle_mismatch(tmp_path):
      root = _profile_with_pack(tmp_path)
      # bundle drops a member
      (root / "skill-bundles" / "warroom.yaml").write_text(
          "name: warroom\ndescription: d\nskills:\n  - warroom\ninstruction: |\n  x\n",
          encoding="utf-8")
      out = io.StringIO()
      assert prebrief.verify(root, "warroom", out=out) == 1
      assert "bundle" in out.getvalue()


  def test_verify_fails_on_version_mirror_drift(tmp_path):
      root = _profile_with_pack(tmp_path, pack_version="1.0.0", body_version="9.9.9")
      out = io.StringIO()
      assert prebrief.verify(root, "warroom", out=out) == 1
      assert "version" in out.getvalue().lower()


  def test_verify_missing_doc_returns_1(tmp_path):
      root = _profile_with_pack(tmp_path, with_doc=False)
      out = io.StringIO()
      assert prebrief.verify(root, "warroom", out=out) == 1
      assert "pack doc" in out.getvalue().lower()
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k "parse_pack or show or verify"
  ```

  Expected: collection error / failures — `warroom_setup.prebrief` does not exist yet.

- [ ] **Create `template/warroom_setup/prebrief.py`** with exactly:

  ```python
  """Pre-brief pack operator surface. Stdlib only, Python >=3.9.

  A pack is a trio: a bundle loader (skill-bundles/<pack>.yaml), member skills
  (skills/<m>/SKILL.md), and a briefing/version-anchor doc
  (shared/prebrief/<pack>.md). This module reads the doc, reports/verifies pack
  integrity, (re)syncs the persona injection, pins via the user-owned local/
  namespace, and posts an opt-in fleet nudge over the mailbox.

  No new config keys (V-1 uses the local/ pin). No Hermes calls except the
  best-effort `mailbox` shell-out in `announce`.
  """
  import json
  import os
  import re
  import subprocess
  import sys
  from pathlib import Path
  from typing import Dict, List, Optional

  _SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


  def pack_doc_path(profile_root, pack):
      # type: (Path, str) -> Path
      return Path(profile_root) / "shared" / "prebrief" / ("%s.md" % pack)


  def local_pin_path(profile_root, pack):
      # type: (Path, str) -> Path
      return Path(profile_root) / "local" / "prebrief" / ("%s.md" % pack)


  def _frontmatter(text):
      # type: (str) -> str
      lines = text.split("\n")
      if not lines or lines[0].strip() != "---":
          raise ValueError("pack doc missing YAML frontmatter")
      out = []
      for line in lines[1:]:
          if line.strip() == "---":
              return "\n".join(out)
          out.append(line)
      raise ValueError("unclosed pack-doc frontmatter")


  def _scalar(fm, key):
      # type: (str, str) -> Optional[str]
      m = re.search(r"^%s:\s*(\S+)\s*$" % re.escape(key), fm, re.M)
      return m.group(1) if m else None


  def _parse_doc_text(text):
      # type: (str) -> Dict
      fm = _frontmatter(text)
      pack = _scalar(fm, "pack")
      version = _scalar(fm, "pack_version")
      members = re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)
      body_version = None
      m = re.search(r"^Pack version:\s*(\S+)\s*$", text, re.M)
      if m:
          body_version = m.group(1)
      return {"pack": pack, "pack_version": version, "members": members,
              "body_version": body_version}


  def parse_pack(profile_root, pack):
      # type: (Path, str) -> Dict
      """Parse the pack doc (raises FileNotFoundError if absent)."""
      return _parse_doc_text(pack_doc_path(profile_root, pack).read_text(encoding="utf-8"))


  def _bundle_skills(profile_root, pack):
      # type: (Path, str) -> List[str]
      bundle = Path(profile_root) / "skill-bundles" / ("%s.yaml" % pack)
      if not bundle.is_file():
          return []
      text = bundle.read_text(encoding="utf-8")
      m = re.search(r"^skills:\s*\n((?:\s+-\s*.*\n)+)", text, re.M)
      if not m:
          return []
      return re.findall(r"-\s*([a-z][a-z0-9-]*)", m.group(1))


  def _member_installed(profile_root, member):
      # type: (Path, str) -> bool
      return (Path(profile_root) / "skills" / member / "SKILL.md").is_file()


  def _pin_version(profile_root, pack):
      # type: (Path, str) -> Optional[str]
      pin = local_pin_path(profile_root, pack)
      if not pin.is_file():
          return None
      try:
          return _parse_doc_text(pin.read_text(encoding="utf-8")).get("pack_version")
      except ValueError:
          return None


  def show(profile_root, pack="warroom", out=None):
      # type: (Path, str, object) -> int
      out = out if out is not None else sys.stdout
      try:
          info = parse_pack(profile_root, pack)
      except (FileNotFoundError, ValueError) as exc:
          out.write("no pack doc for %r: %s\n" % (pack, exc))
          return 1
      out.write("pack: %s\n" % info["pack"])
      out.write("version: %s\n" % info["pack_version"])
      pin = _pin_version(profile_root, pack)
      if pin is not None:
          out.write("pinned: %s (available: %s)\n" % (pin, info["pack_version"]))
      out.write("members:\n")
      for m in info["members"]:
          status = "installed" if _member_installed(profile_root, m) else "MISSING"
          out.write("  - %-20s %s\n" % (m, status))
      return 0


  def verify(profile_root, pack="warroom", out=None):
      # type: (Path, str, object) -> int
      out = out if out is not None else sys.stdout
      doc = pack_doc_path(profile_root, pack)
      if not doc.is_file():
          out.write("FAIL: pack doc not found at %s\n" % doc)
          return 1
      try:
          info = _parse_doc_text(doc.read_text(encoding="utf-8"))
      except ValueError as exc:
          out.write("FAIL: %s\n" % exc)
          return 1
      problems = []  # type: List[str]
      if not info["pack_version"] or not _SEMVER.match(info["pack_version"]):
          problems.append("pack_version missing or not semver")
      if info["body_version"] is None:
          problems.append("body is missing the 'Pack version:' mirror line")
      elif info["body_version"] != info["pack_version"]:
          problems.append("version mirror drift: frontmatter %s != body %s"
                          % (info["pack_version"], info["body_version"]))
      for m in info["members"]:
          if not _member_installed(profile_root, m):
              problems.append("member %r does not resolve to skills/%s/SKILL.md" % (m, m))
      bundle_skills = set(_bundle_skills(profile_root, pack))
      members = set(info["members"])
      if bundle_skills != members:
          problems.append("bundle skills %s != pack members %s"
                          % (sorted(bundle_skills), sorted(members)))
      if problems:
          for p in problems:
              out.write("FAIL: %s\n" % p)
          return 1
      out.write("OK: pack %r v%s, %d members, bundle consistent\n"
                % (info["pack"], info["pack_version"], len(info["members"])))
      return 0
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k "parse_pack or show or verify"
  ```

  Expected: 0 failures; adds 9 tests.

- [ ] **Commit:**

  ```bash
  git add template/warroom_setup/prebrief.py template/tests/test_prebrief.py
  git commit -m "AWR prebrief: prebrief.py parse_pack/show/verify (T8)"
  ```

### Task 9: `prebrief.py` — `sync` + `pin`/`unpin` (atomic)

Files:
- Modify: `template/warroom_setup/prebrief.py`
- Modify: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_prebrief.py`:

  ```python
  # --------------------------------------------------------------------------- #
  # Task 9 -- sync / pin / unpin
  # --------------------------------------------------------------------------- #
  def test_pin_copies_shared_to_local_atomically(tmp_path):
      root = _profile_with_pack(tmp_path)
      out = io.StringIO()
      assert prebrief.pin(root, "warroom", out=out) == 0
      pin = root / "local" / "prebrief" / "warroom.md"
      assert pin.is_file()
      assert pin.read_text(encoding="utf-8") == \
          (root / "shared" / "prebrief" / "warroom.md").read_text(encoding="utf-8")
      assert "pinned" in out.getvalue()


  def test_pin_leaves_no_tmp_file(tmp_path):
      root = _profile_with_pack(tmp_path)
      prebrief.pin(root, "warroom", out=io.StringIO())
      leftovers = list((root / "local" / "prebrief").glob("*.tmp"))
      assert leftovers == []


  def test_pin_missing_source_returns_1(tmp_path):
      root = _profile_with_pack(tmp_path, with_doc=False)
      out = io.StringIO()
      assert prebrief.pin(root, "warroom", out=out) == 1


  def test_unpin_removes_local_override(tmp_path):
      root = _profile_with_pack(tmp_path)
      prebrief.pin(root, "warroom", out=io.StringIO())
      out = io.StringIO()
      assert prebrief.unpin(root, "warroom", out=out) == 0
      assert not (root / "local" / "prebrief" / "warroom.md").exists()
      assert "unpinned" in out.getvalue()


  def test_unpin_when_not_pinned_is_noop_zero(tmp_path):
      root = _profile_with_pack(tmp_path)
      out = io.StringIO()
      assert prebrief.unpin(root, "warroom", out=out) == 0
      assert "not pinned" in out.getvalue()


  def test_sync_delegates_to_persona_sync(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      (root / "local").mkdir(exist_ok=True)
      (root / "local" / "agent.json").write_text(
          json.dumps({"agent_name": "aria", "handle": "aria-sh",
                      "display_name": "Aria", "model": "opus",
                      "specialist_prefix": "aria", "agent_fingerprint": "aria-xyz"}),
          encoding="utf-8")
      calls = {}

      def fake_run(manifest, repo_root, ident, check=False):
          calls["manifest"] = Path(manifest)
          calls["repo_root"] = Path(repo_root)
          return 0

      monkeypatch.setattr(prebrief.persona_sync, "run", fake_run)
      (root / "manifest.json").write_text('{"header":"h","outputs":[]}', encoding="utf-8")
      out = io.StringIO()
      assert prebrief.sync(root, out=out) == 0
      assert calls["manifest"] == root / "manifest.json"


  def test_sync_no_identity_returns_2(tmp_path):
      root = _profile_with_pack(tmp_path)
      out = io.StringIO()
      assert prebrief.sync(root, out=out) == 2
      assert "warroom setup" in out.getvalue()
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k "pin or unpin or sync"
  ```

  Expected: failures — `prebrief.pin` / `unpin` / `sync` and the `prebrief.persona_sync` attribute do not exist yet.

- [ ] **Edit `prebrief.py` — add the imports + the three verbs.** Add these imports immediately after the `from typing import Dict, List, Optional` line:

  ```python
  from . import persona_sync
  from .agent_model import load as load_identity
  ```

  Append these functions to the END of `template/warroom_setup/prebrief.py`:

  ```python
  def _atomic_copy_text(src, dst, mode=0o600):
      # type: (Path, Path, int) -> None
      """Copy src -> dst atomically (temp + os.replace) under the same dir."""
      dst.parent.mkdir(parents=True, exist_ok=True)
      text = Path(src).read_text(encoding="utf-8")
      tmp = str(dst) + ".tmp"
      try:
          Path(tmp).write_text(text, encoding="utf-8")
          try:
              os.chmod(tmp, mode)
          except OSError:
              pass
          os.replace(tmp, str(dst))
      except BaseException:
          try:
              os.unlink(tmp)
          except OSError:
              pass
          raise


  def pin(profile_root, pack="warroom", out=None):
      # type: (Path, str, object) -> int
      """Freeze the briefing: copy shared/prebrief/<pack>.md ->
      local/prebrief/<pack>.md (user-owned, survives `hermes profile update`).
      Atomic write. Returns 1 if the shared source is absent."""
      out = out if out is not None else sys.stdout
      src = pack_doc_path(profile_root, pack)
      if not src.is_file():
          out.write("cannot pin %r: no shared pack doc at %s\n" % (pack, src))
          return 1
      dst = local_pin_path(profile_root, pack)
      _atomic_copy_text(src, dst)
      out.write("pinned %r -> %s\n" % (pack, dst))
      return 0


  def unpin(profile_root, pack="warroom", out=None):
      # type: (Path, str, object) -> int
      """Remove the local pin so the shared doc governs again. No-op (exit 0)
      when not pinned."""
      out = out if out is not None else sys.stdout
      dst = local_pin_path(profile_root, pack)
      if not dst.exists():
          out.write("%r not pinned (no %s)\n" % (pack, dst))
          return 0
      os.remove(str(dst))
      out.write("unpinned %r (removed %s)\n" % (pack, dst))
      return 0


  def sync(profile_root, out=None):
      # type: (Path, object) -> int
      """Regenerate SOUL.md + the Claude head from the manifest (delegates to
      persona_sync.run). Returns 2 when no identity exists yet."""
      out = out if out is not None else sys.stdout
      profile_root = Path(profile_root)
      ident = load_identity(profile_root / "local" / "agent.json")
      if ident is None:
          out.write("no identity yet - run `warroom setup` first\n")
          return 2
      return persona_sync.run(profile_root / "manifest.json", profile_root,
                              ident, check=False)
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k "pin or unpin or sync"
  ```

  Expected: 0 failures; adds 7 tests.

- [ ] **Commit:**

  ```bash
  git add template/warroom_setup/prebrief.py template/tests/test_prebrief.py
  git commit -m "AWR prebrief: sync + atomic pin/unpin verbs (T9)"
  ```

### Task 10: `prebrief.py` — `announce` (opt-in mailbox nudge, fail-soft)

Files:
- Modify: `template/warroom_setup/prebrief.py`
- Modify: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_prebrief.py`:

  ```python
  # --------------------------------------------------------------------------- #
  # Task 10 -- announce (opt-in mailbox nudge; fail-soft)
  # --------------------------------------------------------------------------- #
  def test_announce_invokes_mailbox_send(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      captured = {}

      def fake_discover(env=None, repo_search_start=None):
          return Path("/fake/mailbox")

      class _Res:
          returncode = 0
          stdout = "sent"
          stderr = ""

      def fake_run(argv, **kw):
          captured["argv"] = argv
          return _Res()

      monkeypatch.setattr(prebrief.enroll, "discover_mailbox_cli", fake_discover)
      monkeypatch.setattr(prebrief.subprocess, "run", fake_run)
      out = io.StringIO()
      rc = prebrief.announce(root, pack="warroom", version=None, out=out)
      assert rc == 0
      argv = captured["argv"]
      assert argv[0] == "/fake/mailbox"
      assert "--session" in argv and "send" in argv
      # the broadcast body names the version it resolved from the pack doc
      body = argv[-1]
      assert "1.0.0" in body and "restart" in body.lower()


  def test_announce_uses_explicit_version_when_given(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      captured = {}
      monkeypatch.setattr(prebrief.enroll, "discover_mailbox_cli",
                          lambda env=None, repo_search_start=None: Path("/fake/mailbox"))

      class _Res:
          returncode = 0
          stdout = ""
          stderr = ""

      monkeypatch.setattr(prebrief.subprocess, "run",
                          lambda argv, **kw: captured.__setitem__("argv", argv) or _Res())
      prebrief.announce(root, pack="warroom", version="2.5.0", out=io.StringIO())
      assert "2.5.0" in captured["argv"][-1]


  def test_announce_fail_soft_when_cli_absent(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      monkeypatch.setattr(prebrief.enroll, "discover_mailbox_cli",
                          lambda env=None, repo_search_start=None: None)
      out = io.StringIO()
      rc = prebrief.announce(root, pack="warroom", version=None, out=out)
      assert rc == 1  # non-zero, but did NOT raise
      assert "mailbox CLI not found" in out.getvalue()


  def test_announce_fail_soft_on_nonzero_send(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      monkeypatch.setattr(prebrief.enroll, "discover_mailbox_cli",
                          lambda env=None, repo_search_start=None: Path("/fake/mailbox"))

      class _Res:
          returncode = 1
          stdout = ""
          stderr = "no session id (run inside a Claude session)"

      monkeypatch.setattr(prebrief.subprocess, "run", lambda argv, **kw: _Res())
      out = io.StringIO()
      rc = prebrief.announce(root, pack="warroom", version=None, out=out)
      assert rc == 1
      assert "no session" in out.getvalue()


  def test_announce_fail_soft_on_oserror(tmp_path, monkeypatch):
      root = _profile_with_pack(tmp_path)
      monkeypatch.setattr(prebrief.enroll, "discover_mailbox_cli",
                          lambda env=None, repo_search_start=None: Path("/fake/mailbox"))

      def boom(argv, **kw):
          raise OSError("exec failed")

      monkeypatch.setattr(prebrief.subprocess, "run", boom)
      out = io.StringIO()
      rc = prebrief.announce(root, pack="warroom", version=None, out=out)
      assert rc == 1  # OSError swallowed -> fail-soft
      assert "could not post" in out.getvalue().lower()
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k announce
  ```

  Expected: failures — `prebrief.announce` and the `prebrief.enroll` attribute do not exist yet.

- [ ] **Edit `prebrief.py` — add the `enroll` import + `announce`.** Add to the imports (after the `from . import persona_sync` line added in Task 9):

  ```python
  from . import enroll
  ```

  Append this function to the END of `template/warroom_setup/prebrief.py`:

  ```python
  _ANNOUNCE_SESSION = "warroom-prebrief-announce"


  def announce(profile_root, pack="warroom", version=None, out=None, env=None):
      # type: (Path, str, Optional[str], object, Optional[dict]) -> int
      """Opt-in fleet nudge (P-2). Posts a board broadcast via the discovered
      mailbox CLI: 'pre-brief pack <pack> updated to v<ver>; restart to pick it
      up'. PULL semantics are unchanged — content still arrives via the next
      `hermes profile update` + session restart; this is only a soft signal.

      Fail-soft by contract: a missing CLI, a non-zero exit (e.g. no daemon / no
      session), or an OSError prints a warning and returns 1 WITHOUT raising. It
      never blocks the pack. The version defaults to the pack doc's pack_version.
      """
      out = out if out is not None else sys.stdout
      profile_root = Path(profile_root)
      ver = version
      if ver is None:
          try:
              ver = parse_pack(profile_root, pack).get("pack_version") or "?"
          except (FileNotFoundError, ValueError):
              ver = "?"
      cli = enroll.discover_mailbox_cli(env=env, repo_search_start=profile_root)
      if cli is None:
          out.write("announce: mailbox CLI not found; skipping fleet nudge "
                    "(content still arrives via `hermes profile update`)\n")
          return 1
      body = ("pre-brief pack %r updated to v%s; restart your session to pick it "
              "up (run `hermes profile update` first)" % (pack, ver))
      argv = [str(cli), "--session", _ANNOUNCE_SESSION, "send", "--to", "*",
              "--kind", "note", body]
      try:
          res = subprocess.run(argv, capture_output=True, text=True, env=env)
      except OSError as exc:
          out.write("announce: could not post nudge (%s)\n" % exc)
          return 1
      if res.returncode != 0:
          detail = (res.stderr or res.stdout or "").strip()
          out.write("announce: mailbox send failed (%s); nudge not posted\n" % detail)
          return 1
      out.write("announce: posted pre-brief v%s nudge to the board\n" % ver)
      return 0
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k announce
  ```

  Expected: 0 failures; adds 5 tests.

- [ ] **Commit:**

  ```bash
  git add template/warroom_setup/prebrief.py template/tests/test_prebrief.py
  git commit -m "AWR prebrief: announce verb — opt-in fail-soft mailbox nudge (T10)"
  ```

### Task 11: Wire `warroom prebrief <verb>` into the CLI

Files:
- Modify: `template/warroom_setup/cli.py`
- Modify: `template/tests/test_prebrief.py`
- Test: `template/tests/test_prebrief.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_prebrief.py`:

  ```python
  # --------------------------------------------------------------------------- #
  # Task 11 -- CLI dispatch + exit-code matrix (mirrors test_assimilate matrix)
  # --------------------------------------------------------------------------- #
  from warroom_setup import cli  # noqa: E402


  def test_cli_prebrief_help_lists_verbs():
      parser = cli._build_parser()
      ns = parser.parse_args(["prebrief", "show"])
      assert ns.cmd == "prebrief" and ns.verb == "show"
      ns = parser.parse_args(["prebrief", "pin", "--pack", "warroom"])
      assert ns.verb == "pin" and ns.pack == "warroom"
      ns = parser.parse_args(["prebrief", "announce", "--version", "2.0.0"])
      assert ns.verb == "announce" and ns.version == "2.0.0"
      ns = parser.parse_args(["prebrief", "unpin"])
      assert ns.verb == "unpin"


  def test_cli_prebrief_verify_dispatches(tmp_path, monkeypatch, capsys):
      root = _profile_with_pack(tmp_path)
      monkeypatch.setattr(cli, "_profile_root", lambda: root)
      rc = cli.main(["prebrief", "verify"])
      assert rc == 0
      assert "OK" in capsys.readouterr().out


  def test_cli_prebrief_show_dispatches(tmp_path, monkeypatch, capsys):
      root = _profile_with_pack(tmp_path)
      monkeypatch.setattr(cli, "_profile_root", lambda: root)
      rc = cli.main(["prebrief", "show"])
      assert rc == 0
      assert "pack: warroom" in capsys.readouterr().out


  def test_cli_prebrief_no_verb_returns_2(capsys):
      rc = cli.main(["prebrief"])
      assert rc == 2


  def test_cli_prebrief_exit_code_matrix(tmp_path, monkeypatch):
      # 0 -- verify healthy pack
      healthy = _profile_with_pack(tmp_path / "healthy")
      monkeypatch.setattr(cli, "_profile_root", lambda: healthy)
      assert cli.main(["prebrief", "verify"]) == 0

      # 1 -- verify broken pack (missing member skills)
      broken = _profile_with_pack(tmp_path / "broken", with_skills=False)
      monkeypatch.setattr(cli, "_profile_root", lambda: broken)
      assert cli.main(["prebrief", "verify"]) == 1

      # 1 -- show with no pack doc at all
      nodoc = _profile_with_pack(tmp_path / "nodoc", with_doc=False)
      monkeypatch.setattr(cli, "_profile_root", lambda: nodoc)
      assert cli.main(["prebrief", "show"]) == 1

      # 0 -- pin then unpin a healthy pack
      monkeypatch.setattr(cli, "_profile_root", lambda: healthy)
      assert cli.main(["prebrief", "pin"]) == 0
      assert cli.main(["prebrief", "unpin"]) == 0

      # 2 -- sync with no identity
      assert cli.main(["prebrief", "sync"]) == 2
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py -q -k "cli_prebrief"
  ```

  Expected: failures — `prebrief` is not a registered subcommand; `parse_args(["prebrief", ...])` errors (SystemExit) or `args.cmd` is unhandled (falls to `print_help` + return 2 with no `verb` attr).

- [ ] **Edit `cli.py` — import the module.** Replace this line (`template/warroom_setup/cli.py:7`):

  ```python
  from . import enroll, setup
  ```

  with:

  ```python
  from . import enroll, prebrief as prebrief_mod, setup
  ```

- [ ] **Edit `cli.py` — register the subparser.** Immediately AFTER the `assimilate` subparser block (after the line `a.add_argument("--yes", action="store_true", ...)` and before `return parser`), insert:

  ```python
      pb = sub.add_parser("prebrief",
                          help="inspect / verify / sync / pin / announce the pre-brief pack")
      pb.add_argument("verb", nargs="?", default=None,
                      choices=["show", "verify", "sync", "pin", "unpin", "announce"],
                      help="prebrief action")
      pb.add_argument("--pack", default="warroom", help="pack name (default: warroom)")
      pb.add_argument("--version", default=None,
                      help="announce: version to advertise (default: pack doc version)")
  ```

- [ ] **Edit `cli.py` — add the dispatch handler.** Add this function after `cmd_assimilate` (before `def main`):

  ```python
  def cmd_prebrief(args):
      # type: (argparse.Namespace) -> int
      """Dispatch `warroom prebrief <verb>`. Exit codes:
        0 — verb succeeded
        1 — verify failed / show found no doc / announce could not post
        2 — no verb, or sync with no identity
      """
      if args.verb is None:
          print("usage: warroom prebrief {show|verify|sync|pin|unpin|announce}")
          return 2
      root = _profile_root()
      if args.verb == "show":
          return prebrief_mod.show(root, args.pack)
      if args.verb == "verify":
          return prebrief_mod.verify(root, args.pack)
      if args.verb == "sync":
          return prebrief_mod.sync(root)
      if args.verb == "pin":
          return prebrief_mod.pin(root, args.pack)
      if args.verb == "unpin":
          return prebrief_mod.unpin(root, args.pack)
      if args.verb == "announce":
          return prebrief_mod.announce(root, args.pack, version=args.version)
      print("usage: warroom prebrief {show|verify|sync|pin|unpin|announce}")
      return 2
  ```

- [ ] **Edit `cli.py` — route in `main`.** In `main`, immediately after the `if args.cmd == "assimilate": return cmd_assimilate(args)` line, add:

  ```python
      if args.cmd == "prebrief":
          return cmd_prebrief(args)
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief.py \
      template/tests/test_cli.py -q
  ```

  Expected: 0 failures; adds 5 tests. `test_cli.py` (existing CLI tests) stays green.

- [ ] **Commit:**

  ```bash
  git add template/warroom_setup/cli.py template/tests/test_prebrief.py
  git commit -m "AWR prebrief: warroom prebrief CLI verbs + exit-code matrix (T11)"
  ```

### Task 12: Phase 3 checkpoint — full suite green + sanitize

Files:
- Test: whole `template/` suite

#### Steps

- [ ] **Run the full suite + sanitize:**

  ```bash
  template/.venv/bin/python -m pytest template -q
  python3 template/scripts/sanitize_check.py template/
  ```

  Expected: 0 failures (Phase 2 total + 26 tests across Tasks 8-11). `sanitize_check` exits 0.

- [ ] **No commit** (checkpoint only).

---

## Phase 4 — bundle pre-brief reference + propagation docs + fleet nudge docs (hub repo DEFERRED, D-5)

Phase 4's external first-party hub repo is DEFERRED (adopted D-5): NO hub-repo files are created. This phase ships (a) the bundle `instruction` pre-brief reference built ON TOP of the L1 orchestrator's final instruction text, and (b) README documentation of pinning, the propagation channels (`hermes profile update` primary; `hermes skills tap`/`update` secondary for foreign/assimilated profiles), the fleet-update recipe, the slug-collision note, the `warroom-verifier` non-member rationale, and the opt-in `warroom prebrief announce` nudge.

### Task 13: Bundle `instruction` references the pre-brief (preserving the L1 intake order)

Files:
- Modify: `template/skill-bundles/warroom.yaml`
- Modify: `template/tests/test_warroom_bundle.py`
- Test: `template/tests/test_warroom_bundle.py`, `template/tests/test_confidence_gate.py`

> **SEAM NOTE for the executor (Task 13 is SELF-CONTAINED — no hard dependency on L1).** This task edits the `instruction:` block. There are two branch states, and the literal block below handles BOTH because it reproduces the L1 plan's final intake-order text verbatim (`docs/superpowers/plans/2026-06-09-awr-l1-orchestrator.md:552-554`) and appends one pre-brief sentence:
> - **L1 NOT landed (live instruction is the one-liner `War-room protocol. Follow confidence-gate before posting any claim to the channel.`):** WRITE the full literal block shown in the "Rewrite the bundle" step. This authors the intake order (`orient -> triage -> severity -> route -> lane -> first post`) here, in this plan — it is NOT "inventing" foreign text; it is the exact text L1 was designed to ship, and Task 13's own test below is the authority for it on this branch.
> - **L1 landed (live instruction already names the intake order):** the live first three lines should be byte-identical to the literal block's first three lines (both come from the same L1 final text). If they match, write the literal block as shown. If they DIFFER (L1 shipped different wording), KEEP the live L1 text verbatim and append ONLY the two-line pre-brief sentence — then STOP and surface the wording difference to the lead so the divergence is reconciled, rather than silently overwriting L1's text.
>
> In all cases: the skill list stays `[warroom, confidence-gate]` (pack members unchanged); you APPEND a pre-brief reference; you do NOT remove or reorder the intake words. Task 13's test `test_bundle_instruction_references_prebrief_without_regressing_intake` asserts the six intake words IN ORDER + `confidence-gate` + a pre-brief reference, so it is green on either branch state after you apply the block.

#### Steps

- [ ] **Read the live bundle first.**

  ```bash
  cat template/skill-bundles/warroom.yaml
  ```

  Note the exact current `instruction:` wording. Two cases (see the SEAM NOTE): if it is the one-liner `War-room protocol. Follow confidence-gate before posting any claim to the channel.` (L1 NOT landed), the literal block below authors the full intake order. If it ALREADY names the intake order (L1 landed), your rewrite keeps that text verbatim and only adds the pre-brief sentence.

- [ ] **Write the failing test.** Append to the END of `template/tests/test_warroom_bundle.py`:

  ```python
  def test_bundle_instruction_references_prebrief_without_regressing_intake():
      bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text(encoding="utf-8")
      m = re.search(r"^instruction:\s*\|\n((?:[ \t]+.*\n?)*)", bundle, re.M)
      assert m, "bundle must carry a block-scalar instruction"
      instr = m.group(1).lower()
      # pre-brief reference is present
      assert "pre-brief" in instr or "prebrief" in instr
      # AND the L1 intake order is NOT regressed (same guard L1 ships)
      order = ["orient", "triage", "severity", "route", "lane", "first post"]
      idxs = [instr.find(w) for w in order]
      assert -1 not in idxs, "intake steps must still be named: %r" % order
      assert idxs == sorted(idxs), "intake steps must stay in order"
      assert "confidence-gate" in instr
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_warroom_bundle.py -q \
      -k prebrief_without_regressing
  ```

  Expected: `1 failed` — `test_bundle_instruction_references_prebrief_without_regressing_intake` fails. If L1 has NOT landed (live one-liner), it fails on the intake-order assertion (and the pre-brief assertion). If L1 HAS landed, it fails on the "pre-brief" assertion only (the intake words are already present, but no pre-brief reference is). Either way it is red before the rewrite.

- [ ] **Rewrite the bundle.** Overwrite `template/skill-bundles/warroom.yaml` with exactly (skills list unchanged; the first three instruction lines are the L1 final text verbatim, plus one appended pre-brief sentence):

  ```yaml
  name: warroom
  description: Agentic war-room coordination bundle.
  skills:
    - warroom
    - confidence-gate
  instruction: |
    War-room protocol. On /warroom run the intake in order: orient -> triage ->
    severity -> route -> lane -> first post. Follow confidence-gate before
    posting any claim to the channel.
    You have already read the war-room pre-brief (shared/prebrief/warroom.md,
    injected into SOUL); this bundle loads the full protocol bodies on demand.
  ```

  If the live L1 instruction text differs from the first three lines shown here, KEEP the live L1 text verbatim and append ONLY the final two-line pre-brief sentence — do not regress L1's wording.

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_warroom_bundle.py \
      template/tests/test_confidence_gate.py -q
  ```

  Expected: 0 failures; adds 1 test. The L1 `test_bundle_instruction_names_intake_order` (if present) and `test_warroom_bundle_includes_confidence_gate` stay green (skills list unchanged; intake words preserved).

- [ ] **Commit:**

  ```bash
  git add template/skill-bundles/warroom.yaml template/tests/test_warroom_bundle.py
  git commit -m "AWR prebrief: bundle instruction references the pre-brief (preserves L1 intake) (T13)"
  ```

### Task 14: README — pre-brief pack, propagation, pinning, skills-tap, non-member, announce

Files:
- Modify: `template/README.md`
- Modify: `template/tests/test_template_content.py`
- Test: `template/tests/test_template_content.py`

#### Steps

- [ ] **Write the failing tests.** Append to the END of `template/tests/test_template_content.py`:

  ```python
  # ---- Pre-brief pack: README documents the feature + propagation ----

  def test_readme_documents_prebrief_pack():
      readme = (ROOT / "README.md").read_text(encoding="utf-8")
      assert "## Pre-brief pack" in readme
      assert "shared/prebrief/warroom.md" in readme
      assert "/warroom" in readme                       # full-protocol expansion
      assert "hermes profile update" in readme          # primary propagation
      assert "hermes skills tap" in readme              # secondary (foreign profiles)
      assert "local/prebrief/" in readme                # pinning
      assert "warroom prebrief" in readme               # operator CLI
      assert "announce" in readme                       # opt-in fleet nudge


  def test_readme_documents_prebrief_slug_collision_and_nonmember():
      readme = (ROOT / "README.md").read_text(encoding="utf-8")
      # slug-collision note (bundle wins over the like-named skill — keep it)
      assert "bundle wins" in readme.lower()
      # warroom-verifier is a deliberate NON-member (role-specific)
      assert "warroom-verifier" in readme
  ```

- [ ] **Run — expect red:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_template_content.py -q -k prebrief
  ```

  Expected: `2 failed` — the README has no pre-brief section yet. (The existing `test_readme_preserves_existing_sections` and `test_readme_documents_mailbox_and_mcp_and_sanitization` must still pass after the edit — the new section is APPEND-only.)

> **PRECONDITION NOTE:** The README text below references `skills/warroom-verifier/SKILL.md` as a deliberate NON-member. This is FORWARD documentation — `warroom-verifier` ships with position 3 (DEFCON) and may NOT exist on this branch. No test in this plan asserts the dir exists (Task 3's integrity tests only check the two real members, `confidence-gate` and `warroom`). Do not create the dir; do not gate on it. The README prose stands as accurate forward documentation whether or not the dir is present.

- [ ] **Edit `README.md` — add the section.** Locate the line `## MCP servers` and insert this block immediately ABOVE it (so the new section sits after `## Coordination (mailbox routing)` and before `## MCP servers`). Add exactly:

  ```markdown
  ## Pre-brief pack

  Every war-room agent has read the same baseline briefing before its first
  message: the **pre-brief pack**. A pack is a trio:

  - **Loader** — `skill-bundles/warroom.yaml`, a Hermes bundle that loads the
    member skills under one `/warroom` slash command.
  - **Bodies** — the member skills `skills/warroom/SKILL.md` and
    `skills/confidence-gate/SKILL.md`.
  - **Briefing + version anchor** — `shared/prebrief/warroom.md`, the
    human-readable briefing and the manifest-of-record (`pack_version`,
    `members`, `summary`).

  **How it loads on startup.** Nothing auto-loads a bundle on session start —
  Hermes loads a bundle only when you type `/warroom`. So the *briefing* is
  injected into the always-loaded `SOUL.md` and the Claude head agent file via
  persona-sync (a "War-room pre-brief" section, sourced from
  `shared/prebrief/warroom.md`). That guarantees the briefing + the condensed
  gate contract are in context on turn 1 with **zero `~/.claude/settings.json`
  edits**. The full skill bodies are a `/warroom` expansion away when you need
  the verbatim commands. Run `bash scripts/setup.sh --sync` (or `warroom setup
  --sync`) after editing the pack doc to regenerate the section.

  **Members.** The pack members are exactly `confidence-gate` and `warroom`.
  `skills/warroom-verifier/SKILL.md` is a deliberate **non-member**: it is the
  role-specific verifier protocol that only verifier-role agents need, not part
  of the baseline every agent reads.

  **Slug collision is intentional.** A member skill is named `warroom` and the
  bundle is also named `warroom`. When a bundle and a skill share a slug the
  **bundle wins** — `/warroom` loads the bundle (verified Hermes behavior). Do
  not "fix" this by renaming; it preserves the `/warroom` UX.

  **Operator CLI.** `warroom prebrief` (stdlib, no deps):

  | Verb | Purpose |
  |---|---|
  | `warroom prebrief show` | pack name, version, member install status, pin gap |
  | `warroom prebrief verify` | integrity check (members resolve, bundle consistent, version mirror); exit non-zero on a broken pack |
  | `warroom prebrief sync` | regenerate the SOUL/head pre-brief section |
  | `warroom prebrief pin` / `unpin` | freeze/unfreeze the briefing via `local/prebrief/warroom.md` |
  | `warroom prebrief announce [--version <v>]` | opt-in fleet nudge over the mailbox |

  **Pinning (freeze against upstream).** `warroom prebrief pin` copies
  `shared/prebrief/warroom.md` to `local/prebrief/warroom.md`. The `local/`
  overlay is user-owned and **survives `hermes profile update`**, and
  persona-sync prefers `local/prebrief/warroom.md` over the shipped doc. Use it
  to freeze the briefing while a pack update is pending your review;
  `warroom prebrief show` reports the pinned-vs-available version gap.
  `warroom prebrief unpin` removes the override so upstream governs again.

  ### Propagating a pack update

  **Primary — template-born agents: `hermes profile update`.** The whole
  `template/` tree is the distribution. A pack change is a new commit + a bumped
  `distribution.yaml::version`. The operator runs `hermes profile update
  <name>`; the distribution-owned tree (skills, the bundle, the pack doc) is
  replaced in place while `config.yaml`, `.env`, and the entire `local/` overlay
  (including any pin) are preserved. `skill-bundles` and `shared` are declared in
  `distribution_owned` so this stays explicit. The pack moves atomically —
  bundle, bodies, and doc travel together. A change lands on the **next session**
  of an updated profile; this is pull, not push. Fleet recipe:

  ```sh
  for p in alpha-sh beta-sh foreign-sh; do hermes profile update "$p"; done
  ```

  (A cron over your war-room profiles is the operator's call.)

  **Secondary — foreign / assimilated profiles: `hermes skills tap`.** A profile
  that was NOT installed from this distribution (e.g. one that ran
  `warroom assimilate`) cannot receive the pack via `profile update`. For those,
  an individual sharpened skill (e.g. an updated `confidence-gate`) can be
  published as a first-party hub skill and pulled per-skill:

  ```sh
  hermes skills tap add <owner>/<repo>          # register a source (untrusted by default)
  hermes skills install <owner>/<repo>/<skill>  # pull-install (security-scanned)
  hermes skills update [<name>]                 # pull the latest for installed skills
  ```

  This channel is **per-skill, pull-based, and security-scanned** — the bundle
  and the pack doc do NOT travel with a single tapped skill, so it is the right
  tool for distributing one sharpened skill to a heterogeneous fleet, not for
  moving the whole pack. **Never add a tap you do not control or trust;** the
  shipped `skills/.hub/taps.json` stays empty and the pack never adds a tap on
  your behalf. The first-party hub repo itself is a separate effort (deferred).

  **Opt-in nudge.** `warroom prebrief announce` posts a soft board signal
  ("pre-brief pack updated to v<x>; restart to pick it up") via the mailbox. It
  is a *signal*, not a push of content — the content still arrives via the next
  `hermes profile update` + session restart. It fails soft (warns, never blocks)
  when the mailbox CLI or daemon is unavailable.
  ```

- [ ] **Run — expect green:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_template_content.py -q
  ```

  Expected: 0 failures; adds 2 tests. `test_readme_preserves_existing_sections` and `test_readme_documents_mailbox_and_mcp_and_sanitization` stay green (append-only edit).

- [ ] **Run sanitize on the README change:**

  ```bash
  python3 template/scripts/sanitize_check.py template/
  ```

  Expected: `sanitize_check: clean (template/)`, exit 0. (All names used in README are neutral: `alpha-sh`, `beta-sh`, `foreign-sh`, `<owner>/<repo>`.)

- [ ] **Commit:**

  ```bash
  git add template/README.md template/tests/test_template_content.py
  git commit -m "AWR prebrief: README — pack, propagation, pinning, skills-tap, announce (T14)"
  ```

### Task 15: Integration smoke — install/update propagation + pin survival (gated on `--runintegration`)

Files:
- Create: `template/tests/test_prebrief_e2e.py`
- Test: `template/tests/test_prebrief_e2e.py`

This task implements the spec's "Integration (real Hermes, gated like the existing `--runintegration` smoke)" block (design.md:528-538). The four assertions: (1) install lands the trio (`skill-bundles/<pack>.yaml`, `skills/<members>/SKILL.md`, `shared/prebrief/<pack>.md`); (2) the bundle loader exposes `/<pack>` and its skills resolve to bodies; (3) bump `pack_version` + update REPLACES pack doc + bundle + skills while PRESERVING `config.yaml` and `local/` (the pull-on-update propagation proof); (4) a `local/prebrief/<pack>.md` pin SURVIVES update (the pin proof).

> **WHY SIMULATION, NOT A LIVE `hermes` CALL (matches `test_installer_e2e.py`).** The shipped `template/.venv` is Python 3.9, but the installed Hermes (`/Users/aahil/.hermes/hermes-agent`) requires 3.10+ (`X | Y` union syntax at import), so `hermes_cli.profile_distribution` is NOT importable under the test interpreter — a live `hermes profile install` cannot run in-process here. The existing Feature-B smokes solve this the same way: they SIMULATE the `hermes profile install`/`update` subprocess and materialize a real profile tree, then assert on it (`test_installer_e2e.py:1-8`). This task reproduces the VERIFY-AGAINST-HERMES #2 copy contract faithfully — catch-all `staged.iterdir()` copy, skip `USER_OWNED_EXCLUDE` (which includes `local`), preserve `config.yaml` on update — verified against the live loop at `profile_distribution.py:560-570`. If you have a 3.10+ interpreter with Hermes importable, you MAY additionally drive the real `_copy_dist_payload`; the assertions are identical. (Stash `template/.venv` before any real `hermes profile install` — handoff §0.)

#### Steps

- [ ] **Write the integration smoke (gated, skipped by default).** Create `template/tests/test_prebrief_e2e.py` with exactly:

  ```python
  """Pre-brief pack integration smoke (spec design.md:528-538).

  Gated: @integration + --runintegration (mirrors test_installer_e2e.py). The
  `hermes profile install`/`update` copy is SIMULATED by reproducing the verified
  _copy_dist_payload contract (catch-all staged.iterdir() copy; skip
  USER_OWNED_EXCLUDE incl. `local`; preserve config.yaml on update) — see
  VERIFY-AGAINST-HERMES #2 and profile_distribution.py:560-570. A real Hermes
  cannot be imported under the 3.9 template .venv (Hermes needs 3.10+).

  Run: template/.venv/bin/python -m pytest tests/test_prebrief_e2e.py --runintegration -q
  """
  import shutil
  import sys
  from pathlib import Path

  import pytest

  pytestmark = pytest.mark.integration

  TEMPLATE = Path(__file__).resolve().parents[1]
  if str(TEMPLATE) not in sys.path:
      sys.path.insert(0, str(TEMPLATE))

  from warroom_setup import prebrief  # noqa: E402

  # The verified USER_OWNED_EXCLUDE subset that matters for a pack update: `local`
  # is preserved (pins survive); config.yaml is preserved on update. Mirrors
  # profile_distribution.USER_OWNED_EXCLUDE (`local` at :118) + the preserve-config
  # branch (:568-570).
  _USER_OWNED_EXCLUDE = {"local", "memories", "sessions", "logs", "plans",
                         "workspace", "home", "cron"}


  def _copy_dist_payload(staged, target, *, preserve_config):
      """Faithful re-impl of the verified Hermes catch-all copy loop.

      Copies every top-level entry from `staged` into `target` EXCEPT names in
      USER_OWNED_EXCLUDE; preserves an existing config.yaml when preserve_config.
      """
      target.mkdir(parents=True, exist_ok=True)
      for entry in sorted(staged.iterdir()):
          name = entry.name
          if name in _USER_OWNED_EXCLUDE:
              continue
          if name == "config.yaml" and preserve_config and (target / "config.yaml").exists():
              continue
          dest = target / name
          if entry.is_dir():
              if dest.exists():
                  shutil.rmtree(dest)
              shutil.copytree(entry, dest,
                              ignore=lambda d, names: [n for n in names if n in _USER_OWNED_EXCLUDE])
          else:
              shutil.copy2(entry, dest)


  def _stage_from_template(staged):
      """Build a staged distribution carrying the pack trio + config.yaml."""
      staged.mkdir(parents=True, exist_ok=True)
      for d in ("skill-bundles", "shared", "skills"):
          shutil.copytree(TEMPLATE / d, staged / d)
      shutil.copy2(TEMPLATE / "config.yaml", staged / "config.yaml")
      return staged


  def _install(staged, target):
      _copy_dist_payload(staged, target, preserve_config=False)


  def _update(staged, target):
      _copy_dist_payload(staged, target, preserve_config=True)


  # --------------------------------------------------------------------------- #
  # (1) install lands the trio
  # --------------------------------------------------------------------------- #
  def test_install_lands_pack_trio(tmp_path):
      staged = _stage_from_template(tmp_path / "staged")
      target = tmp_path / "profile"
      _install(staged, target)
      assert (target / "skill-bundles" / "warroom.yaml").is_file()
      assert (target / "shared" / "prebrief" / "warroom.md").is_file()
      members = prebrief.parse_pack(target, "warroom")["members"]
      assert members == ["confidence-gate", "warroom"]
      for m in members:
          assert (target / "skills" / m / "SKILL.md").is_file()


  # --------------------------------------------------------------------------- #
  # (2) the loader exposes /<pack> and its skills resolve to bodies
  # --------------------------------------------------------------------------- #
  def test_installed_bundle_loads_member_bodies(tmp_path):
      staged = _stage_from_template(tmp_path / "staged")
      target = tmp_path / "profile"
      _install(staged, target)
      # `bundles list` would show /warroom because the loader file is at the
      # scanned path <profile>/skill-bundles/warroom.yaml (VERIFY-AGAINST-HERMES #3).
      assert (target / "skill-bundles" / "warroom.yaml").is_file()
      # invoking /warroom loads member bodies -> each member resolves to a body.
      assert prebrief.verify(target, "warroom") == 0  # bundle skills == members, bodies present


  # --------------------------------------------------------------------------- #
  # (3) bump + update REPLACES the pack, PRESERVES config.yaml + local/
  # --------------------------------------------------------------------------- #
  def test_update_replaces_pack_and_preserves_config_and_local(tmp_path):
      staged = _stage_from_template(tmp_path / "staged")
      target = tmp_path / "profile"
      _install(staged, target)

      # operator owns config.yaml + a local/ overlay
      (target / "config.yaml").write_text("OPERATOR EDITED CONFIG\n", encoding="utf-8")
      (target / "local").mkdir(parents=True, exist_ok=True)
      (target / "local" / "keepme.txt").write_text("operator data\n", encoding="utf-8")

      # bump pack_version in the staged distribution (the upstream change)
      doc = staged / "shared" / "prebrief" / "warroom.md"
      bumped = doc.read_text(encoding="utf-8").replace(
          "pack_version: 1.0.0", "pack_version: 1.1.0").replace(
          "Pack version: 1.0.0", "Pack version: 1.1.0")
      doc.write_text(bumped, encoding="utf-8")

      _update(staged, target)

      # pack doc + bundle + skills were REPLACED (new version present)
      assert prebrief.parse_pack(target, "warroom")["pack_version"] == "1.1.0"
      assert (target / "skill-bundles" / "warroom.yaml").is_file()
      for m in ("confidence-gate", "warroom"):
          assert (target / "skills" / m / "SKILL.md").is_file()
      # config.yaml + local/ were PRESERVED (operator content intact)
      assert (target / "config.yaml").read_text(encoding="utf-8") == "OPERATOR EDITED CONFIG\n"
      assert (target / "local" / "keepme.txt").read_text(encoding="utf-8") == "operator data\n"


  # --------------------------------------------------------------------------- #
  # (4) a local/prebrief/<pack>.md pin SURVIVES update
  # --------------------------------------------------------------------------- #
  def test_pin_survives_update(tmp_path):
      staged = _stage_from_template(tmp_path / "staged")
      target = tmp_path / "profile"
      _install(staged, target)

      # operator pins the briefing at v1.0.0
      assert prebrief.pin(target, "warroom") == 0
      pin = target / "local" / "prebrief" / "warroom.md"
      pinned_before = pin.read_text(encoding="utf-8")
      assert "pack_version: 1.0.0" in pinned_before

      # upstream bumps to 1.1.0 and the operator updates
      doc = staged / "shared" / "prebrief" / "warroom.md"
      doc.write_text(doc.read_text(encoding="utf-8").replace(
          "pack_version: 1.0.0", "pack_version: 1.1.0").replace(
          "Pack version: 1.0.0", "Pack version: 1.1.0"), encoding="utf-8")
      _update(staged, target)

      # the pin SURVIVED (local/ is user-owned) and still reads 1.0.0,
      # while the shared doc now reads 1.1.0 -> show reports the gap.
      assert pin.is_file()
      assert pin.read_text(encoding="utf-8") == pinned_before
      assert prebrief.parse_pack(target, "warroom")["pack_version"] == "1.1.0"
  ```

- [ ] **Run — skipped by default, green when gated:**

  ```bash
  template/.venv/bin/python -m pytest template/tests/test_prebrief_e2e.py -q
  template/.venv/bin/python -m pytest template/tests/test_prebrief_e2e.py --runintegration -q
  ```

  Expected: the first run reports `4 skipped` (the `@integration` marker; no `--runintegration`). The second run reports `4 passed` (install lands the trio; the loader's skills resolve; update replaces the pack while preserving `config.yaml` + `local/`; the pin survives). These 4 do NOT count toward the default-suite delta (they are skipped without the flag).

- [ ] **Commit:**

  ```bash
  git add template/tests/test_prebrief_e2e.py
  git commit -m "AWR prebrief: gated integration smoke — install/update propagation + pin survival (T15)"
  ```

### Task 16: Phase 4 + final checkpoint — full suite + sanitize + grep guards + manual reload note

Files:
- Test: whole `template/` suite + sanitization guards

#### Steps

- [ ] **Run the full suite (default — integration smoke skipped):**

  ```bash
  template/.venv/bin/python -m pytest template -q
  ```

  Expected: 0 failures. Default-run additions across Tasks 1-14 = 4+2+4+4+2+9+7+5+5+2+1 = 45 new PASSING tests, plus Task 15's +4 SKIPPED (gated on `--runintegration`). Only "0 failures" and the +45 passing / +4 skipped delta from THIS plan are load-bearing — do not assert an absolute count (positions 1-4 may have added tests).

- [ ] **Run the gated integration smoke once to confirm it is green:**

  ```bash
  template/.venv/bin/python -m pytest template --runintegration -q
  ```

  Expected: 0 failures; Task 15's 4 integration tests now run and pass (alongside the existing `--runintegration` smokes).

- [ ] **Run the sanitization guards (handoff §0 + Appendix):**

  ```bash
  python3 template/scripts/sanitize_check.py template/
  grep -RIn -i "twelvelabs|twelve labs|@twelvelabs|tl-branding" template/
  grep -RIn "normalize_unsentineled_blocks|_strip_bare_block|_MANAGED_BLOCKS" template/
  ```

  Expected: `sanitize_check` exits 0 (`clean`); both greps print nothing (empty).

- [ ] **Confirm no settings.json edit + no new deps + stdlib-only (locked decision #9, stack):**

  ```bash
  grep -RIn "settings.json" template/warroom_setup/prebrief.py
  grep -RIn "import requests\|import yaml\|pip install" template/warroom_setup/prebrief.py
  git diff --stat main -- template/pyproject.toml
  ```

  Expected: the first two greps print nothing; `pyproject.toml` is unchanged (no diff). `prebrief.py` imports only stdlib (`json os re subprocess sys pathlib typing`) + sibling modules (`persona_sync`, `agent_model`, `enroll`).

- [ ] **Operator manual-reload note (Open Q4 — NOT a CI assertion).** Record in the PR/handoff that SOUL.md injection is the *guaranteed* turn-1 surface (Hermes always loads it); whether the Claude head file `~/.claude/agents/<name>.md` re-reads each session should be manually confirmed once on a live profile (`warroom prebrief sync`, then open a Claude session and check the "War-room pre-brief" section is present). This is a known-open verification, not a blocker.

- [ ] **No commit** (final checkpoint only; all changes already committed in Tasks 1-15).

---

## Self-review (author's, completed before returning)

- **Spec coverage:** Build order Phase 0 → Task 0 (branch-state baseline); Phase 1 → Tasks 1-4; Phase 2 → Tasks 5-7; Phase 3 → Tasks 8-12; Phase 4 (hub repo deferred per D-5; announce nudge + skills-tap README per project brief) → Tasks 10 (announce) + 13 (bundle) + 14 (README) + 15 (integration smoke) + 16 (final checkpoint). Every spec "File-path map" entry maps to a task: pack doc → T1; distribution.yaml → T2; pack-integrity tests → T3; SANITIZATION.md → T3; manifest.json + persona_sync → T5; persona-sync tests → T5/T6; prebrief.py → T8/T9/T10; cli.py → T11; bundle → T13; README → T14. Spec "Test strategy" coverage: the `template/tests` unit bullets land across T1-T14; the spec's **Integration (real Hermes, gated like `--runintegration`)** block — install lands the trio, loader exposes `/<pack>`, bump+update replaces pack while preserving `config.yaml`+`local/`, pin survives — lands in **T15** (simulation-based, mirroring `test_installer_e2e.py`, because Hermes is not importable under the 3.9 template `.venv`). `schema.py` deliberately untouched (deviation documented).
- **The 4 plan-defect classes:** (1) Write-path: every test reads the same literal path the impl writes (`shared/prebrief/warroom.md`, `local/prebrief/warroom.md`, `manifest.json`, `skill-bundles/warroom.yaml`); the pin write target = persona-sync `local_override` read target. (2) Real-surface APIs: `persona_sync.run`, `enroll.discover_mailbox_cli`, `setup._atomic_write_text` pattern, `agent_model.load`, `mailbox send --session ... --to * --kind note <body>` — all verified against live source. (3) Regex vs real content: frontmatter splitter, members list, bundle `skills:` extractor, `Pack version:` mirror, instruction block scalar — all validated against the exact committed pack doc / bundle. (4) Hermes-side: the three VERIFY-AGAINST-HERMES checks all PASS with file:line evidence; the `mailbox send` session requirement is verified and handled fail-soft; the load-bearing propagation/pin behavior is additionally exercised end-to-end by the gated T15 integration smoke, which reproduces the verified `_copy_dist_payload` copy contract (`profile_distribution.py:560-570`) — Hermes itself is not importable under the 3.9 template `.venv`, so the smoke is simulation-based exactly like the existing `test_installer_e2e.py`.
- **Cross-task name consistency:** `parse_pack`, `show`, `verify`, `sync`, `pin`, `unpin`, `announce`, `pack_doc_path`, `local_pin_path`, `_atomic_copy_text`, `_ANNOUNCE_SESSION`, `prebrief_mod`, `cmd_prebrief`, `_resolve_section_source`, `optional`, `local_override` — spelled identically across Tasks 5-14 and their tests.
- **Placeholder scan:** no TBD / TODO / "similar to" / "add error handling" — every code/test block is complete and literal.
