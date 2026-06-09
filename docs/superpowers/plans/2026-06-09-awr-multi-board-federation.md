# Multi-Board Hierarchical Federation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Boards form a tree (squad → team → org) with bidirectional signal flow — escalations resolve upward, broadcasts resolve downward — via read-time federated views over the mailbox engine's in-RAM state, plus an operator topology surface and template-side `parent` enrollment wiring.

**Architecture:** Topology lives in each board's `meta.json` (`parent` link); pure tree helpers in `coordination/src/mailbox/boards.py` walk the engine's boards dict. `Message.scope` (`local|escalate|broadcast`) drives read-time resolution in `poll_inbox`/`federated_messages` — no copying, no loops; Phase 3 adds opt-in push delivery for `delivery: push` boards. The agent still joins exactly ONE home board (`MAILBOX_BOARD` unchanged); the template records the parent link at enroll time via the discovered mailbox CLI.

**Tech Stack:** Python 3.9+ stdlib only. `coordination/` mailbox package (engine + UNIX-socket daemon + argparse CLI + pytest), `template/` war-room setup package (schema/selectables/setup/enroll + pytest). No new dependencies.

Spec: `docs/superpowers/specs/2026-06-09-awr-multi-board-federation-design.md`. Build-order position 1 of 5 (nothing has landed before this plan; current `main`-derived source is the baseline).

> **Commit-message convention:** the `git commit -m "AWR federation: … (Tn)"` lines below give only the subject. The executor's environment auto-appends the repo-house `Co-Authored-By:` trailer to every commit, matching existing repo commits (e.g. `e7a2cfc`); do not hand-add it.

## Adopted decisions

- **D1 `delivery` default = `pull`** (read-time). `push` is per-board opt-in via a new `set-delivery` verb; an absent `delivery` key in `meta.json` means `pull`. (Spec Open question 1, recommendation adopted.)
- **D2 `ps` federation default = federated.** `ps`/`claims`/`inbox` take `federated=True` by default; `--local` scopes down. On a board with no parent/children, federated resolution degenerates to exactly the v1 local behavior, so default-federated is behaviorally identical for all existing installs and tests. (Spec Open question 2, recommendation adopted.)
- **D3 No retroactive re-delivery on re-parent.** Push fan-out happens only at `send` time; topology edits never replay old broadcasts. Delivered copies carry `origin_message_id`, and the fan-out dedups on it as a safety guard. (Spec Open question 3, recommendation adopted.)

## Deviations

- **DV1 — `test_schema.py::test_war_room_keys_exact` (template) is updated (one tuple).** This existing test asserts the exact `WAR_ROOM_KEYS` tuple; adding the spec-required `parent` key is impossible without touching it. It is a deliberate change-detector test whose designed update procedure IS this edit. No other existing test file is modified; no behavioral expectation is weakened. (`test_defaults_cover_war_room_keys` uses set-equality and stays green untouched.)
- **DV2 — `parent` is added to `WAR_ROOM_KEYS` only, NOT `MAILBOX_KEYS`.** The spec says "WAR_ROOM_KEYS / MAILBOX_KEYS" but its own config example places `parent` under `war_room:`. `patch_mailbox_block` always renders ALL of its keys (empty as `""`), so adding `parent` there would change every rendered `mailbox:` block and break `test_mailbox_keys_exact` plus byte-level installer expectations. `patch_war_room_block` omits empty values, so the `war_room:` route changes zero rendered bytes for non-federated profiles. `parent` is also not a runtime routing key (federation is engine-side; `.env` is unchanged by spec), so it does not belong in the mailbox routing block (locked decision #1).
- **DV3 — `Message.to_dict()` uses sparse serialization** (`scope` omitted when `"local"`, `origin_message_id` omitted when `None`). The frozen contract §3 and `coordination/tests/test_models.py::test_message_to_dict_has_all_fields` assert the exact v1 dict; sparse serialization keeps every existing coordination test green UNCHANGED and keeps on-disk JSON byte-compatible for local messages. `from_dict` restores defaults, so round-trips are lossless.
- **DV4 — no `read` CLI verb exists** in `coordination/src/mailbox/cli.py` (verified: subcommands are join/claim/release/claim-lane/release-lane/list-lanes/seize/request-release/send/inbox/claims/ps/board/whoami). The spec's "`ps`/`claims`/`inbox`/`read` gain `--federated/--local`" is applied to the verbs that actually exist: `ps`, `claims`, `inbox`.
- **DV5 — `coordination/hooks/session_start.py` needs NO code change.** The hook only prints the `colocated` dict that `engine.join` returns (verified hooks/session_start.py:59-71); the federated colocation summary is delivered by making `join`'s colocation counting subtree-aware engine-side. The spec's file map listed the hook; the real seam is `engine.join`.
- **DV6 — added a `set-delivery <board> (pull|push)` CLI verb + `set_delivery` engine op** (not in the spec's CLI table). Required: the spec gates Phase 3 behind a per-board `delivery` meta flag but provides no way to set it.
- **DV7 — template `enroll.bootstrap(parent=...)` calls the engine via the discovered mailbox CLI subprocess** (`mailbox create-board <board> --parent <p>`), not via `import mailbox.client`. enroll.py's locked discipline is "never imports mailbox.client" (enroll.py:9-10, pinned by `test_enroll_status_does_not_import_mailbox_client`); the CLI subprocess is the existing sanctioned channel (it is what `discover_mailbox_cli` exists for).
- **DV8 — claims/lanes *enforcement* stays board-scoped; only *visibility* federates.** Spec §4 says "Lane semantics unchanged; visibility widens to the subtree". `check_write`/`claim_lane` conflict scans are untouched (presence/claims roll up only — federating enforcement would create asymmetric deny behavior between parent and child). `list_claims --federated` and `federated_claims` widen visibility. A test pins this interpretation (T10).
- **DV9 — `warroom/SKILL.md` gets a small ADDITIVE federation section here** (spec File-path map lists BOTH `warroom/SKILL.md` and `confidence-gate/SKILL.md` as deliverables of THIS spec — deferring it would narrow coverage, which is not authorized). T9 appends a sentinel-free "Federation" subsection documenting `mailbox escalate` / `mailbox broadcast` / `mailbox tree` / `mailbox fleet`; `confidence-gate/SKILL.md` keeps its gate-discipline note. The L1-orchestrator plan (build-order position 4) may later rewrite `warroom/SKILL.md` wholesale; an additive section now is forward-compatible (a wholesale rewrite supersedes it) and discharges this spec's deliverable without a cross-plan promise. The file has no managed sentinels, so the append is a plain text edit.

## Verified baselines & test commands (run 2026-06-09 on this checkout)

```bash
# coordination suite (the federation engine lives here)
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
# → 174 passed, 1 skipped

# template suite
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
# → 409 passed, 10 skipped

# sanitization guard
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
# → "sanitize_check: clean (template/)", exit 0
```

Suite expectations below are expressed as **0 failures + a delta**; never as absolute future totals. `coordination/pyproject.toml` carries `[tool.pytest.ini_options] testpaths=["tests"] pythonpath=["src"]`; `coordination/tests/conftest.py` provides the `engine` (tmp state dir + fake `clock`) and `tmp_home` (temp `MAILBOX_HOME`/`MAILBOX_SOCKET` + PYTHONPATH) fixtures, and forces a short pytest basetemp for AF_UNIX socket length.

**Source surfaces verified against live code (line numbers current as of this plan):**
`engine.join` engine.py:98-159 · `_ensure_board` engine.py:33-40 · load-time merge engine.py:72-95 · `send` engine.py:452-472 (`# ----- send -----` banner at 452) · `poll_inbox` engine.py:475-497 · `list_claims` engine.py:522-551 · `ps` engine.py:564-583 · `Message` models.py:67-96 · `derive_repo_board`/`board_id_for_name` boards.py:8-44 · `build_parser`/`main` cli.py:91-258 · `OPS`/`dispatch` protocol.py:14-33 · hook board env read hooks/session_start.py:33 · contract doc exists at `coordination/docs/internal/contract.md` · template `WAR_ROOM_KEYS` schema.py:11-14, `DEFAULTS` schema.py:22-31 · `patch_war_room_block` setup.py:182-220 (omits empty-string values, accepts any `WAR_ROOM_KEYS` kwarg, raises TypeError otherwise) · `TEXT_FIELDS` selectables.py:59-80 · `enroll.bootstrap` enroll.py:174-232, `EnrollState` enroll.py:103-123 · `cmd_enroll` template cli.py:55-93. Engine ops are invoked **by name through `protocol.dispatch` (`getattr(engine, op)(**args)`)** — every new verb is an engine method whose name appears in `protocol.OPS`; `bin/mailbox` is a pure `python -m mailbox.cli` shim and needs no change.

---

# Phase 1 — Foundation + read-time federation

## Task 1: `Message.scope` with sparse, back-compat serialization

Boards/messages are the substrate; scope comes first so everything downstream can build on it.

**Files**
- Modify: `coordination/src/mailbox/models.py`
- Test: `coordination/tests/test_federation.py` (new)

**Steps**

- [ ] Create `coordination/tests/test_federation.py` with the failing scope tests:

```python
"""Multi-board federation tests (spec 2026-06-09): Message.scope, tree helpers,
topology ops, federated reads, fleet, push delivery. Engine-level tests use the
`engine` fixture from conftest (tmp state dir + fake clock)."""
from pathlib import Path

from mailbox.models import Message


# ---------------------------------------------------------------------------
# T1 — Message.scope (sparse serialization: local omitted, v1-byte-compatible)
# ---------------------------------------------------------------------------

def test_message_scope_default_omitted_from_to_dict():
    m = Message(id="msg_0123456789ab", board="named-squad-api",
                from_session="s1", from_label="alpha-sh", to="*",
                kind="note", body="hello", created=5.0)
    d = m.to_dict()
    assert m.scope == "local"
    assert "scope" not in d        # sparse: local messages keep the v1 shape


def test_message_scope_serialized_when_non_local():
    m = Message(id="msg_0123456789ab", board="named-squad-api",
                from_session="s1", from_label="alpha-sh", to="*",
                kind="note", body="hello", created=5.0, scope="escalate")
    d = m.to_dict()
    assert d["scope"] == "escalate"
    assert Message.from_dict(d) == m


def test_message_from_dict_back_compat_defaults_scope_local():
    d = {"id": "msg_0123456789ab", "board": "named-squad-api",
         "from_session": "s1", "from_label": "alpha-sh", "to": "*",
         "kind": "note", "body": "hello", "created": 5.0}
    assert Message.from_dict(d).scope == "local"


def test_message_round_trip_preserves_local_scope():
    m = Message(id="msg_0123456789ab", board="b", from_session="s1",
                from_label="l", to="*", kind="note", body="x", created=1.0)
    assert Message.from_dict(m.to_dict()) == m
```

- [ ] Run it and confirm the expected failure:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 4 failures, each `TypeError: __init__() got an unexpected keyword argument 'scope'` or `AttributeError: 'Message' object has no attribute 'scope'`.

- [ ] Implement: in `coordination/src/mailbox/models.py`, replace the whole `Message` dataclass (models.py:67-96) with:

```python
@dataclass
class Message:
    id: str                    # "msg_" + 12 hex
    board: str
    from_session: str
    from_label: str
    to: str                    # session_id | label | "*"
    kind: str                  # "note"|"release-request"|"dep-signal"|"handoff"|"done"
    body: str
    created: float
    read_by: List[str] = field(default_factory=list)
    ref_paths: List[str] = field(default_factory=list)
    scope: str = "local"       # "local" | "escalate" | "broadcast"

    def to_dict(self) -> dict:
        d = asdict(self)
        # Sparse serialization: the default scope is omitted so local messages
        # keep the exact v1 JSON shape (contract §3) on disk and on the wire.
        # from_dict restores the default, so round-trips are lossless.
        if d.get("scope") == "local":
            d.pop("scope", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            id=d["id"],
            board=d["board"],
            from_session=d["from_session"],
            from_label=d["from_label"],
            to=d["to"],
            kind=d["kind"],
            body=d["body"],
            created=d["created"],
            read_by=list(d.get("read_by", [])),
            ref_paths=list(d.get("ref_paths", [])),
            scope=d.get("scope", "local"),
        )
```

- [ ] Run the new file again (expect 4 passed), then the full coordination suite — the sparse `to_dict` is exactly what keeps `test_models.py::test_message_to_dict_has_all_fields` green unchanged:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
```

Expected: 0 failures (adds 4 tests over the 174-passed/1-skipped baseline).

- [ ] Commit:

```bash
git add coordination/src/mailbox/models.py coordination/tests/test_federation.py
git commit -m "AWR federation: Message.scope with sparse back-compat serialization (T1)"
```

## Task 2: Tree helpers in `boards.py` (`ancestors`/`descendants`/`subtree`/validation)

Pure functions over the engine's boards-meta dict (`{board_id: meta}`); no engine import, matching boards.py's existing dependency-free style.

**Files**
- Modify: `coordination/src/mailbox/boards.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T2 — boards.py tree helpers (pure walks over the boards-meta dict)
# ---------------------------------------------------------------------------

from mailbox import boards as boards_mod


def _meta(bid, parent=None):
    return {"id": bid, "origin": "named:" + bid, "name": bid,
            "created": 0.0, "parent": parent}


def _forest():
    return {
        "named-org": _meta("named-org"),
        "named-team-platform": _meta("named-team-platform", parent="named-org"),
        "named-squad-api": _meta("named-squad-api", parent="named-team-platform"),
        "named-squad-web": _meta("named-squad-web", parent="named-team-platform"),
        "named-solo": _meta("named-solo"),
    }


def _chain(n):
    """n boards named-l0 .. named-l<n-1>, each the parent of the next."""
    boards = {}
    prev = None
    for i in range(n):
        bid = "named-l%d" % i
        boards[bid] = _meta(bid, parent=prev)
        prev = bid
    return boards


def test_ancestors_walks_to_root():
    b = _forest()
    assert boards_mod.ancestors(b, "named-squad-api") == [
        "named-team-platform", "named-org"]
    assert boards_mod.ancestors(b, "named-org") == []


def test_descendants_breadth_first_sorted():
    b = _forest()
    assert boards_mod.descendants(b, "named-org") == [
        "named-team-platform", "named-squad-api", "named-squad-web"]
    assert boards_mod.descendants(b, "named-squad-api") == []


def test_subtree_includes_self():
    b = _forest()
    assert boards_mod.subtree(b, "named-team-platform") == [
        "named-team-platform", "named-squad-api", "named-squad-web"]
    assert boards_mod.subtree(b, "named-solo") == ["named-solo"]


def test_is_ancestor_and_depth_and_height():
    b = _forest()
    assert boards_mod.is_ancestor(b, "named-org", "named-squad-api")
    assert not boards_mod.is_ancestor(b, "named-squad-api", "named-org")
    assert not boards_mod.is_ancestor(b, "named-squad-web", "named-squad-api")
    assert boards_mod.depth(b, "named-org") == 0
    assert boards_mod.depth(b, "named-squad-api") == 2
    assert boards_mod.height(b, "named-org") == 2
    assert boards_mod.height(b, "named-squad-api") == 0


def test_missing_parent_meta_drops_out_of_walk():
    b = _forest()
    del b["named-org"]            # orphan the team board
    assert boards_mod.ancestors(b, "named-squad-api") == ["named-team-platform"]
    assert boards_mod.parent_of(b, "named-team-platform") == "named-org"


def test_walks_are_cycle_safe_on_hand_edited_meta():
    # set_parent validation prevents persisting cycles, but a hand-edited
    # meta.json must never hang the daemon.
    b = {
        "named-a": _meta("named-a", parent="named-b"),
        "named-b": _meta("named-b", parent="named-a"),
    }
    assert boards_mod.ancestors(b, "named-a") == ["named-b"]
    assert "named-b" in boards_mod.descendants(b, "named-a")
    assert boards_mod.height(b, "named-a") >= 1   # terminates


def test_validate_parent_accepts_legal_link():
    b = _forest()
    assert boards_mod.validate_parent(b, "named-solo", "named-org") is None


def test_validate_parent_rejects_self_missing_cycle_depth():
    b = _forest()
    assert "self-parent" in boards_mod.validate_parent(
        b, "named-org", "named-org")
    assert "no-such-board" in boards_mod.validate_parent(
        b, "named-org", "named-ghost")
    assert "cycle" in boards_mod.validate_parent(
        b, "named-org", "named-squad-api")
    deep = _chain(9)              # depths 0..8 == MAX_FEDERATION_DEPTH, legal
    deep["named-extra"] = _meta("named-extra")
    assert "too-deep" in boards_mod.validate_parent(
        deep, "named-extra", "named-l8")
    assert boards_mod.validate_parent(deep, "named-extra", "named-l7") is None
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 9 new failures, `AttributeError: module 'mailbox.boards' has no attribute 'ancestors'` (and siblings).

- [ ] Implement: in `coordination/src/mailbox/boards.py`, change the typing import (line 5) from `from typing import Tuple` to `from typing import List, Optional, Tuple`, then append at end of file:

```python
# --- Federation topology (multi-board federation spec, 2026-06-09) ----------
#
# Pure tree walks over the engine's in-RAM board-meta dict
# ({board_id: meta_dict}). A meta's "parent" key (absent/None = root) is the
# only topology input. Every walk is cycle-safe via a visited set: set_parent
# validation prevents persisting cycles, but a hand-edited meta.json must
# never hang the daemon.

MAX_FEDERATION_DEPTH = 8   # max allowed depth value (root = 0): 9-level chain


def parent_of(boards: dict, board_id: str) -> Optional[str]:
    """The parent board id recorded in board_id's meta, or None (root)."""
    meta = boards.get(board_id) or {}
    return meta.get("parent") or None


def _children_index(boards: dict) -> dict:
    """{parent_id: [child ids, sorted]} over every meta with a parent link."""
    idx = {}
    for bid in boards:
        p = parent_of(boards, bid)
        if p is not None:
            idx.setdefault(p, []).append(bid)
    for p in idx:
        idx[p].sort()
    return idx


def ancestors(boards: dict, board_id: str) -> List[str]:
    """[parent, grandparent, ..., root]. A parent id with no meta (orphan
    link) ends the walk — the missing ancestor just drops out (spec: degrade
    gracefully). Cycle-safe."""
    out = []
    seen = {board_id}
    cur = parent_of(boards, board_id)
    while cur is not None and cur in boards and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = parent_of(boards, cur)
    return out


def descendants(boards: dict, board_id: str) -> List[str]:
    """All transitive children, breadth-first, children sorted by id."""
    idx = _children_index(boards)
    out = []
    seen = {board_id}
    frontier = list(idx.get(board_id, []))
    while frontier:
        bid = frontier.pop(0)
        if bid in seen:
            continue
        seen.add(bid)
        out.append(bid)
        frontier.extend(idx.get(bid, []))
    return out


def subtree(boards: dict, board_id: str) -> List[str]:
    """[board_id] + descendants(board_id)."""
    return [board_id] + descendants(boards, board_id)


def is_ancestor(boards: dict, a: str, b: str) -> bool:
    """True iff a is a transitive ancestor of b."""
    return a in ancestors(boards, b)


def depth(boards: dict, board_id: str) -> int:
    """Edges from board_id up to its root (root = 0)."""
    return len(ancestors(boards, board_id))


def height(boards: dict, board_id: str) -> int:
    """Longest downward path (edges) from board_id; 0 for a leaf."""
    idx = _children_index(boards)
    best = 0
    seen = {board_id}
    stack = [(board_id, 0)]
    while stack:
        bid, d = stack.pop()
        for cid in idx.get(bid, []):
            if cid in seen:
                continue
            seen.add(cid)
            if d + 1 > best:
                best = d + 1
            stack.append((cid, d + 1))
    return best


def validate_parent(boards: dict, board_id: str, parent_id: str) -> Optional[str]:
    """Validate linking board_id under parent_id. Returns an error string, or
    None when the link is legal. Rejects (a) self-parenting, (b) a parent that
    is a descendant of the board (cycle), (c) a parent with no meta, and
    (d) a resulting tree deeper than MAX_FEDERATION_DEPTH."""
    if parent_id == board_id:
        return "self-parent: a board cannot be its own parent"
    if parent_id not in boards:
        return "no-such-board: " + str(parent_id)
    if parent_id in descendants(boards, board_id):
        return "cycle: %s is a descendant of %s" % (parent_id, board_id)
    if depth(boards, parent_id) + 1 + height(boards, board_id) > MAX_FEDERATION_DEPTH:
        return "too-deep: federation depth would exceed %d" % MAX_FEDERATION_DEPTH
    return None
```

- [ ] Run `test_federation.py` again (expect all green), then the full coordination suite (0 failures; adds 9 tests).
- [ ] Commit:

```bash
git add coordination/src/mailbox/boards.py coordination/tests/test_federation.py
git commit -m "AWR federation: boards.py tree helpers + cycle/depth validation (T2)"
```

## Task 3: Engine topology ops — `create_board`, `set_parent`, `tree`, meta `parent`, audit log

**Files**
- Modify: `coordination/src/mailbox/engine.py`
- Modify: `coordination/src/mailbox/protocol.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T3 — engine topology ops: create_board / set_parent / tree / audit
# ---------------------------------------------------------------------------

from mailbox import protocol
from mailbox.engine import MailboxEngine


def test_create_board_records_and_persists_parent(engine, clock):
    assert engine.create_board("org") == {
        "id": "named-org", "name": "org", "parent": None}
    res = engine.create_board("team-platform", parent="org")
    assert res == {"id": "named-team-platform", "name": "team-platform",
                   "parent": "named-org"}
    # persisted: a reloaded engine sees the link (meta.json round-trip)
    reloaded = MailboxEngine(engine.state_dir, now_fn=lambda: clock.t)
    assert reloaded.boards["named-team-platform"]["parent"] == "named-org"


def test_create_board_requires_existing_parent(engine):
    res = engine.create_board("team-platform", parent="ghost")
    assert res == {"error": "no-such-board: ghost"}
    assert "named-team-platform" not in engine.boards   # nothing persisted


def test_create_board_is_idempotent_and_can_link_existing(engine):
    engine.create_board("org")
    engine.create_board("squad-api")                    # root at first
    res = engine.create_board("squad-api", parent="org")  # later: link it
    assert res["parent"] == "named-org"
    # re-running without parent leaves the link alone
    res2 = engine.create_board("squad-api")
    assert res2["parent"] == "named-org"


def test_set_parent_reparents_detaches_and_reports_was(engine):
    engine.create_board("org")
    engine.create_board("team-platform", parent="org")
    engine.create_board("squad-api", parent="team-platform")
    res = engine.set_parent("squad-api", "org")
    assert res == {"id": "named-squad-api", "parent": "named-org",
                   "was": "named-team-platform"}
    res = engine.set_parent("squad-api", detach=True)
    assert res == {"id": "named-squad-api", "parent": None,
                   "was": "named-org"}


def test_set_parent_rejects_self_cycle_and_missing(engine):
    engine.create_board("org")
    engine.create_board("team-platform", parent="org")
    assert "self-parent" in engine.set_parent("org", "org")["error"]
    assert "cycle" in engine.set_parent("org", "team-platform")["error"]
    assert "no-such-board" in engine.set_parent("ghost", "org")["error"]
    assert "no-such-board" in engine.set_parent("org", "ghost")["error"]
    # nothing was persisted by the rejected calls
    assert engine.boards["named-org"].get("parent") is None


def test_set_parent_rejects_overdeep_tree(engine):
    prev = None
    for i in range(9):                       # named-l0 .. named-l8: depth 0..8
        name = "l%d" % i
        res = engine.create_board(name, parent=prev)
        assert "error" not in res, res
        prev = name
    engine.create_board("extra")
    assert "too-deep" in engine.set_parent("extra", "l8")["error"]
    assert "error" not in engine.set_parent("extra", "l7")


def test_join_ensure_board_preserves_pre_created_parent(engine, tmp_path):
    # enroll pre-creates the home board with its parent; a later session join
    # must not clobber the link (_ensure_board early-returns on existing id).
    engine.create_board("org")
    engine.create_board("squad-api", parent="org")
    d = tmp_path / "w"
    d.mkdir()
    engine.join(session_id="s1", label="api-sh", cwd=str(d),
                board_name="squad-api")
    assert engine.boards["named-squad-api"]["parent"] == "named-org"


def test_tree_renders_forest_with_orphans(engine):
    engine.create_board("org")
    engine.create_board("team-platform", parent="org")
    engine.create_board("squad-api", parent="team-platform")
    engine.create_board("solo")
    # hand-orphan a board (parent meta gone) — tree degrades gracefully
    engine.boards["named-lost"] = {"id": "named-lost", "origin": "named:lost",
                                   "name": "lost", "created": 0.0,
                                   "parent": "named-ghost"}
    data = engine.tree()
    ids = [n["id"] for n in data["roots"]]
    assert ids == ["named-lost", "named-org", "named-solo"]
    lost = data["roots"][0]
    assert lost["orphan"] is True
    org = data["roots"][1]
    assert org["orphan"] is False
    assert [c["id"] for c in org["children"]] == ["named-team-platform"]
    assert [c["id"] for c in org["children"][0]["children"]] == [
        "named-squad-api"]
    # subtree render + bad ref
    sub = engine.tree(board="team-platform")
    assert sub["roots"][0]["id"] == "named-team-platform"
    assert engine.tree(board="ghost") == {"error": "no-such-board: ghost"}


def test_topology_mutations_append_audit_log(engine):
    engine.create_board("org")
    engine.create_board("team-platform", parent="org")
    engine.set_parent("team-platform", detach=True)
    lines = (Path(engine.state_dir) / "federation.log").read_text().splitlines()
    assert any("create-board id=named-org parent=None" in l for l in lines)
    assert any("create-board id=named-team-platform parent=named-org" in l
               for l in lines)
    assert any("set-parent id=named-team-platform parent=None "
               "was=named-org" in l for l in lines)


def test_dispatch_exposes_topology_ops(engine):
    resp = protocol.dispatch(engine, {"op": "create_board",
                                      "args": {"name": "org"}})
    assert resp["ok"] is True and resp["data"]["id"] == "named-org"
    resp = protocol.dispatch(engine, {"op": "set_parent",
                                      "args": {"board": "org", "detach": True}})
    assert resp["ok"] is True and resp["data"]["parent"] is None
    resp = protocol.dispatch(engine, {"op": "tree", "args": {}})
    assert resp["ok"] is True and "roots" in resp["data"]
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 10 new failures, `AttributeError: 'MailboxEngine' object has no attribute 'create_board'` (and `unknown op: create_board` for the dispatch test).

- [ ] Implement in `coordination/src/mailbox/engine.py`. First replace `_ensure_board` (engine.py:33-40) with:

```python
    def _ensure_board(self, board_id, origin, name=None, parent=None):
        if board_id in self.boards:
            return
        meta = {"id": board_id, "origin": origin, "name": name,
                "created": self._now(), "parent": parent}
        self.boards[board_id] = meta
        store.atomic_write_json(
            os.path.join(self._board_dir(board_id), "meta.json"), meta)

    def _persist_board_meta(self, board_id):
        store.atomic_write_json(
            os.path.join(self._board_dir(board_id), "meta.json"),
            self.boards[board_id])

    def _resolve_board_ref(self, ref):
        """Resolve an operator-supplied board reference to a known board id:
        an exact id first (named-/repo-/cwd-), else the named-board id for
        the bare name. None when nothing matches."""
        if ref is None:
            return None
        if ref in self.boards:
            return ref
        named = boards_mod.board_id_for_name(ref)
        if named in self.boards:
            return named
        return None

    def _audit_federation(self, line):
        """Append one line to <state_dir>/federation.log. This is an
        append-only audit log, not a state record — the atomic temp+replace
        rule applies to records; logs append (same idiom as the enroll/gate
        logs on the template side)."""
        os.makedirs(self.state_dir, exist_ok=True)
        path = os.path.join(self.state_dir, "federation.log")
        with open(path, "a") as fh:
            fh.write("%.3f %s\n" % (self._now(), line))
```

- [ ] Then insert the topology ops right after the `join` method (after engine.py:159, before `heartbeat`):

```python
    # ----- topology (multi-board federation) -----
    def create_board(self, name, parent=None):
        """Mint (or reuse) the named board for `name`; optionally link it
        under an EXISTING parent (operators build top-down). Validation per
        boards.validate_parent; errors are returned as {"error": ...} and
        never persisted."""
        board_id = boards_mod.board_id_for_name(name)
        parent_id = None
        if parent is not None:
            parent_id = self._resolve_board_ref(parent)
            if parent_id is None:
                return {"error": "no-such-board: " + str(parent)}
        if board_id not in self.boards:
            self._ensure_board(board_id, "named:" + name, name=name)
        if parent_id is not None:
            err = boards_mod.validate_parent(self.boards, board_id, parent_id)
            if err:
                return {"error": err}
            self.boards[board_id]["parent"] = parent_id
            self._persist_board_meta(board_id)
        self._audit_federation(
            "create-board id=%s parent=%s" % (board_id, parent_id))
        meta = self.boards[board_id]
        return {"id": board_id, "name": meta.get("name"),
                "parent": meta.get("parent")}

    def set_parent(self, board, parent=None, detach=False):
        """Re-parent `board` under `parent` (cycle/depth-validated), or
        detach it into a root. Both refs accept a board id or a bare name."""
        board_id = self._resolve_board_ref(board)
        if board_id is None:
            return {"error": "no-such-board: " + str(board)}
        was = self.boards[board_id].get("parent")
        if detach:
            self.boards[board_id]["parent"] = None
            self._persist_board_meta(board_id)
            self._audit_federation(
                "set-parent id=%s parent=None was=%s" % (board_id, was))
            return {"id": board_id, "parent": None, "was": was}
        parent_id = self._resolve_board_ref(parent)
        if parent_id is None:
            return {"error": "no-such-board: " + str(parent)}
        err = boards_mod.validate_parent(self.boards, board_id, parent_id)
        if err:
            return {"error": err}
        self.boards[board_id]["parent"] = parent_id
        self._persist_board_meta(board_id)
        self._audit_federation(
            "set-parent id=%s parent=%s was=%s" % (board_id, parent_id, was))
        return {"id": board_id, "parent": parent_id, "was": was}

    # ----- tree -----
    def tree(self, board=None):
        """Topology render data: {"roots": [node...]}; node = {"id", "name",
        "orphan", "children": [...]}. A board whose parent id has no meta is
        surfaced as an orphan root (spec: degrade gracefully). Cycle-safe via
        a visited set."""
        if board is not None:
            root_id = self._resolve_board_ref(board)
            if root_id is None:
                return {"error": "no-such-board: " + str(board)}
            root_ids = [root_id]
            orphans = set()
        else:
            root_ids = []
            orphans = set()
            for bid in sorted(self.boards):
                parent = self.boards[bid].get("parent")
                if not parent:
                    root_ids.append(bid)
                elif parent not in self.boards:
                    root_ids.append(bid)
                    orphans.add(bid)

        seen = set()

        def _node(bid):
            seen.add(bid)
            meta = self.boards.get(bid, {})
            children = []
            for cid in sorted(self.boards):
                if cid in seen:
                    continue
                if self.boards[cid].get("parent") == bid:
                    children.append(_node(cid))
            return {"id": bid, "name": meta.get("name"),
                    "orphan": bid in orphans, "children": children}

        return {"roots": [_node(r) for r in root_ids]}
```

- [ ] In `coordination/src/mailbox/protocol.py`, replace the `OPS` set (protocol.py:14-19) with:

```python
OPS = {
    "join", "heartbeat", "leave", "check_write", "claim", "release", "seize",
    "request_release", "send", "poll_inbox", "list_claims", "ps", "whoami",
    "board", "gc", "ping",
    "claim_lane", "release_lane", "list_lanes",
    "create_board", "set_parent", "tree",
}
```

- [ ] Run `test_federation.py` (all green), then the full coordination suite. Note `test_engine_presence.py::test_ensure_board_persists_meta` stays green: it asserts only `origin`/`name`/`created` keys plus an idempotency self-compare, both unaffected by the added `parent` key.

Expected: 0 failures (adds 10 tests).

- [ ] Commit:

```bash
git add coordination/src/mailbox/engine.py coordination/src/mailbox/protocol.py coordination/tests/test_federation.py
git commit -m "AWR federation: engine create_board/set_parent/tree + parent meta + audit log (T3)"
```

## Task 4: `send(scope=...)` + `federated_messages` read-time resolution

**Files**
- Modify: `coordination/src/mailbox/engine.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T4 — send scope + federated_messages (read-time resolution, the core)
# ---------------------------------------------------------------------------

import hashlib


def _setup_tree(engine, tmp_path):
    """org -> team-platform -> {squad-api, squad-web}; one session per board,
    each with a DISTINCT cwd (so repo boards never overlap)."""
    engine.create_board("org")
    engine.create_board("team-platform", parent="org")
    engine.create_board("squad-api", parent="team-platform")
    engine.create_board("squad-web", parent="team-platform")
    sessions = [
        ("s_org", "org-sh", "org"),
        ("s_team", "team-sh", "team-platform"),
        ("s_api", "api-sh", "squad-api"),
        ("s_web", "web-sh", "squad-web"),
    ]
    for i, (sid, label, board) in enumerate(sessions):
        d = tmp_path / ("cwd%d" % i)
        d.mkdir(exist_ok=True)
        engine.join(session_id=sid, label=label, cwd=str(d), board_name=board)


def test_send_persists_scope_and_validates(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    res = engine.send(session_id="s_api", to="*", kind="note",
                      body="incident", scope="escalate")
    assert res["id"].startswith("msg_")
    assert engine.messages[res["id"]].scope == "escalate"
    assert engine.messages[res["id"]].board == "named-squad-api"
    assert engine.send(session_id="s_api", to="*", kind="note",
                       body="x", scope="sideways") == {
        "error": "bad-scope: sideways"}


def test_federated_messages_own_up_down(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.send(session_id="s_api", to="*", kind="note", body="api local")
    engine.send(session_id="s_api", to="*", kind="note",
                body="api incident", scope="escalate")
    engine.send(session_id="s_org", to="*", kind="note",
                body="org announcement", scope="broadcast")

    team = engine.federated_messages("named-team-platform")
    bodies = {m["body"]: m for m in team}
    assert "api local" not in bodies                  # local stays local
    up = bodies["api incident"]
    assert up["direction"] == "up"
    assert up["origin_board"] == "named-squad-api"
    down = bodies["org announcement"]
    assert down["direction"] == "down"
    assert down["origin_board"] == "named-org"

    org = engine.federated_messages("named-org")
    org_bodies = {m["body"]: m for m in org}
    assert "api incident" in org_bodies               # transitive escalation
    assert org_bodies["org announcement"]["direction"] == "local"

    api = engine.federated_messages("named-squad-api")
    api_bodies = {m["body"]: m for m in api}
    assert api_bodies["api local"]["direction"] == "local"
    assert api_bodies["org announcement"]["direction"] == "down"


def test_federated_messages_siblings_invisible(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.send(session_id="s_api", to="*", kind="note",
                body="api incident", scope="escalate")
    web = engine.federated_messages("named-squad-web")
    assert all(m["body"] != "api incident" for m in web)


def test_federated_messages_root_leaf_degenerate(engine, tmp_path):
    engine.create_board("solo")
    d = tmp_path / "solo"
    d.mkdir()
    engine.join(session_id="s_solo", label="solo-sh", cwd=str(d),
                board_name="solo")
    engine.send(session_id="s_solo", to="*", kind="note", body="hi",
                scope="escalate")
    rows = engine.federated_messages("named-solo")
    assert [m["body"] for m in rows if m["board"] == "named-solo"] == ["hi"]
    assert rows[-1]["direction"] == "local"           # own board, any scope


def test_escalate_audit_logs_sha_never_body(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.send(session_id="s_api", to="*", kind="note",
                body="secret-incident-details", scope="escalate")
    text = (Path(engine.state_dir) / "federation.log").read_text()
    assert "send scope=escalate board=named-squad-api from=api-sh" in text
    assert "secret-incident-details" not in text
    sha = hashlib.sha256(b"secret-incident-details").hexdigest()[:8]
    assert "body_sha=" + sha in text
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 5 new failures — `TypeError: send() got an unexpected keyword argument 'scope'` and `AttributeError: 'MailboxEngine' object has no attribute 'federated_messages'`.

- [ ] Implement in `coordination/src/mailbox/engine.py`. Add `import hashlib` to the top-of-file imports (engine.py:1-4, alphabetical: `hashlib` before `os`). Replace the whole `send` method (engine.py:452-472 pre-task; search for `# ----- send -----`) with:

```python
    # ----- send -----
    def send(self, session_id, to, kind, body, ref_paths=None, scope="local"):
        if scope not in ("local", "escalate", "broadcast"):
            return {"error": "bad-scope: " + str(scope)}
        presence = self.presence.get(session_id)
        if presence is None:
            return {"error": "no presence for session"}
        board = self._primary_board(session_id)
        msg = Message(
            id=self._gen_id("msg_"),
            board=board,
            from_session=session_id,
            from_label=presence.label,
            to=to,
            kind=kind,
            body=body,
            created=self._now(),
            read_by=[],
            ref_paths=list(ref_paths) if ref_paths else [],
            scope=scope,
        )
        self.messages[msg.id] = msg
        self._persist_message(msg)
        if scope != "local":
            body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
            self._audit_federation(
                "send scope=%s board=%s from=%s body_sha=%s"
                % (scope, board, presence.label, body_sha))
        return {"id": msg.id}
```

- [ ] Then insert `federated_messages` directly after the new `send` method (before `# ----- poll_inbox -----`):

```python
    # ----- federated reads (multi-board federation) -----
    def federated_messages(self, board_id):
        """Read-time federation (spec §3): own messages (any scope), plus
        escalations from descendants, plus broadcasts from ancestors. Pure
        filter over the in-RAM message dict; each row is annotated with its
        origin board and direction ("local" | "up" | "down") so a renderer
        can show 'escalated from squad-api' / 'broadcast from org'."""
        anc = set(boards_mod.ancestors(self.boards, board_id))
        desc = set(boards_mod.descendants(self.boards, board_id))
        out = []
        for m in self.messages.values():
            if m.board == board_id:
                direction = "local"
            elif m.board in desc and m.scope == "escalate":
                direction = "up"
            elif m.board in anc and m.scope == "broadcast":
                direction = "down"
            else:
                continue
            d = m.to_dict()
            d["origin_board"] = m.board
            d["direction"] = direction
            out.append(d)
        out.sort(key=lambda d: d["created"])
        return out
```

- [ ] Run `test_federation.py` (all green), then the full coordination suite (0 failures; adds 5 tests — existing `send` callers pass no `scope`, defaulting to `"local"`, and `{"id": ...}` return shape is unchanged).
- [ ] Commit:

```bash
git add coordination/src/mailbox/engine.py coordination/tests/test_federation.py
git commit -m "AWR federation: send scope + federated_messages read-time resolution (T4)"
```

## Task 5: Federated `poll_inbox` + subtree-aware join colocation

**Files**
- Modify: `coordination/src/mailbox/engine.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T5 — federated poll_inbox + subtree-aware join colocation
# ---------------------------------------------------------------------------


def test_poll_inbox_federated_up_and_down(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.poll_inbox("s_org")          # drain any join notes
    engine.poll_inbox("s_api")
    engine.send(session_id="s_api", to="*", kind="note",
                body="api incident", scope="escalate")
    engine.send(session_id="s_org", to="*", kind="note",
                body="org announcement", scope="broadcast")

    org_inbox = engine.poll_inbox("s_org")
    up = [m for m in org_inbox if m["body"] == "api incident"]
    assert len(up) == 1
    assert up[0]["direction"] == "up"
    assert up[0]["origin_board"] == "named-squad-api"

    api_inbox = engine.poll_inbox("s_api")
    down = [m for m in api_inbox if m["body"] == "org announcement"]
    assert len(down) == 1
    assert down[0]["direction"] == "down"
    assert down[0]["origin_board"] == "named-org"


def test_poll_inbox_local_flag_excludes_federated(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.poll_inbox("s_org")
    engine.send(session_id="s_api", to="*", kind="note",
                body="api incident", scope="escalate")
    local_only = engine.poll_inbox("s_org", federated=False)
    assert all(m["body"] != "api incident" for m in local_only)
    # not consumed by the local read: the federated read still delivers it
    fed = engine.poll_inbox("s_org")
    assert any(m["body"] == "api incident" for m in fed)


def test_poll_inbox_federated_respects_read_receipts(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.poll_inbox("s_org")
    engine.send(session_id="s_api", to="*", kind="note",
                body="once only", scope="escalate")
    first = engine.poll_inbox("s_org")
    assert any(m["body"] == "once only" for m in first)
    second = engine.poll_inbox("s_org")
    assert all(m["body"] != "once only" for m in second)


def test_poll_inbox_sibling_and_plain_local_invisible(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.poll_inbox("s_web")
    engine.poll_inbox("s_org")
    engine.send(session_id="s_api", to="*", kind="note",
                body="api incident", scope="escalate")
    engine.send(session_id="s_api", to="*", kind="note", body="api local")
    web_inbox = engine.poll_inbox("s_web")          # sibling: sees neither
    assert all(m["body"] not in ("api incident", "api local")
               for m in web_inbox)
    org_inbox = engine.poll_inbox("s_org")          # ancestor: escalate only
    assert all(m["body"] != "api local" for m in org_inbox)


def test_join_colocation_counts_subtree_peers(engine, tmp_path):
    engine.create_board("org")
    engine.create_board("squad-api", parent="org")
    d1 = tmp_path / "child"
    d1.mkdir()
    d2 = tmp_path / "parent"
    d2.mkdir()
    engine.join(session_id="s_child", label="squad-sh", cwd=str(d1),
                board_name="squad-api")
    res = engine.join(session_id="s_parent", label="org-sh", cwd=str(d2),
                      board_name="org")
    # the parent-board joiner sees the child-board member in its summary
    assert res["colocated"].get("named-org") == ["squad-sh"]
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 5 new failures — federated assertions find no messages (`assert len(up) == 1` → 0) and `colocated` is `{}`.

- [ ] Implement in `coordination/src/mailbox/engine.py`. Replace the whole `poll_inbox` method (search for `# ----- poll_inbox -----`) with:

```python
    # ----- poll_inbox -----
    def poll_inbox(self, session_id, federated=True):
        presence = self.presence.get(session_id)
        if presence is None:
            return []
        boards = set(presence.boards)
        # Federated view (D2: federated by default; degenerates to the v1
        # local behavior when no board has a parent or children).
        fed_up = set()       # boards whose ESCALATIONS this session sees
        fed_down = set()     # boards whose BROADCASTS this session sees
        if federated:
            for b in boards:
                fed_up.update(boards_mod.descendants(self.boards, b))
                fed_down.update(boards_mod.ancestors(self.boards, b))
        label = presence.label
        matched = []
        directions = {}
        for msg in self.messages.values():
            if msg.board in boards:
                direction = "local"
            elif msg.board in fed_up and msg.scope == "escalate":
                direction = "up"
            elif msg.board in fed_down and msg.scope == "broadcast":
                direction = "down"
            else:
                continue
            if msg.from_session == session_id:
                continue
            if session_id in msg.read_by:
                continue
            if msg.to == "*" or msg.to == session_id or msg.to == label:
                matched.append(msg)
                directions[msg.id] = direction
        matched.sort(key=lambda m: m.created)
        result = []
        for msg in matched:
            msg.read_by.append(session_id)
            self._persist_message(msg)
            d = msg.to_dict()
            d["origin_board"] = msg.board
            d["direction"] = directions[msg.id]
            result.append(d)
        return result
```

- [ ] Then make `join`'s colocation counting subtree-aware. In the `join` method, replace this exact block (engine.py:129-137 pre-task):

```python
        colocated = {}
        if newly_created or was_offline:
            for bid in board_list:
                others = []
                for other in self.presence.values():
                    if other.session_id == session_id:
                        continue
                    if bid in other.boards and self._is_live(other):
                        others.append(other.label)
```

with:

```python
        colocated = {}
        if newly_created or was_offline:
            for bid in board_list:
                # Federated colocation: a joiner on a parent board counts the
                # live fleet across its subtree (presence rolls UP only). With
                # no children this is exactly the v1 single-board check.
                sub = set(boards_mod.subtree(self.boards, bid))
                others = []
                for other in self.presence.values():
                    if other.session_id == session_id:
                        continue
                    if (sub & set(other.boards)) and self._is_live(other):
                        others.append(other.label)
```

(The rest of the loop — note message creation — is untouched. `coordination/hooks/session_start.py` is NOT edited: it renders whatever `colocated` the engine returns, per DV5.)

- [ ] Run `test_federation.py` (all green), then the full coordination suite. `test_engine_messaging.py`, `test_hooks.py`, and `test_e2e.py` exercise flat (tree-less) boards where `subtree(b) == [b]` and `fed_up`/`fed_down` are empty — identical behavior, 0 failures (adds 5 tests). The annotated `origin_board`/`direction` keys are additive; existing tests index only known keys.
- [ ] Commit:

```bash
git add coordination/src/mailbox/engine.py coordination/tests/test_federation.py
git commit -m "AWR federation: federated poll_inbox + subtree join colocation (T5)"
```

## Task 6: CLI verbs — `create-board`, `set-parent`, `tree`, `escalate`, `broadcast`, `send --scope`, `inbox --federated/--local`

**Files**
- Modify: `coordination/src/mailbox/cli.py`
- Test: `coordination/tests/test_federation.py`

`bin/mailbox` is a pure `python -m mailbox.cli` shim (verified) — no change there.

**Steps**

- [ ] Append to `coordination/tests/test_federation.py` (these spawn a real daemon per test via `tmp_home` + `client.ensure_running`, the established `test_cli.py` pattern):

```python
# ---------------------------------------------------------------------------
# T6 — CLI verbs (real daemon round-trips via tmp_home)
# ---------------------------------------------------------------------------

from mailbox import cli, client


def test_cli_topology_verbs_need_no_session(tmp_home, monkeypatch, capsys):
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "team-platform", "--parent", "org"]) == 0
    assert cli.main(["create-board", "squad-api",
                     "--parent", "team-platform"]) == 0
    capsys.readouterr()
    assert cli.main(["tree"]) == 0
    out = capsys.readouterr().out
    assert "named-org  (org)" in out
    assert "    named-team-platform  (team-platform)" in out
    assert "        named-squad-api  (squad-api)" in out
    # re-parent + detach round-trip
    assert cli.main(["set-parent", "squad-api", "org"]) == 0
    assert cli.main(["set-parent", "squad-api", "--detach"]) == 0


def test_cli_create_board_bad_parent_exits_1(tmp_home, monkeypatch, capsys):
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    client.ensure_running()
    rc = cli.main(["create-board", "squad-api", "--parent", "ghost"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no-such-board: ghost" in captured.err


def test_cli_set_parent_requires_parent_or_detach(tmp_home, monkeypatch, capsys):
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    rc = cli.main(["set-parent", "org"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "pass a parent board or --detach" in captured.err


def test_cli_escalate_inbox_annotation_and_local_flag(
        tmp_home, tmp_path, monkeypatch, capsys):
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.chdir(b)
    assert cli.main(["--session", "s-org", "join", "--board", "org",
                     "--label", "org-sh"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-squad", "escalate", "api outage"]) == 0
    capsys.readouterr()
    # --local first: the escalation is NOT delivered (and NOT consumed)
    assert cli.main(["--session", "s-org", "inbox", "--local"]) == 0
    out_local = capsys.readouterr().out
    assert "api outage" not in out_local
    # federated default: delivered with the origin annotation
    assert cli.main(["--session", "s-org", "inbox"]) == 0
    out_fed = capsys.readouterr().out
    assert "api outage" in out_fed
    assert "escalated from named-squad-api" in out_fed


def test_cli_broadcast_reaches_descendant(tmp_home, tmp_path, monkeypatch,
                                          capsys):
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.chdir(b)
    assert cli.main(["--session", "s-org", "join", "--board", "org",
                     "--label", "org-sh"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-org", "broadcast", "all hands"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-squad", "inbox"]) == 0
    out = capsys.readouterr().out
    assert "all hands" in out
    assert "broadcast from named-org" in out


def test_cli_send_scope_flag_equivalent(tmp_home, tmp_path, monkeypatch,
                                        capsys):
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.chdir(b)
    assert cli.main(["--session", "s-org", "join", "--board", "org",
                     "--label", "org-sh"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-squad", "send", "via send flag",
                     "--scope", "escalate"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-org", "inbox"]) == 0
    assert "via send flag" in capsys.readouterr().out
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

Expected: 6 new failures — argparse `SystemExit: 2` (`invalid choice: 'create-board'`).

- [ ] Implement in `coordination/src/mailbox/cli.py`. First add the helpers right after the `_lane_name` function (cli.py:25-35):

```python
# Topology verbs run without a session id (operator commands, not session
# ops). fleet (Phase 2) resolves a session's board only when one is present.
_SESSION_OPTIONAL_CMDS = {"create-board", "set-parent", "tree"}

# New-verb error contract: an {"error": ...} data dict exits 1 with the error
# on stderr. Existing v1 verbs keep their print-the-dict behavior unchanged.
_FEDERATION_CMDS = {"create-board", "set-parent", "tree",
                    "escalate", "broadcast"}


def _add_fed_flags(sp):
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--federated", dest="federated", action="store_true",
                   default=True,
                   help="federated view across the board tree (default)")
    g.add_argument("--local", dest="federated", action="store_false",
                   help="restrict to own boards (no federation)")
```

- [ ] Replace `_print_inbox` (cli.py:38-47) with:

```python
def _print_inbox(messages: list) -> None:
    if not messages:
        print("(no messages)")
        return
    for m in messages:
        direction = m.get("direction")
        origin = ""
        if direction == "up":
            origin = " (^ escalated from %s)" % m.get("origin_board", "?")
        elif direction == "down":
            origin = " (v broadcast from %s)" % m.get("origin_board", "?")
        print("[%s] from %s%s: %s" % (
            m.get("kind", "note"),
            m.get("from_label", "?"),
            origin,
            m.get("body", ""),
        ))
```

- [ ] Add `_print_tree` after `_print_ps` (cli.py:78-88):

```python
def _print_tree(data: dict) -> None:
    roots = data.get("roots", []) if isinstance(data, dict) else []
    if not roots:
        print("(no boards)")
        return

    def _walk(node, indent):
        line = "%s%s" % (indent, node.get("id", "?"))
        name = node.get("name")
        if name:
            line += "  (%s)" % name
        if node.get("orphan"):
            line += "  [orphan: parent missing]"
        print(line)
        for child in node.get("children", []):
            _walk(child, indent + "    ")

    for root in roots:
        _walk(root, "")
```

- [ ] In `build_parser` (cli.py:91-138): replace the `send` parser block

```python
    sp = sub.add_parser("send")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")
```

with:

```python
    sp = sub.add_parser("send")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")
    sp.add_argument("--scope", default="local",
                    choices=["local", "escalate", "broadcast"])

    # Federation verbs (multi-board federation spec, 2026-06-09).
    sp = sub.add_parser("escalate")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")

    sp = sub.add_parser("broadcast")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")

    sp = sub.add_parser("create-board")
    sp.add_argument("name")
    sp.add_argument("--parent", default=None)

    sp = sub.add_parser("set-parent")
    sp.add_argument("board")
    sp.add_argument("parent", nargs="?", default=None)
    sp.add_argument("--detach", action="store_true")

    sp = sub.add_parser("tree")
    sp.add_argument("board", nargs="?", default=None)
```

and replace `sub.add_parser("inbox")` with:

```python
    sp = sub.add_parser("inbox")
    _add_fed_flags(sp)
```

- [ ] In `main` (cli.py:141-258): replace the session-resolution block

```python
    session_id = _resolve_session(args)
    if not session_id:
        print("no session id (run inside a Claude session)", file=sys.stderr)
        return 1

    cmd = args.cmd
```

with:

```python
    cmd = args.cmd

    session_id = _resolve_session(args)
    if not session_id and cmd not in _SESSION_OPTIONAL_CMDS:
        print("no session id (run inside a Claude session)", file=sys.stderr)
        return 1
```

then replace the `send` dispatch branch

```python
    elif cmd == "send":
        op = "send"
        op_args = {
            "session_id": session_id,
            "to": args.to,
            "kind": args.kind,
            "body": args.body,
        }
```

with:

```python
    elif cmd == "send":
        op = "send"
        op_args = {
            "session_id": session_id,
            "to": args.to,
            "kind": args.kind,
            "body": args.body,
            "scope": args.scope,
        }
    elif cmd in ("escalate", "broadcast"):
        op = "send"
        op_args = {
            "session_id": session_id,
            "to": args.to,
            "kind": args.kind,
            "body": args.body,
            "scope": cmd,
        }
    elif cmd == "create-board":
        op = "create_board"
        op_args = {"name": args.name, "parent": args.parent}
    elif cmd == "set-parent":
        if not args.detach and args.parent is None:
            print("set-parent: pass a parent board or --detach",
                  file=sys.stderr)
            return 1
        op = "set_parent"
        op_args = {"board": args.board, "parent": args.parent,
                   "detach": args.detach}
    elif cmd == "tree":
        op = "tree"
        op_args = {"board": args.board}
```

then replace the `inbox` dispatch branch

```python
    elif cmd == "inbox":
        op = "poll_inbox"
        op_args = {"session_id": session_id}
```

with:

```python
    elif cmd == "inbox":
        op = "poll_inbox"
        op_args = {"session_id": session_id, "federated": args.federated}
```

and finally replace the result-printing block

```python
    data = resp.get("data")
    if cmd == "inbox":
        _print_inbox(data or [])
```

with:

```python
    data = resp.get("data")
    if (cmd in _FEDERATION_CMDS and isinstance(data, dict)
            and data.get("error")):
        print(data["error"], file=sys.stderr)
        return 1
    if cmd == "inbox":
        _print_inbox(data or [])
    elif cmd == "tree":
        _print_tree(data or {})
```

- [ ] Run `test_federation.py` (all green), then the full coordination suite (0 failures; adds 6 tests). Existing `test_cli.py` stays green: `join`/`claims`/`whoami` dispatch is untouched, and the no-session error path still fires for session verbs.
- [ ] Commit:

```bash
git add coordination/src/mailbox/cli.py coordination/tests/test_federation.py
git commit -m "AWR federation: CLI create-board/set-parent/tree/escalate/broadcast + inbox --federated (T6)"
```

## Task 7: Contract + spec-index documentation

**Files**
- Modify: `coordination/docs/internal/contract.md` (verified to exist at this exact path)
- Modify: `coordination/docs/specs/2026-06-03-mailbox-design.md`

**Steps**

- [ ] Append to `coordination/docs/internal/contract.md` (after §17, end of file):

```markdown

---

## 18. Multi-board federation (2026-06-09 — additive; §§3, 7, 8, 12 unchanged for v1 callers)

Design: `docs/superpowers/specs/2026-06-09-awr-multi-board-federation-design.md`
(repo root). Everything here is backward-compatible: no `parent` ⇒ root board,
no `scope` ⇒ local message, flat boards behave exactly as v1.

### Board meta (`boards/<id>/meta.json`)
- `parent: <board_id> | null` — NEW. Absent/null = root. Written by
  `create_board` / `set_parent`; validated (no self-parent, parent must exist,
  no cycles, depth capped at `boards.MAX_FEDERATION_DEPTH = 8`).
- `delivery: "pull" | "push"` — NEW, absent = `pull` (read-time federation).
  `push` boards receive materialized copies of ancestor broadcasts
  (op `set_delivery`).

### Message (extends §3)
- `scope: "local" | "escalate" | "broadcast"` — NEW, default `"local"`.
  **Sparse serialization:** omitted from `to_dict()` when `"local"` so local
  messages keep the exact §3 JSON shape; `from_dict` restores the default.
- `origin_message_id: str | null` — NEW (set only on push-delivered copies;
  sparse: omitted when null).

### boards.py tree helpers (pure; first arg = the engine's boards-meta dict)
`parent_of(boards, id)`, `ancestors(boards, id)`, `descendants(boards, id)`,
`subtree(boards, id)`, `is_ancestor(boards, a, b)`, `depth(boards, id)`,
`height(boards, id)`, `validate_parent(boards, id, parent_id) -> Optional[str]`,
`MAX_FEDERATION_DEPTH = 8`. All walks are cycle-safe (visited sets).

### New ops (in `protocol.OPS`; engine method names match op names)
- `create_board(name, parent=None)` → `{"id","name","parent"}` | `{"error"}`
- `set_parent(board, parent=None, detach=False)` → `{"id","parent","was"}` | `{"error"}`
- `set_delivery(board, mode)` → `{"id","delivery"}` | `{"error"}` (mode: pull|push)
- `tree(board=None)` → `{"roots":[node]}` | `{"error"}`;
  node = `{"id","name","orphan","members","claims","children":[node]}`
- `fleet(session_id=None, board=None)` → `{"board","rows":[ps-row +
  "via_board" + "via_name"]}` | `{"error"}`
Board refs accept an exact board id or a bare name (`org` ⇒ `named-org`).

### Extended ops
- `send(..., scope="local")` — validates scope; escalate/broadcast posts are
  audited to `<state_dir>/federation.log` as `send scope=… board=… from=…
  body_sha=<sha256[:8]>` (bodies are hashed, never logged). Broadcasts fan
  out copies to push-mode descendant boards (`origin_message_id` dedup; no
  retroactive re-delivery on re-parent).
- `poll_inbox(session_id, federated=True)` — federated view: own boards +
  descendants' escalations + ancestors' broadcasts; every row is annotated
  with `origin_board` + `direction` (`"local"|"up"|"down"`). Push-mode boards
  skip the read-time broadcast path (their copies arrive as local messages).
  `federated=False` = exact v1 behavior.
- `ps(session_id, federated=True)` — subtree roll-up (a parent sees its
  descendants' presence; never the reverse).
- `list_claims(session_id, scope="board", federated=True)` — `"board"` scope
  widens to the subtree, matching claims by their HOLDER's presence membership in
  that subtree (a claim lives on its holder's repo board, outside every named
  subtree, so it federates by holder, not by `claim.board ∈ subtree`).
  **Enforcement (`check_write`/`claim_lane`) stays board-scoped** — only
  visibility federates.
- `join` — the colocation summary counts live peers across each joined
  board's subtree (engine-side; the SessionStart hook is unchanged).
- Engine read helpers (not ops): `federated_messages(board_id)`,
  `federated_presence(board_id)`, `federated_claims(board_id)`.

### CLI (extends §12)
`create-board <name> [--parent <p>]`, `set-parent <board> [<p>] [--detach]`,
`set-delivery <board> (pull|push)`, `tree [<board>]`, `fleet [<board>]`,
`escalate "<body>" [--to L] [--kind K]` (≡ `send --scope escalate`),
`broadcast "<body>" …` (≡ `send --scope broadcast`),
`send --scope (local|escalate|broadcast)`,
`ps`/`claims`/`inbox` `--federated` (default) / `--local`.
Topology verbs (`create-board`/`set-parent`/`set-delivery`/`tree`/`fleet`)
run without a session id. New verbs exit 1 with the engine's `error` string
on stderr; v1 verbs keep their v1 output contract.
```

- [ ] Append to `coordination/docs/specs/2026-06-03-mailbox-design.md` (end of file, after "Out of scope (v1)"):

```markdown

## Related specs

- **Multi-board hierarchical federation** (boards form a tree; `escalate` /
  `broadcast` scopes; read-time federated views; `tree`/`fleet` operator
  surface): `docs/superpowers/specs/2026-06-09-awr-multi-board-federation-design.md`
  at the repo root. Implemented in this package (`boards.py`, `engine.py`,
  `cli.py`); op surface documented in `docs/internal/contract.md` §18.
```

- [ ] Verify both edits landed:

```bash
grep -c "Multi-board federation" /Users/aahil/Documents/Code/agentic-war-room/coordination/docs/internal/contract.md
grep -c "2026-06-09-awr-multi-board-federation-design" /Users/aahil/Documents/Code/agentic-war-room/coordination/docs/specs/2026-06-03-mailbox-design.md
```

Expected: each prints ≥ 1.

- [ ] Commit:

```bash
git add coordination/docs/internal/contract.md coordination/docs/specs/2026-06-03-mailbox-design.md
git commit -m "AWR federation: contract §18 + spec cross-link (T7)"
```

## Task 8: Template `parent` key — schema, wizard field, block rendering, `run_setup` wiring

**Files**
- Modify: `template/warroom_setup/schema.py`
- Modify: `template/warroom_setup/selectables.py`
- Modify: `template/warroom_setup/setup.py`
- Modify: `template/tests/test_schema.py` (ONE tuple — change-detector update, DV1)
- Test: `template/tests/test_parent_wiring.py` (new)

**Steps**

- [ ] Create `template/tests/test_parent_wiring.py`:

```python
"""Multi-board federation: template-side `parent` wiring (schema key, wizard
field, war_room block rendering, run_setup pass-through). The runtime stays
single-board (`MAILBOX_BOARD` only); federation is resolved engine-side."""
import io
import shutil
from pathlib import Path

from warroom_setup import enroll, schema, selectables, setup


def test_schema_has_parent_key_after_board():
    keys = list(schema.WAR_ROOM_KEYS)
    assert "parent" in keys
    assert keys.index("parent") == keys.index("board") + 1
    assert schema.DEFAULTS["parent"] == ""


def test_patch_war_room_block_renders_parent(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_war_room_block(tmp_path, "squad-api", parent="team-platform")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "board: squad-api" in text
    assert "parent: team-platform" in text


def test_blank_parent_is_omitted_from_block(tmp_path):
    # Zero rendered-byte change for non-federated profiles (DV2).
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_war_room_block(tmp_path, "squad-api")
    assert "parent:" not in (tmp_path / "config.yaml").read_text(
        encoding="utf-8")


def test_mailbox_block_unchanged_by_parent_feature(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_mailbox_block(tmp_path, board="squad-api")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "parent" not in text
    assert schema.MAILBOX_KEYS == ("board", "label", "mailbox_home",
                                   "socket_path")


def test_selectables_parent_field_appended_last_with_enable_if():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    assert ids[-1] == "warroom.parent"      # F10 rule: appended, never inserted
    fld = [f for f in selectables.TEXT_FIELDS if f.id == "warroom.parent"][0]
    assert fld.enable_if == "warroom.enroll"
    assert fld.secret is False and fld.required is False
    assert "warroom.parent" not in selectables.ENV_FIELD_IDS


def _fake_profile(tmp_path):
    src = Path(__file__).resolve().parents[1]
    prof = tmp_path / "profiles" / "zed"
    prof.mkdir(parents=True)
    for d in ("persona", "templates", "shared"):
        shutil.copytree(src / d, prof / d)
    shutil.copy2(src / "manifest.json", prof / "manifest.json")
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n")
    (prof / "config.yaml").write_text("model:\n  name: opus\n")
    return prof


class _ParentAwareRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, profile_root, board, label, dry_run=False, env=None,
                 parent=None):
        self.calls.append({"board": board, "label": label, "parent": parent})
        return enroll.EnrollState(board=board, label=label, cli_path=None,
                                  mailbox_home="", socket_path="",
                                  last_check_ts=0.0, status="ok")


class _LegacyRecorder:
    """Old bootstrap signature (no parent kwarg) — proves run_setup only
    passes parent= when the operator actually supplied one."""

    def __init__(self):
        self.calls = []

    def __call__(self, profile_root, board, label, dry_run=False, env=None):
        self.calls.append({"board": board, "label": label})
        return enroll.EnrollState(board=board, label=label, cli_path=None,
                                  mailbox_home="", socket_path="",
                                  last_check_ts=0.0, status="ok")


def _run(prof, monkeypatch, rec, extra_lines=""):
    monkeypatch.setenv("HOME", str(prof.parent.parent / "home"))
    monkeypatch.setattr(enroll, "bootstrap", rec)
    instream = io.StringIO(
        "zed\nZed\n\nsk-anthropic\ndt-token\n123,456\n" + extra_lines
    )
    toggle_in = io.StringIO("\n\n\n\n\n")
    return setup.run_setup(prof, yes=False, reconfigure=False,
                           in_stream=instream, out_stream=io.StringIO(),
                           toggle_in_stream=toggle_in)


def test_run_setup_passes_parent_to_bootstrap_and_block(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _ParentAwareRecorder()
    # prompt order after the channel fields: board, min_confidence, label, parent
    rc = _run(prof, monkeypatch, rec,
              extra_lines="squad-api\n80\nalpha-sh\nteam-platform\n")
    assert rc == 0
    assert rec.calls == [{"board": "squad-api", "label": "alpha-sh",
                          "parent": "team-platform"}]
    text = (prof / "config.yaml").read_text(encoding="utf-8")
    assert "parent: team-platform" in text


def test_run_setup_blank_parent_omits_kwarg(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _LegacyRecorder()
    rc = _run(prof, monkeypatch, rec,
              extra_lines="squad-api\n80\nalpha-sh\n\n")
    assert rc == 0
    assert rec.calls == [{"board": "squad-api", "label": "alpha-sh"}]
    assert "parent:" not in (prof / "config.yaml").read_text(encoding="utf-8")
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_parent_wiring.py -q
```

Expected: failures — `assert "parent" in keys` fails; `TypeError: patch_war_room_block() got unexpected war_room keys: parent`; selectables `ids[-1] == "warroom.parent"` fails.

- [ ] Implement. In `template/warroom_setup/schema.py`, replace `WAR_ROOM_KEYS` (schema.py:11-14) with:

```python
# Ordered key set for the sentinel-managed war_room config block. `parent` is
# the optional federation link (multi-board federation spec, 2026-06-09):
# blank/absent => standalone root board. It renders only when non-empty, so
# non-federated profiles keep the exact pre-federation block bytes.
WAR_ROOM_KEYS = (
    "enabled", "board", "parent", "label", "role", "min_confidence",
    "gate_action", "enforce", "show_confidence_badge",
)
```

and in `DEFAULTS` (schema.py:22-31) insert `"parent": "",` directly after the `"board": "default",` line:

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
}
```

- [ ] In `template/tests/test_schema.py`, update the change-detector tuple (DV1 — the ONLY existing-test edit in this plan), replacing:

```python
def test_war_room_keys_exact():
    assert schema.WAR_ROOM_KEYS == (
        "enabled", "board", "label", "role", "min_confidence",
        "gate_action", "enforce", "show_confidence_badge",
    )
```

with:

```python
def test_war_room_keys_exact():
    assert schema.WAR_ROOM_KEYS == (
        "enabled", "board", "parent", "label", "role", "min_confidence",
        "gate_action", "enforce", "show_confidence_badge",
    )
```

- [ ] In `template/warroom_setup/selectables.py`, append to the END of the `TEXT_FIELDS` list (after the `warroom.label` entry, before the closing `]`):

```python
    # Federation (multi-board): appended AFTER warroom.label — same F10 rule,
    # never inserted between existing fields (which would silently reorder the
    # wizard prompt sequence).
    TextField(id="warroom.parent",
              prompt="Parent board (for federation; blank for a standalone board)",
              required=False, enable_if="warroom.enroll"),
```

- [ ] In `template/warroom_setup/setup.py::run_setup`, replace this block (setup.py:418-428 pre-task):

```python
    if "warroom.enroll" in selected:
        mc = schema.clamp_pct(values.get("warroom.min_confidence", ""))
        board = values.get("warroom.board", "").strip()
        patch_war_room_block(profile_root, board,
                             min_confidence=mc, enforce=("warroom.enforce" in selected))
        # Cross-agent runtime: bootstrap writes the mailbox: block (same board,
        # keeping war_room.board / mailbox.board in sync per decision #13),
        # persists runtime state, and installs the Claude Code SessionStart hook.
        label = values.get("warroom.label", "").strip() or ident.handle
        from . import enroll
        st = enroll.bootstrap(profile_root, board, label)
```

with:

```python
    if "warroom.enroll" in selected:
        mc = schema.clamp_pct(values.get("warroom.min_confidence", ""))
        board = values.get("warroom.board", "").strip()
        parent = values.get("warroom.parent", "").strip()
        patch_war_room_block(profile_root, board, parent=parent,
                             min_confidence=mc, enforce=("warroom.enforce" in selected))
        # Cross-agent runtime: bootstrap writes the mailbox: block (same board,
        # keeping war_room.board / mailbox.board in sync per decision #13),
        # persists runtime state, and installs the Claude Code SessionStart hook.
        label = values.get("warroom.label", "").strip() or ident.handle
        from . import enroll
        # parent kwarg only when supplied: keeps monkeypatched legacy-signature
        # bootstrap recorders (existing tests) working unchanged.
        if parent:
            st = enroll.bootstrap(profile_root, board, label, parent=parent)
        else:
            st = enroll.bootstrap(profile_root, board, label)
```

(`enroll.bootstrap` does not accept `parent=` until T9; the parent-aware recorder in this task's test absorbs it. T9 adds the real parameter — the two tasks are committed back-to-back and the suite is only required green at the phase checkpoint after T9. If executing strictly one-green-commit-at-a-time, run T8's `test_run_setup_passes_parent_to_bootstrap_and_block` knowing it passes because the recorder, not the real bootstrap, receives the kwarg.)

- [ ] Run the new file (all green) and the rest of the template suite:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
```

Expected: 0 failures (adds 7 tests over the 409-passed/10-skipped baseline). Existing scripted-stdin `run_setup` tests stay green: the new prompt is LAST, and `prompts.collect` returns cleanly at EOF (prompts.py:73-76), so shorter scripts simply leave `warroom.parent` unset.

- [ ] Commit:

```bash
git add template/warroom_setup/schema.py template/warroom_setup/selectables.py template/warroom_setup/setup.py template/tests/test_schema.py template/tests/test_parent_wiring.py
git commit -m "AWR federation: template parent key + wizard field + run_setup wiring (T8)"
```

## Task 9: `enroll.bootstrap(parent=...)` → engine link via the mailbox CLI; `warroom enroll --parent`; gate-skill note — **Phase 1 checkpoint**

**Files**
- Modify: `template/warroom_setup/enroll.py`
- Modify: `template/warroom_setup/cli.py`
- Modify: `template/skills/confidence-gate/SKILL.md`
- Modify: `template/skills/warroom/SKILL.md` (additive federation section, DV9)
- Create: `template/tests/fixtures/fake_mailbox_record.sh`
- Test: `template/tests/test_enroll_parent.py` (new)

**Steps**

- [ ] Create the recording CLI fixture `template/tests/fixtures/fake_mailbox_record.sh`:

```bash
#!/usr/bin/env bash
# Test fixture: a recording stand-in for the `mailbox` CLI. Appends each
# invocation's argv to $FAKE_MAILBOX_LOG (if set) and exits with
# $FAKE_MAILBOX_EXIT (default 0). Never spawns a daemon, never opens a socket.
if [ -n "${FAKE_MAILBOX_LOG:-}" ]; then
  echo "$*" >> "$FAKE_MAILBOX_LOG"
fi
exit "${FAKE_MAILBOX_EXIT:-0}"
```

```bash
chmod +x /Users/aahil/Documents/Code/agentic-war-room/template/tests/fixtures/fake_mailbox_record.sh
```

- [ ] Create `template/tests/test_enroll_parent.py`:

```python
"""enroll.bootstrap(parent=...): records the home board's parent link
engine-side via the discovered mailbox CLI (`create-board <board> --parent
<p>`), fail-warn on every failure mode, `.env` stays single-board."""
import json
import shutil
import stat
from pathlib import Path

from warroom_setup import cli, enroll

FIXTURE = (Path(__file__).resolve().parent / "fixtures"
           / "fake_mailbox_record.sh")


def _profile(tmp_path):
    prof = tmp_path / "profiles" / "alpha-sh"
    (prof / "hooks").mkdir(parents=True)
    prof.joinpath("config.yaml").write_text("model: {}\n", encoding="utf-8")
    return prof


def _env_with_cli(tmp_path, with_cli=True):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    env = {"HOME": str(home), "PATH": ""}
    if with_cli:
        mh = tmp_path / "mhome"
        mh.mkdir()
        dst = mh / "mailbox"
        shutil.copy2(FIXTURE, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR)
        env["MAILBOX_HOME"] = str(mh)
    return env


def test_bootstrap_parent_invokes_create_board(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(log))
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "ok"
    assert st.parent == "team-platform"
    assert st.parent_status == "ok"
    assert log.read_text().splitlines() == [
        "create-board squad-api --parent team-platform"]


def test_bootstrap_without_parent_never_calls_engine(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(log))
    st = enroll.bootstrap(prof, "shared", "alpha-sh",
                          env=_env_with_cli(tmp_path))
    assert st.parent is None and st.parent_status is None
    assert not log.exists()


def test_bootstrap_parent_failure_is_fail_warn(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_EXIT", "1")
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "ok"                  # enrollment itself succeeded
    assert st.parent_status == "parent-failed"
    # config + .env still written: fail-warn, never fail-stop
    assert "MAILBOX_BOARD=squad-api" in (prof / ".env").read_text()


def test_bootstrap_parent_with_no_cli_records_cli_not_found(tmp_path):
    prof = _profile(tmp_path)
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path, with_cli=False),
                          parent="team-platform")
    assert st.status == "cli-not-found"
    assert st.parent_status == "cli-not-found"


def test_bootstrap_parent_keeps_env_single_board(tmp_path, monkeypatch):
    # Spec: `.env` shape is UNCHANGED — single MAILBOX_BOARD, no parent key.
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(tmp_path / "l.log"))
    enroll.bootstrap(prof, "squad-api", "alpha-sh",
                     env=_env_with_cli(tmp_path), parent="team-platform")
    env_txt = (prof / ".env").read_text()
    assert "MAILBOX_BOARD=squad-api" in env_txt
    assert "team-platform" not in env_txt


def test_bootstrap_dry_run_records_parent_without_writes(tmp_path):
    prof = _profile(tmp_path)
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh", dry_run=True,
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "dry-run"
    assert st.parent == "team-platform"
    assert st.parent_status is None
    assert not (prof / "local").exists()


def test_state_file_records_parent_fields(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(tmp_path / "l.log"))
    enroll.bootstrap(prof, "squad-api", "alpha-sh",
                     env=_env_with_cli(tmp_path), parent="team-platform")
    data = json.loads(
        (prof / "local" / "warroom-enroll.json").read_text())
    assert data["parent"] == "team-platform"
    assert data["parent_status"] == "ok"


def test_cli_enroll_parent_flag_passthrough(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    seen = {}

    def _fake(pr, b, l, dry_run=False, env=None, parent=None):
        seen.update(board=b, parent=parent)
        return enroll.EnrollState(b, l, None, "", "", 0.0, "ok")

    monkeypatch.setattr(enroll, "bootstrap", _fake)
    rc = cli.main(["enroll", "--board", "squad-api",
                   "--parent", "team-platform", "--profile-root", str(prof)])
    assert rc == 0
    assert seen == {"board": "squad-api", "parent": "team-platform"}


def test_confidence_gate_skill_mentions_federation_scopes():
    text = (Path(__file__).resolve().parents[1] / "skills"
            / "confidence-gate" / "SKILL.md").read_text(encoding="utf-8")
    assert "mailbox escalate" in text
    assert "mailbox broadcast" in text
    assert "visibility only" in text


def test_warroom_skill_documents_federation_verbs():
    # DV9 + spec File-path map: warroom/SKILL.md documents the federation
    # protocol verbs alongside the existing board-local protocol.
    text = (Path(__file__).resolve().parents[1] / "skills"
            / "warroom" / "SKILL.md").read_text(encoding="utf-8")
    assert "mailbox escalate" in text
    assert "mailbox broadcast" in text
    assert "mailbox tree" in text
    assert "mailbox fleet" in text
```

- [ ] Run and confirm the failures:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template/tests/test_enroll_parent.py -q
```

Expected: failures — `TypeError: bootstrap() got an unexpected keyword argument 'parent'`, `AttributeError: 'EnrollState' object has no attribute 'parent'`, argparse `unrecognized arguments: --parent`, and both SKILL.md assertions (confidence-gate + warroom).

- [ ] Implement in `template/warroom_setup/enroll.py`. Add `import subprocess` to the imports (after `import shutil`, enroll.py:13-15). Replace the `EnrollState` dataclass body (enroll.py:103-123) with:

```python
@dataclass
class EnrollState:
    board: str
    label: str
    cli_path: Optional[str]
    mailbox_home: str
    socket_path: str
    last_check_ts: float
    status: str  # "ok" | "cli-not-found" | "socket-unreachable" | "dry-run"
    # Federation (optional): the home board's parent link, recorded
    # engine-side at bootstrap. parent_status: None (no parent requested) |
    # "ok" | "parent-failed" | "cli-not-found".
    parent: Optional[str] = None
    parent_status: Optional[str] = None

    def to_dict(self):
        # type: () -> dict
        return {
            "board": self.board,
            "label": self.label,
            "cli_path": self.cli_path,
            "mailbox_home": self.mailbox_home,
            "socket_path": self.socket_path,
            "last_check_ts": self.last_check_ts,
            "status": self.status,
            "parent": self.parent,
            "parent_status": self.parent_status,
        }
```

- [ ] Add `_ensure_parent_link` directly above `bootstrap` (after `_append_log`):

```python
def _ensure_parent_link(cli, board, parent, env=None):
    # type: (Path, str, str, Optional[dict]) -> str
    """Best-effort: ask the mailbox engine (via the discovered CLI — enroll
    NEVER imports mailbox.client) to mint the home board and record its
    parent link: `mailbox create-board <board> --parent <parent>`. The
    engine requires the parent to already exist (operators build top-down).
    Returns "ok" | "parent-failed"; never raises — federation is additive
    and enrollment stays fail-warn."""
    e = _env(env)
    sub_env = dict(os.environ)
    for k in ("MAILBOX_HOME", "MAILBOX_SOCKET"):
        v = (e.get(k) or "").strip()
        if v:
            sub_env[k] = v
    try:
        proc = subprocess.run(
            [str(cli), "create-board", board, "--parent", parent],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=sub_env, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return "parent-failed"
    return "ok" if proc.returncode == 0 else "parent-failed"
```

- [ ] Update `bootstrap` (enroll.py:174-232). Change the signature line from:

```python
def bootstrap(profile_root, board, label, dry_run=False, env=None):
    # type: (Path, str, str, bool, Optional[dict]) -> EnrollState
```

to:

```python
def bootstrap(profile_root, board, label, dry_run=False, env=None, parent=None):
    # type: (Path, str, str, bool, Optional[dict], Optional[str]) -> EnrollState
```

Change the `EnrollState(...)` construction to include the new fields (append after `status=status,`):

```python
    state = EnrollState(
        board=(board or "default"),
        label=(label or ""),
        cli_path=(str(cli) if cli is not None else None),
        mailbox_home=str(home),
        socket_path=str(sock),
        last_check_ts=time.time(),
        status=status,
        parent=(parent or None),
        parent_status=None,
    )
```

And insert the parent-link call between `write_runtime_env(profile_root, state, env=env)` and the `local = profile_root / "local"` line (so the state file below records the outcome):

```python
    # Federation (optional): record the home board's parent link engine-side.
    # `.env` stays single-board; the engine resolves federation at read time.
    if state.parent:
        if cli is None:
            state.parent_status = "cli-not-found"
        else:
            state.parent_status = _ensure_parent_link(
                cli, state.board, state.parent, env=env)
```

- [ ] In `template/warroom_setup/cli.py`: add to the enroll subparser (after the `--label` argument, cli.py:25):

```python
    e.add_argument("--parent", default=None,
                   help="parent board for federation (records the link engine-side)")
```

and in `cmd_enroll`, replace:

```python
    st = enroll.bootstrap(profile_root, board, label, dry_run=args.dry_run)
```

with:

```python
    # parent kwarg only when supplied (keeps legacy-signature bootstrap
    # monkeypatches in existing tests working unchanged).
    if args.parent:
        st = enroll.bootstrap(profile_root, board, label,
                              dry_run=args.dry_run, parent=args.parent)
    else:
        st = enroll.bootstrap(profile_root, board, label,
                              dry_run=args.dry_run)
```

- [ ] Append to `template/skills/confidence-gate/SKILL.md` (end of file):

```markdown

Federation note: on a federated board tree, `mailbox escalate "<msg>"` /
`mailbox broadcast "<msg>"` change *visibility only* (ancestors / descendants
of your home board see the post). An escalated claim is still a claim: it
keeps its confidence envelope and gates exactly like a local post. Never
escalate to dodge the gate — abstain loudly instead.
```

- [ ] Append to `template/skills/warroom/SKILL.md` (end of file — additive,
  sentinel-free; DV9 + spec File-path map). The existing protocol stays untouched:

```markdown

## Federation — escalate up, broadcast down

When your board is part of a tree (squad → team → org), signal flows both ways
by *visibility* (read-time; nothing is copied):
```
mailbox escalate "<msg>"     # ancestors (team, org) see it — surface an incident upward
mailbox broadcast "<msg>"    # descendants (every squad) see it — an org-wide call down
mailbox send "<msg>" --scope escalate|broadcast   # the same, explicit
```
Reads federate by default; scope down with `--local`:
```
mailbox inbox                # own board + escalations up + broadcasts down (annotated)
mailbox ps                   # live peers across your subtree
mailbox claims               # open claims across your subtree (visibility only)
mailbox inbox --local        # restrict to your own board
```
Inspect and shape the topology (operator verbs; no session needed):
```
mailbox tree [<board>]       # render the board forest / a subtree
mailbox fleet [<board>]      # who is active across a subtree, by board
mailbox create-board <name> --parent <p>
mailbox set-parent <board> <p> | --detach
```
Federation widens *visibility*, never *enforcement*: a claim still only blocks
writers on its own board. Siblings and cousins never see each other.
```

- [ ] Run the new test file (all green: 10 tests), then **Phase 1 checkpoint** — both full suites + sanitization:

```bash
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
# coordination is not in sanitize_check's scope (template-only by design), so
# also run the employer-leak grep over the coordination tree this phase touched:
grep -RIn -i "twelvelabs\|twelve labs\|@twelvelabs\|tl-branding" /Users/aahil/Documents/Code/agentic-war-room/coordination/
```

Expected: 0 failures in both suites (template adds 17 tests across T8+T9; coordination adds 39 across T1–T6); sanitize exits 0; the coordination employer-leak grep prints NOTHING. Existing `test_enroll_bootstrap.py` / `test_cli_enroll.py` recorders stay green: the new dataclass fields default to `None`, and run_setup/cmd_enroll only pass `parent=` when the operator supplied one.

- [ ] Commit:

```bash
git add template/warroom_setup/enroll.py template/warroom_setup/cli.py template/skills/confidence-gate/SKILL.md template/skills/warroom/SKILL.md template/tests/fixtures/fake_mailbox_record.sh template/tests/test_enroll_parent.py
git commit -m "AWR federation: enroll.bootstrap(parent=) via mailbox CLI + gate/warroom skill federation docs (T9)"
```

---

# Phase 2 — Presence & claims federation

## Task 10: Engine — `federated_presence`/`federated_claims`, `fleet`, `ps`/`list_claims` federated

**Files**
- Modify: `coordination/src/mailbox/engine.py`
- Modify: `coordination/src/mailbox/protocol.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T10 — presence/claims federation: fleet, ps/claims roll-up (visibility only)
# ---------------------------------------------------------------------------


def test_federated_presence_rolls_up_subtree(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    rows = engine.federated_presence("named-org")
    labels = [r["label"] for r in rows]
    assert labels == ["api-sh", "org-sh", "team-sh", "web-sh"]
    api_row = [r for r in rows if r["label"] == "api-sh"][0]
    assert api_row["via_board"] == "named-squad-api"


def test_federated_presence_leaf_sees_only_itself(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    rows = engine.federated_presence("named-squad-api")
    assert [r["label"] for r in rows] == ["api-sh"]   # roll-up only, never up


def test_fleet_resolves_refs_session_default_and_errors(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    by_name = engine.fleet(board="org")
    assert by_name["board"] == "named-org"
    assert len(by_name["rows"]) == 4
    # no board: fall back to the session's primary (named) board
    by_session = engine.fleet(session_id="s_team")
    assert by_session["board"] == "named-team-platform"
    assert [r["label"] for r in by_session["rows"]] == [
        "api-sh", "team-sh", "web-sh"]
    assert engine.fleet(board="ghost") == {"error": "no-such-board: ghost"}
    assert engine.fleet() == {
        "error": "no-board: pass a board or run inside a session"}


def test_ps_federated_default_and_local_flag(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    fed = [r["label"] for r in engine.ps("s_org")]
    assert fed == ["api-sh", "org-sh", "team-sh", "web-sh"]
    local = [r["label"] for r in engine.ps("s_org", federated=False)]
    assert local == ["org-sh"]
    # child never sees the parent's presence (roll-up only)
    child = [r["label"] for r in engine.ps("s_api")]
    assert child == ["api-sh"]


def test_list_claims_board_scope_widens_to_subtree(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    target = str(tmp_path / "cwd2" / "src" / "core.py")
    engine.claim(session_id="s_api", globs=[target], note="api work")
    fed = engine.list_claims("s_org")
    assert any(c["note"] == "api work" for c in fed)
    local = engine.list_claims("s_org", federated=False)
    assert all(c["note"] != "api work" for c in local)
    # child never sees the parent's claims
    parent_target = str(tmp_path / "cwd0" / "doc.md")
    engine.claim(session_id="s_org", globs=[parent_target], note="org work")
    child = engine.list_claims("s_api")
    assert all(c["note"] != "org work" for c in child)


def test_federated_claims_annotates_origin(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    target = str(tmp_path / "cwd2" / "src" / "core.py")
    engine.claim(session_id="s_api", globs=[target], note="api work")
    rows = engine.federated_claims("named-org")
    hit = [c for c in rows if c["note"] == "api work"]
    assert len(hit) == 1
    assert hit[0]["origin_board"] == hit[0]["board"]
    assert hit[0]["holder_status"] == "active"


def test_federated_claims_cross_repo_holder_visible_to_ancestor(engine,
                                                                tmp_path):
    # Spec §4 dogpile-across-a-federated-team: the holder's claim lives on its
    # OWN repo board (a cwd- root, outside every named subtree). It is still
    # surfaced to an ancestor because federation rolls up by the HOLDER's
    # presence membership, not by claim.board ∈ named-subtree. Without the
    # presence-membership roll-up this returns nothing.
    _setup_tree(engine, tmp_path)
    target = str(tmp_path / "cwd2" / "src" / "core.py")
    res = engine.claim(session_id="s_api", globs=[target], note="api work")
    assert res["board"].startswith(("cwd-", "repo-"))   # NOT a named board
    assert res["board"] not in boards_mod.subtree(engine.boards, "named-org")
    rows = engine.federated_claims("named-org")
    assert any(c["note"] == "api work" for c in rows)    # visible regardless


def test_check_write_enforcement_stays_board_scoped(engine, tmp_path):
    # DV8: visibility federates; ENFORCEMENT does not. The holder is the CHILD
    # (s_api) so the parent's (s_org) FEDERATED view DOES surface the claim —
    # proving visibility federates — while check_write for the parent still
    # allows, proving enforcement stays board-scoped (the claim sits on the
    # child's repo board, never in the parent's board set). This exercises the
    # real cross-board boundary; in v1 (no federation) the parent could not
    # even see the claim, so an accidental federation of enforcement would be
    # caught here.
    _setup_tree(engine, tmp_path)
    target = str(tmp_path / "cwd2" / "src" / "core.py")
    engine.claim(session_id="s_api", globs=[target], note="api claim")
    # visibility federates: the ancestor sees the descendant's claim
    fed = engine.list_claims("s_org")
    assert any(c["note"] == "api claim" for c in fed)
    # enforcement stays board-scoped: the ancestor's write is NOT denied
    res = engine.check_write("s_org", target)
    assert res["decision"] == "allow"
```

- [ ] Run and confirm the failures (`AttributeError: 'MailboxEngine' object has no attribute 'federated_presence'`, etc., and `list_claims() got an unexpected keyword argument 'federated'`):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

- [ ] Implement in `coordination/src/mailbox/engine.py`. Insert after `federated_messages` (still under the `# ----- federated reads` banner):

```python
    def federated_presence(self, board_id):
        """Presence across subtree(board_id) — an ancestor sees the whole
        fleet beneath it (roll-up only; spec §4). Rows are ps-shaped plus
        "via_board": the first of the member's boards inside the subtree."""
        sub = set(boards_mod.subtree(self.boards, board_id))
        rows = []
        for p in self.presence.values():
            hit = [b for b in p.boards if b in sub]
            if not hit:
                continue
            rows.append({
                "session_id": p.session_id,
                "label": p.label,
                "cwd": p.cwd,
                "member": p.member,
                "status": self._status_of(p),
                "last_seen_seconds": self._now() - p.last_heartbeat,
                "boards": list(p.boards),
                "via_board": hit[0],
            })
        rows.sort(key=lambda r: r["label"])
        return rows

    def _subtree_sessions(self, sub):
        """Session ids whose presence sits on ANY board in `sub` (a set of
        board ids). This is the federation roll-up key for CLAIMS: a claim is
        stored on its holder's REPO board (boards[0], a cwd-/repo- root that is
        NEVER inside a named subtree), so claims can only be federated by their
        HOLDER's presence membership — the same membership that already makes
        federated_presence work. Rolls UP only (a parent's subtree includes a
        child's session; never the reverse)."""
        out = set()
        for p in self.presence.values():
            if sub & set(p.boards):
                out.add(p.session_id)
        return out

    def federated_claims(self, board_id):
        """Unreleased claims across subtree(board_id), annotated like
        list_claims plus "origin_board". Visibility only — conflict
        enforcement (check_write/claim_lane) stays board-scoped.

        A claim lives on its holder's repo board, so we federate by the
        HOLDER's presence membership in the subtree, not by claim.board ∈
        subtree (which would surface nothing — repo boards are roots outside
        every named subtree). This is the cross-repo dogpile case in spec §4:
        a file claim made by a squad session is visible to its team/org
        ancestors."""
        sub = set(boards_mod.subtree(self.boards, board_id))
        sessions = self._subtree_sessions(sub)
        out = []
        for c in self.claims.values():
            if c.released:
                continue
            if c.session_id not in sessions:
                continue
            holder = self.presence.get(c.session_id)
            if holder is None or holder.status == "offline":
                holder_status = "offline"
            elif self._is_live(holder):
                holder_status = "active"
            else:
                holder_status = "stale"
            entry = c.to_dict()
            entry["live"] = holder_status == "active"
            entry["holder_status"] = holder_status
            entry["origin_board"] = c.board
            out.append(entry)
        return out

    def fleet(self, session_id=None, board=None):
        """Operator fleet view: federated presence for `board` (id or name),
        defaulting to the calling session's primary board."""
        if board is not None:
            bid = self._resolve_board_ref(board)
            if bid is None:
                return {"error": "no-such-board: " + str(board)}
        elif session_id is not None and session_id in self.presence:
            bid = self._primary_board(session_id)
        else:
            return {"error": "no-board: pass a board or run inside a session"}
        return {"board": bid, "rows": self.federated_presence(bid)}
```

- [ ] Replace the `list_claims` method's first lines AND its `"board"`-scope
  membership test (search `# ----- list_claims -----`). A claim is stored on its
  holder's repo board, never a named board, so the federated `"board"` scope must
  match by the HOLDER's presence membership in the subtree — not by `claim.board ∈
  subtree` (which would surface nothing). The non-federated path keeps the exact v1
  `c.board not in boards` test. Replace:

```python
    # ----- list_claims -----
    def list_claims(self, session_id, scope="board"):
        p = self.presence.get(session_id)
        if p is not None:
            boards = set(p.boards)
        else:
            boards = set()
        out = []
        for c in self.claims.values():
            if c.released:
                continue
            if scope == "mine":
                if c.session_id != session_id:
                    continue
            elif scope == "all":
                pass
            else:  # "board"
                if c.board not in boards:
                    continue
```

with:

```python
    # ----- list_claims -----
    def list_claims(self, session_id, scope="board", federated=True):
        p = self.presence.get(session_id)
        if p is not None:
            boards = set(p.boards)
        else:
            boards = set()
        # D2/DV8: federated "board" scope widens to the subtree union, then
        # matches claims by their HOLDER's presence membership in that subtree
        # (claims live on repo boards, outside every named subtree — see
        # _subtree_sessions). Visibility only; enforcement stays board-scoped.
        fed_sessions = None
        if federated and scope == "board":
            widened = set()
            for b in boards:
                widened.update(boards_mod.subtree(self.boards, b))
            fed_sessions = self._subtree_sessions(widened)
        out = []
        for c in self.claims.values():
            if c.released:
                continue
            if scope == "mine":
                if c.session_id != session_id:
                    continue
            elif scope == "all":
                pass
            elif fed_sessions is not None:  # federated "board"
                if c.session_id not in fed_sessions:
                    continue
            else:  # local "board" — exact v1 behavior
                if c.board not in boards:
                    continue
```

- [ ] Replace the `ps` method's first lines (search `# ----- ps -----`); the row-building loop is untouched except the membership test:

```python
    # ----- ps -----
    def ps(self, session_id, federated=True):
        me = self.presence.get(session_id)
        if me is None:
            return []
        if federated:
            scope = set()
            for b in me.boards:
                scope.update(boards_mod.subtree(self.boards, b))
        else:
            scope = set(me.boards)
        rows = []
        for p in self.presence.values():
            if not (scope & set(p.boards)):
                continue
            rows.append({
                "session_id": p.session_id,
                "label": p.label,
                "cwd": p.cwd,
                "member": p.member,
                "status": self._status_of(p),
                "last_seen_seconds": self._now() - p.last_heartbeat,
                "boards": list(p.boards),
            })
        rows.sort(key=lambda r: r["label"])
        return rows
```

- [ ] In `coordination/src/mailbox/protocol.py`, add `"fleet"` to `OPS` (the federation line becomes):

```python
    "create_board", "set_parent", "tree", "fleet",
```

- [ ] Run `test_federation.py` (all green), then the full coordination suite (0 failures; adds 8 tests — flat-board installs see `subtree(b) == [b]`, so `ps`/`list_claims` defaults are behavior-identical).
- [ ] Commit:

```bash
git add coordination/src/mailbox/engine.py coordination/src/mailbox/protocol.py coordination/tests/test_federation.py
git commit -m "AWR federation: federated_presence/claims + fleet + ps/claims roll-up (T10)"
```

## Task 11: CLI — `fleet` verb + `ps`/`claims` `--federated/--local` — **Phase 2 checkpoint**

**Files**
- Modify: `coordination/src/mailbox/cli.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T11 — CLI fleet + ps/claims federation flags
# ---------------------------------------------------------------------------


def _cli_tree_with_two_sessions(tmp_path, monkeypatch):
    """org -> squad-api; one session per board, distinct cwds."""
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.chdir(b)
    assert cli.main(["--session", "s-org", "join", "--board", "org",
                     "--label", "org-sh"]) == 0


def test_cli_fleet_renders_subtree_presence(tmp_home, tmp_path, monkeypatch,
                                            capsys):
    client.ensure_running()
    _cli_tree_with_two_sessions(tmp_path, monkeypatch)
    capsys.readouterr()
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    assert cli.main(["fleet", "org"]) == 0
    out = capsys.readouterr().out
    assert "squad-sh" in out
    assert "org-sh" in out
    assert "named-squad-api" in out          # via_board annotation
    # bad ref errors cleanly
    assert cli.main(["fleet", "ghost"]) == 1
    assert "no-such-board: ghost" in capsys.readouterr().err
    # no board + no session: engine's no-board error
    assert cli.main(["fleet"]) == 1
    assert "no-board" in capsys.readouterr().err


def test_cli_ps_federated_default_and_local(tmp_home, tmp_path, monkeypatch,
                                            capsys):
    client.ensure_running()
    _cli_tree_with_two_sessions(tmp_path, monkeypatch)
    capsys.readouterr()
    assert cli.main(["--session", "s-org", "ps"]) == 0
    fed_out = capsys.readouterr().out
    assert "squad-sh" in fed_out and "org-sh" in fed_out
    assert cli.main(["--session", "s-org", "ps", "--local"]) == 0
    local_out = capsys.readouterr().out
    assert "squad-sh" not in local_out and "org-sh" in local_out


def test_cli_claims_federated_default_and_local(tmp_home, tmp_path,
                                                monkeypatch, capsys):
    client.ensure_running()
    _cli_tree_with_two_sessions(tmp_path, monkeypatch)
    target = str(tmp_path / "a" / "src" / "core.py")
    assert cli.main(["--session", "s-squad", "claim", target,
                     "--note", "api work"]) == 0
    capsys.readouterr()
    assert cli.main(["--session", "s-org", "claims"]) == 0
    assert "api work" in capsys.readouterr().out
    assert cli.main(["--session", "s-org", "claims", "--local"]) == 0
    assert "api work" not in capsys.readouterr().out
```

- [ ] Run and confirm the failures (argparse `SystemExit: 2` — `invalid choice: 'fleet'` / `unrecognized arguments: --local`):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

- [ ] Implement in `coordination/src/mailbox/cli.py`. Update the two command sets:

```python
_SESSION_OPTIONAL_CMDS = {"create-board", "set-parent", "tree", "fleet"}
```

```python
_FEDERATION_CMDS = {"create-board", "set-parent", "tree", "fleet",
                    "escalate", "broadcast"}
```

- [ ] Add `_print_fleet` directly after `_print_tree`:

```python
def _print_fleet(data: dict) -> None:
    rows = data.get("rows", []) if isinstance(data, dict) else []
    if not rows:
        print("(nobody in subtree)")
        return
    for r in rows:
        via = r.get("via_board", "?")
        via_name = r.get("via_name")
        if via_name:
            via += "  (%s)" % via_name
        print("%-20s  %-7s  %ss ago  %s" % (
            r.get("label", "?"),
            r.get("status", "?"),
            int(r.get("last_seen_seconds", 0)),
            via,
        ))
```

(`via_name` arrives in T14; `.get` keeps this renderer stable either way.)

- [ ] In `build_parser`, insert after the `tree` parser block:

```python
    sp = sub.add_parser("fleet")
    sp.add_argument("board", nargs="?", default=None)
```

and replace

```python
    sp = sub.add_parser("claims")
    sp.add_argument("--mine", action="store_true")
    sp.add_argument("--all", action="store_true")

    sub.add_parser("ps")
```

with:

```python
    sp = sub.add_parser("claims")
    sp.add_argument("--mine", action="store_true")
    sp.add_argument("--all", action="store_true")
    _add_fed_flags(sp)

    sp = sub.add_parser("ps")
    _add_fed_flags(sp)
```

- [ ] In `main`, insert after the `tree` dispatch branch:

```python
    elif cmd == "fleet":
        op = "fleet"
        op_args = {"session_id": session_id, "board": args.board}
```

replace the `claims` dispatch branch with:

```python
    elif cmd == "claims":
        if args.all:
            scope = "all"
        elif args.mine:
            scope = "mine"
        else:
            scope = "board"
        op = "list_claims"
        op_args = {"session_id": session_id, "scope": scope,
                   "federated": args.federated}
```

replace the `ps` dispatch branch with:

```python
    elif cmd == "ps":
        op = "ps"
        op_args = {"session_id": session_id, "federated": args.federated}
```

and add the fleet printer to the output block (after the `tree` line):

```python
    elif cmd == "fleet":
        _print_fleet(data or {})
```

- [ ] Run `test_federation.py` (all green), then **Phase 2 checkpoint** — both suites + sanitize:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
# coordination is template-only-sanitize-exempt by design; grep it for leaks too:
grep -RIn -i "twelvelabs\|twelve labs\|@twelvelabs\|tl-branding" /Users/aahil/Documents/Code/agentic-war-room/coordination/
```

Expected: 0 failures everywhere (coordination adds 3 tests this task, 50 since baseline; template unchanged at +17); sanitize exits 0; the coordination employer-leak grep prints NOTHING.

- [ ] Commit:

```bash
git add coordination/src/mailbox/cli.py coordination/tests/test_federation.py
git commit -m "AWR federation: CLI fleet verb + ps/claims --federated/--local (T11)"
```

---

# Phase 3 — Write-time broadcast push delivery

## Task 12: `origin_message_id`, `delivery` meta flag, `set_delivery`, push fan-out

**Files**
- Modify: `coordination/src/mailbox/models.py`
- Modify: `coordination/src/mailbox/engine.py`
- Modify: `coordination/src/mailbox/protocol.py`
- Modify: `coordination/src/mailbox/cli.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T12 — Phase 3: opt-in push delivery (delivery=push meta + origin_message_id)
# ---------------------------------------------------------------------------


def test_message_origin_message_id_sparse_serialization():
    m = Message(id="msg_0123456789ab", board="b", from_session="s1",
                from_label="l", to="*", kind="note", body="x", created=1.0)
    assert "origin_message_id" not in m.to_dict()
    m2 = Message(id="msg_0123456789ac", board="b", from_session="s1",
                 from_label="l", to="*", kind="note", body="x", created=1.0,
                 origin_message_id="msg_0123456789ab")
    d = m2.to_dict()
    assert d["origin_message_id"] == "msg_0123456789ab"
    assert Message.from_dict(d) == m2


def test_set_delivery_validates_and_persists(engine, clock):
    engine.create_board("squad-api")
    assert engine.set_delivery("squad-api", "push") == {
        "id": "named-squad-api", "delivery": "push"}
    assert engine.set_delivery("squad-api", "sideways") == {
        "error": "bad-delivery: sideways"}
    assert engine.set_delivery("ghost", "push") == {
        "error": "no-such-board: ghost"}
    reloaded = MailboxEngine(engine.state_dir, now_fn=lambda: clock.t)
    assert reloaded.boards["named-squad-api"]["delivery"] == "push"


def test_broadcast_pushes_copies_to_push_descendants_only(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.set_delivery("squad-api", "push")    # squad-web stays pull
    res = engine.send(session_id="s_org", to="*", kind="note",
                      body="org announcement", scope="broadcast")
    assert res["delivered"] == ["named-squad-api"]
    copies = [m for m in engine.messages.values()
              if m.origin_message_id == res["id"]]
    assert len(copies) == 1
    copy = copies[0]
    assert copy.board == "named-squad-api"
    assert copy.scope == "local"
    assert copy.from_label == "org-sh"          # original sender preserved
    assert copy.created == engine.messages[res["id"]].created


def test_push_fan_out_is_idempotent_per_origin(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.set_delivery("squad-api", "push")
    res = engine.send(session_id="s_org", to="*", kind="note",
                      body="once", scope="broadcast")
    origin = engine.messages[res["id"]]
    # a second fan-out of the SAME origin (e.g. replay after a topology edit)
    # delivers nothing new (D3: dedup on origin_message_id)
    assert engine._push_broadcast(origin) == []
    copies = [m for m in engine.messages.values()
              if m.origin_message_id == res["id"]]
    assert len(copies) == 1


def test_poll_inbox_push_board_receives_exactly_once(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.poll_inbox("s_api")                  # drain
    engine.set_delivery("squad-api", "push")
    sent = engine.send(session_id="s_org", to="*", kind="note",
                       body="pushed announcement", scope="broadcast")
    inbox = engine.poll_inbox("s_api")
    hits = [m for m in inbox if m["body"] == "pushed announcement"]
    # the materialized copy arrives as LOCAL; the read-time broadcast path is
    # suppressed for push boards — never a double delivery
    assert len(hits) == 1
    assert hits[0]["direction"] == "local"
    assert hits[0]["origin_board"] == "named-squad-api"
    assert hits[0]["origin_message_id"] == sent["id"]


def test_cli_set_delivery_verb(tmp_home, monkeypatch, capsys):
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    client.ensure_running()
    assert cli.main(["create-board", "squad-api"]) == 0
    capsys.readouterr()
    assert cli.main(["set-delivery", "squad-api", "push"]) == 0
    assert cli.main(["set-delivery", "ghost", "push"]) == 1
    assert "no-such-board: ghost" in capsys.readouterr().err
```

- [ ] Run and confirm the failures (`TypeError: __init__() got an unexpected keyword argument 'origin_message_id'`, `AttributeError: ... no attribute 'set_delivery'`, argparse `invalid choice: 'set-delivery'`):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

- [ ] Implement. In `coordination/src/mailbox/models.py` `Message`: add the field after `scope`:

```python
    scope: str = "local"       # "local" | "escalate" | "broadcast"
    origin_message_id: Optional[str] = None   # set on push-delivered copies
```

extend the sparse block in `to_dict`:

```python
        if d.get("scope") == "local":
            d.pop("scope", None)
        if d.get("origin_message_id") is None:
            d.pop("origin_message_id", None)
```

and add to `from_dict` (after the `scope=` line):

```python
            origin_message_id=d.get("origin_message_id"),
```

- [ ] In `coordination/src/mailbox/engine.py`, add `set_delivery` after `set_parent` (topology section):

```python
    def set_delivery(self, board, mode):
        """Per-board broadcast delivery mode (D1: default pull = read-time;
        push = materialized copies fan out at send time)."""
        if mode not in ("pull", "push"):
            return {"error": "bad-delivery: " + str(mode)}
        board_id = self._resolve_board_ref(board)
        if board_id is None:
            return {"error": "no-such-board: " + str(board)}
        self.boards[board_id]["delivery"] = mode
        self._persist_board_meta(board_id)
        self._audit_federation(
            "set-delivery id=%s mode=%s" % (board_id, mode))
        return {"id": board_id, "delivery": mode}
```

- [ ] Add `_push_broadcast` directly after the `send` method:

```python
    def _push_broadcast(self, msg):
        """Fan a broadcast out as materialized local copies to every
        descendant board in push mode. Dedup on origin_message_id (D3: no
        retroactive re-delivery on topology edits — fan-out happens only at
        send time; this guard protects replays). The tree is acyclic, so
        loops are impossible. Returns the boards delivered to."""
        delivered = []
        for dest in boards_mod.descendants(self.boards, msg.board):
            if (self.boards.get(dest) or {}).get("delivery") != "push":
                continue
            already = any(
                m.board == dest and m.origin_message_id == msg.id
                for m in self.messages.values())
            if already:
                continue
            copy = Message(
                id=self._gen_id("msg_"),
                board=dest,
                from_session=msg.from_session,
                from_label=msg.from_label,     # origin preserved: no spoofing
                to=msg.to,
                kind=msg.kind,
                body=msg.body,
                created=msg.created,           # original timestamp for ordering
                read_by=[],
                ref_paths=list(msg.ref_paths),
                scope="local",
                origin_message_id=msg.id,
            )
            self.messages[copy.id] = copy
            self._persist_message(copy)
            delivered.append(dest)
        if delivered:
            self._audit_federation(
                "push-delivered origin=%s boards=%s"
                % (msg.id, ",".join(delivered)))
        return delivered
```

- [ ] In `send`, replace the tail (from the audit block to `return {"id": msg.id}`) with:

```python
        if scope != "local":
            body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
            self._audit_federation(
                "send scope=%s board=%s from=%s body_sha=%s"
                % (scope, board, presence.label, body_sha))
        out = {"id": msg.id}
        if scope == "broadcast":
            delivered = self._push_broadcast(msg)
            if delivered:
                out["delivered"] = delivered
        return out
```

(`delivered` appears only when non-empty, so v1 callers asserting on the `{"id": ...}` shape are untouched.)

- [ ] In `poll_inbox`, replace the federated-set computation:

```python
        if federated:
            for b in boards:
                fed_up.update(boards_mod.descendants(self.boards, b))
                fed_down.update(boards_mod.ancestors(self.boards, b))
```

with:

```python
        if federated:
            for b in boards:
                fed_up.update(boards_mod.descendants(self.boards, b))
                if (self.boards.get(b) or {}).get("delivery") == "push":
                    # push boards receive materialized copies at send time;
                    # skipping the read-time broadcast path prevents doubles.
                    continue
                fed_down.update(boards_mod.ancestors(self.boards, b))
```

- [ ] In `coordination/src/mailbox/protocol.py`, the federation `OPS` line becomes:

```python
    "create_board", "set_parent", "set_delivery", "tree", "fleet",
```

- [ ] In `coordination/src/mailbox/cli.py`: add to both command sets —

```python
_SESSION_OPTIONAL_CMDS = {"create-board", "set-parent", "set-delivery",
                          "tree", "fleet"}
```

```python
_FEDERATION_CMDS = {"create-board", "set-parent", "set-delivery", "tree",
                    "fleet", "escalate", "broadcast"}
```

insert the parser after the `set-parent` block:

```python
    sp = sub.add_parser("set-delivery")
    sp.add_argument("board")
    sp.add_argument("mode", choices=["pull", "push"])
```

and the dispatch branch after `set-parent`'s:

```python
    elif cmd == "set-delivery":
        op = "set_delivery"
        op_args = {"board": args.board, "mode": args.mode}
```

- [ ] Run `test_federation.py` (all green), then the full coordination suite (0 failures; adds 6 tests).
- [ ] Commit:

```bash
git add coordination/src/mailbox/models.py coordination/src/mailbox/engine.py coordination/src/mailbox/protocol.py coordination/src/mailbox/cli.py coordination/tests/test_federation.py
git commit -m "AWR federation: opt-in push broadcast delivery + set-delivery verb (T12)"
```

## Task 13: contract §18 push-delivery update — **Phase 3 checkpoint**

**Files**
- Modify: `coordination/docs/internal/contract.md`

**Steps**

- [ ] The contract §18 stub written in T7 already names `set_delivery` and the
  `delivery` meta key, but T12 finalized the push semantics. Reconcile the doc with
  what shipped. In `coordination/docs/internal/contract.md` §18, locate the line in
  the "Extended ops" list that reads:

```markdown
- `send(..., scope="local")` — validates scope; escalate/broadcast posts are
  audited to `<state_dir>/federation.log` as `send scope=… board=… from=…
  body_sha=<sha256[:8]>` (bodies are hashed, never logged). Broadcasts fan
  out copies to push-mode descendant boards (`origin_message_id` dedup; no
  retroactive re-delivery on re-parent).
```

and replace it with the as-built description (return shape + the read-time
suppression rule both matter to callers):

```markdown
- `send(..., scope="local")` — validates scope (`{"error": "bad-scope: …"}` on a
  bad value); escalate/broadcast posts are audited to `<state_dir>/federation.log`
  as `send scope=… board=… from=… body_sha=<sha256[:8]>` (bodies are hashed,
  never logged). A `broadcast` send fans materialized LOCAL copies out to every
  descendant board in `delivery: push` mode (`from_label`/`created` preserved;
  `origin_message_id` carries the source id; dedup is on `origin_message_id` so a
  replay after a topology edit delivers nothing — no retroactive re-delivery).
  The return is `{"id": …}` plus `{"delivered": [board_id, …]}` ONLY when at least
  one push copy was written (v1 callers asserting the bare `{"id": …}` shape are
  unaffected). `poll_inbox` suppresses the read-time broadcast path for a session's
  push boards so a pushed message is never double-delivered.
```

- [ ] Verify the doc edit landed and still mentions the key surfaces:

```bash
grep -c "delivered" /Users/aahil/Documents/Code/agentic-war-room/coordination/docs/internal/contract.md
grep -c "origin_message_id" /Users/aahil/Documents/Code/agentic-war-room/coordination/docs/internal/contract.md
```

Expected: each prints ≥ 1.

- [ ] **Phase 3 checkpoint** — both full suites + sanitize:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
# coordination is template-only-sanitize-exempt by design; grep it for leaks too:
grep -RIn -i "twelvelabs\|twelve labs\|@twelvelabs\|tl-branding" /Users/aahil/Documents/Code/agentic-war-room/coordination/
```

Expected: 0 failures in both suites (coordination is at +56 tests since the
174-passed/1-skipped baseline; template steady at +17 over 409-passed/10-skipped);
sanitize exits 0.

- [ ] Commit:

```bash
git add coordination/docs/internal/contract.md
git commit -m "AWR federation: contract §18 push-delivery as-built reconciliation (T13)"
```

---

# Phase 4 — Operator surface polish

This phase adds NO new primitive — it enriches the renders the spec §6/§Observability
call for: `tree` shows per-node members/claims/delivery; `fleet` annotates each row
with the human board NAME (the `via_name` the T11 `_print_fleet` already reads via
`.get`); and a 3-level real-daemon round-trip pins the whole feature end-to-end
(spec Test strategy → "Integration (real daemon)").

## Task 14: richer `tree`/`fleet` node data + `via_name` annotation

**Files**
- Modify: `coordination/src/mailbox/engine.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T14 — Phase 4: richer tree/fleet render data (members, claims, depth, via_name)
# ---------------------------------------------------------------------------


def test_tree_nodes_carry_members_claims_depth_delivery(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    engine.set_delivery("squad-api", "push")
    target = str(tmp_path / "cwd2" / "src" / "core.py")
    engine.claim(session_id="s_api", globs=[target], note="api work")
    data = engine.tree()
    org = [n for n in data["roots"] if n["id"] == "named-org"][0]
    assert org["members"] == 1                       # org-sh on the org board
    assert org["depth"] == 0
    team = org["children"][0]
    assert team["depth"] == 1
    api = team["children"][0]
    assert api["id"] == "named-squad-api"
    assert api["delivery"] == "push"
    assert api["members"] == 1                        # api-sh
    assert api["claims"] >= 1                         # the explicit claim above
    assert api["depth"] == 2


def test_tree_node_members_count_excludes_offline(engine, tmp_path):
    engine.create_board("org")
    d = tmp_path / "o"
    d.mkdir()
    engine.join(session_id="s1", label="org-sh", cwd=str(d), board_name="org")
    engine.leave("s1")
    org = [n for n in engine.tree()["roots"] if n["id"] == "named-org"][0]
    assert org["members"] == 0


def test_federated_presence_annotates_via_name(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    rows = engine.federated_presence("named-org")
    api = [r for r in rows if r["label"] == "api-sh"][0]
    assert api["via_board"] == "named-squad-api"
    assert api["via_name"] == "squad-api"             # human name for renders


def test_fleet_rows_carry_via_name(engine, tmp_path):
    _setup_tree(engine, tmp_path)
    fl = engine.fleet(board="org")
    api = [r for r in fl["rows"] if r["label"] == "api-sh"][0]
    assert api["via_name"] == "squad-api"
```

- [ ] Run and confirm the failures (`KeyError: 'members'` / `KeyError: 'depth'` /
  `KeyError: 'via_name'`):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

- [ ] Implement in `coordination/src/mailbox/engine.py`. First enrich the `tree`
  node builder. Replace the inner `_node` closure inside the `tree` method (the
  block that begins `def _node(bid):` and returns `{"id": bid, "name": ...}`) with:

```python
        def _members(bid):
            return sum(
                1 for p in self.presence.values()
                if bid in p.boards and p.status != "offline")

        def _claims(bid):
            return sum(
                1 for c in self.claims.values()
                if c.board == bid and not c.released)

        def _node(bid):
            seen.add(bid)
            meta = self.boards.get(bid, {})
            children = []
            for cid in sorted(self.boards):
                if cid in seen:
                    continue
                if self.boards[cid].get("parent") == bid:
                    children.append(_node(cid))
            return {"id": bid, "name": meta.get("name"),
                    "orphan": bid in orphans,
                    "delivery": meta.get("delivery") or "pull",
                    "depth": boards_mod.depth(self.boards, bid),
                    "members": _members(bid), "claims": _claims(bid),
                    "children": children}
```

(The `members`/`claims` counts mirror the existing `board()` summary at
engine.py:601-609 — offline presence and released claims are excluded — so the
operator's `tree` view agrees with `mailbox board`.)

- [ ] Then annotate `federated_presence` rows with the human board name. In the
  `federated_presence` method, replace the `rows.append({...})` dict with:

```python
            via = hit[0]
            via_meta = self.boards.get(via, {})
            rows.append({
                "session_id": p.session_id,
                "label": p.label,
                "cwd": p.cwd,
                "member": p.member,
                "status": self._status_of(p),
                "last_seen_seconds": self._now() - p.last_heartbeat,
                "boards": list(p.boards),
                "via_board": via,
                "via_name": via_meta.get("name"),
            })
```

(`fleet` already returns `federated_presence(bid)` rows verbatim, so `via_name`
flows through it for free; the T11 `_print_fleet` renderer already reads it via
`.get`.)

- [ ] Run `test_federation.py` (all green), then the full coordination suite
  (0 failures; adds 4 tests). The new node keys are additive — `_print_tree` (T6)
  reads only `id`/`name`/`orphan`/`children`, and the `tree` op's existing tests in
  T3 index only those keys, so they stay green.
- [ ] Commit:

```bash
git add coordination/src/mailbox/engine.py coordination/tests/test_federation.py
git commit -m "AWR federation: richer tree node data (members/claims/depth/delivery) + fleet via_name (T14)"
```

## Task 15: richer `tree` render (depth indent already; show members/claims/delivery tags)

**Files**
- Modify: `coordination/src/mailbox/cli.py`
- Test: `coordination/tests/test_federation.py`

**Steps**

- [ ] Append to `coordination/tests/test_federation.py`:

```python
# ---------------------------------------------------------------------------
# T15 — Phase 4: tree CLI render shows members/claims/delivery tags
# ---------------------------------------------------------------------------


def test_cli_tree_render_shows_members_and_delivery(tmp_home, tmp_path,
                                                    monkeypatch, capsys):
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    assert cli.main(["set-delivery", "squad-api", "push"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    capsys.readouterr()
    assert cli.main(["tree"]) == 0
    out = capsys.readouterr().out
    # the squad node shows its live member count and its push delivery tag
    assert "named-squad-api  (squad-api)" in out
    assert "1 member" in out
    assert "push" in out


def test_cli_fleet_render_shows_via_name(tmp_home, tmp_path, monkeypatch,
                                         capsys):
    client.ensure_running()
    assert cli.main(["create-board", "org"]) == 0
    assert cli.main(["create-board", "squad-api", "--parent", "org"]) == 0
    a = tmp_path / "a"
    a.mkdir()
    monkeypatch.chdir(a)
    assert cli.main(["--session", "s-squad", "join", "--board", "squad-api",
                     "--label", "squad-sh"]) == 0
    monkeypatch.delenv("MAILBOX_SESSION_ID", raising=False)
    capsys.readouterr()
    assert cli.main(["fleet", "org"]) == 0
    out = capsys.readouterr().out
    assert "squad-sh" in out
    assert "(squad-api)" in out                     # via_name annotation
```

- [ ] Run and confirm the failures (`assert "1 member" in out` fails — the T6
  `_print_tree` does not yet render member/delivery tags):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation.py -q
```

- [ ] Implement in `coordination/src/mailbox/cli.py`. Replace the `_print_tree`
  function (added in T6) with the enriched renderer:

```python
def _print_tree(data: dict) -> None:
    roots = data.get("roots", []) if isinstance(data, dict) else []
    if not roots:
        print("(no boards)")
        return

    def _walk(node, indent):
        line = "%s%s" % (indent, node.get("id", "?"))
        name = node.get("name")
        if name:
            line += "  (%s)" % name
        tags = []
        members = node.get("members")
        if members is not None:
            tags.append("%d member%s" % (members, "" if members == 1 else "s"))
        claims = node.get("claims")
        if claims:
            tags.append("%d claim%s" % (claims, "" if claims == 1 else "s"))
        if node.get("delivery") == "push":
            tags.append("push")
        if node.get("orphan"):
            tags.append("orphan: parent missing")
        if tags:
            line += "  [%s]" % ", ".join(tags)
        print(line)
        for child in node.get("children", []):
            _walk(child, indent + "    ")

    for root in roots:
        _walk(root, "")
```

(The `fleet` render already shows `via_name` — the T11 `_print_fleet` appends
`"  (%s)" % via_name` when present, and T14 now supplies it — so the
`test_cli_fleet_render_shows_via_name` assertion passes without a `_print_fleet`
change. Verify this; do not re-edit `_print_fleet`.)

- [ ] Run `test_federation.py` (all green), then the full coordination suite
  (0 failures; adds 2 tests). The T6 `tree`-render test asserted exact indented
  lines like `"named-org  (org)"`; those substrings are still present (the tags are
  appended AFTER, in `[...]`), so that test stays green — confirm
  `test_cli_topology_verbs_need_no_session` still passes.
- [ ] Commit:

```bash
git add coordination/src/mailbox/cli.py coordination/tests/test_federation.py
git commit -m "AWR federation: tree render shows members/claims/delivery tags (T15)"
```

## Task 16: 3-level real-daemon e2e — full federation round-trip — **Phase 4 + final checkpoint**

**Files**
- Modify: `coordination/src/mailbox/protocol.py`
- Test: `coordination/tests/test_federation_e2e.py` (new)

This is the spec's "Integration (real daemon)" acceptance: build `org → team-platform
→ squad-api` over a live socket, post a local / escalate / broadcast, assert each
board's federated read is exactly the expected set, re-parent and assert the view
updates live, and assert push delivery fires the descendant inbox exactly once.

**Steps**

- [ ] **First, expose the two read helpers over the socket.** The e2e test
  dispatches `federated_messages` and `federated_presence` directly through
  `client.request` (`_req`), so they must be in `protocol.OPS` (T4/T10 added the
  CLI-facing ops `tree`/`fleet` but the engine read HELPERS were only called
  in-process until now). They are pure, side-effect-free reads, so exposing them is
  safe. In `coordination/src/mailbox/protocol.py`, change the federation `OPS` line
  from its T12 state:

```python
    "create_board", "set_parent", "set_delivery", "tree", "fleet",
```

to:

```python
    "create_board", "set_parent", "set_delivery", "tree", "fleet",
    "federated_messages", "federated_presence",
```

- [ ] Add a dispatch-exposure assertion to confirm both ops are reachable. Append to
  `coordination/tests/test_federation.py`:

```python
def test_dispatch_exposes_federated_read_ops(engine, tmp_path):
    from mailbox import protocol
    _setup_tree(engine, tmp_path)
    r1 = protocol.dispatch(engine, {"op": "federated_messages",
                                    "args": {"board_id": "named-org"}})
    assert r1["ok"] is True and isinstance(r1["data"], list)
    r2 = protocol.dispatch(engine, {"op": "federated_presence",
                                    "args": {"board_id": "named-org"}})
    assert r2["ok"] is True and isinstance(r2["data"], list)
```

- [ ] Run it (expect failure first if `OPS` not yet edited): `... -m pytest
  coordination/tests/test_federation.py -q -k dispatch_exposes_federated`. Expected:
  `assert {'ok': False, 'error': 'unknown op: federated_messages'}` until the `OPS`
  edit above lands; then 0 failures (adds 1 test).

- [ ] Create `coordination/tests/test_federation_e2e.py` (mirrors the `live_daemon`
  fixture idiom from `test_e2e.py:24-42`):

```python
"""Multi-board federation, end-to-end over a REAL daemon + socket (spec Test
strategy → Integration). Distinct cwds per session so repo boards never overlap;
all federation rides the named boards."""
import os

import pytest

from mailbox import client, daemon


@pytest.fixture
def live_daemon(tmp_home):
    client.ensure_running()
    pong = client.request("ping")
    assert pong.get("ok") is True, pong
    assert pong.get("data") == "pong", pong
    yield
    info = daemon.read_pidfile()
    if info and daemon.pid_alive(info["pid"]):
        try:
            os.kill(info["pid"], 15)
        except OSError:
            pass


def _req(op, args=None):
    resp = client.request(op, args or {})
    assert resp.get("ok") is True, (op, args, resp)
    return resp.get("data")


def _join(sid, label, cwd, board):
    os.makedirs(cwd, exist_ok=True)
    return _req("join", {"session_id": sid, "label": label, "cwd": cwd,
                         "board_name": board})


def test_e2e_three_level_federation_live_reparent(live_daemon, tmp_path):
    _req("create_board", {"name": "org"})
    _req("create_board", {"name": "team-platform", "parent": "org"})
    _req("create_board", {"name": "squad-api", "parent": "team-platform"})

    _join("s_org", "org-sh", str(tmp_path / "o"), "org")
    _join("s_api", "api-sh", str(tmp_path / "a"), "squad-api")
    _req("poll_inbox", {"session_id": "s_org"})       # drain join notes
    _req("poll_inbox", {"session_id": "s_api"})

    # local stays local; escalate rolls UP; broadcast rolls DOWN.
    _req("send", {"session_id": "s_api", "to": "*", "kind": "note",
                  "body": "api local"})
    _req("send", {"session_id": "s_api", "to": "*", "kind": "note",
                  "body": "api incident", "scope": "escalate"})
    _req("send", {"session_id": "s_org", "to": "*", "kind": "note",
                  "body": "org announcement", "scope": "broadcast"})

    fed_org = {m["body"]: m for m in _req("federated_messages",
                                          {"board_id": "named-org"})}
    assert "api local" not in fed_org                 # local never escalates
    assert fed_org["api incident"]["direction"] == "up"
    assert fed_org["api incident"]["origin_board"] == "named-squad-api"

    fed_api = {m["body"]: m for m in _req("federated_messages",
                                          {"board_id": "named-squad-api"})}
    assert fed_api["org announcement"]["direction"] == "down"
    assert fed_api["api local"]["direction"] == "local"

    # live re-parent: detach squad-api to a root — org is no longer its ancestor,
    # so the broadcast drops out of squad's view with NO cache to invalidate.
    _req("set_parent", {"board": "squad-api", "detach": True})
    fed_api2 = {m["body"]: m for m in _req("federated_messages",
                                           {"board_id": "named-squad-api"})}
    assert "org announcement" not in fed_api2
    assert fed_api2["api local"]["direction"] == "local"


def test_e2e_push_delivery_fires_descendant_inbox_once(live_daemon, tmp_path):
    _req("create_board", {"name": "org"})
    _req("create_board", {"name": "squad-api", "parent": "org"})
    _req("set_delivery", {"board": "squad-api", "mode": "push"})

    _join("s_org", "org-sh", str(tmp_path / "o"), "org")
    _join("s_api", "api-sh", str(tmp_path / "a"), "squad-api")
    _req("poll_inbox", {"session_id": "s_api"})       # drain join notes

    _req("send", {"session_id": "s_org", "to": "*", "kind": "note",
                  "body": "pushed announcement", "scope": "broadcast"})

    inbox = _req("poll_inbox", {"session_id": "s_api"})
    hits = [m for m in inbox if m["body"] == "pushed announcement"]
    assert len(hits) == 1                              # exactly once
    assert hits[0]["origin_board"] == "named-squad-api"
    # read receipt suppresses redelivery
    again = _req("poll_inbox", {"session_id": "s_api"})
    assert all(m["body"] != "pushed announcement" for m in again)


def test_e2e_fleet_and_tree_live(live_daemon, tmp_path):
    _req("create_board", {"name": "org"})
    _req("create_board", {"name": "squad-api", "parent": "org"})
    _join("s_api", "api-sh", str(tmp_path / "a"), "squad-api")

    fl = _req("fleet", {"board": "org"})
    assert any(r["label"] == "api-sh" for r in fl["rows"])
    assert [r for r in fl["rows"] if r["label"] == "api-sh"][0]["via_name"] == "squad-api"

    data = _req("tree", {})
    org = [n for n in data["roots"] if n["id"] == "named-org"][0]
    assert org["children"][0]["id"] == "named-squad-api"
    assert org["children"][0]["members"] == 1
```

- [ ] Run the new e2e file (expect all green — every op it exercises shipped in
  T1–T15):

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination/tests/test_federation_e2e.py -q
```

Expected: 0 failures (adds 3 tests). If a federated read returns an unexpected set,
debug with `superpowers:systematic-debugging` — never weaken the assertion to make
it pass.

- [ ] **Final checkpoint** — both full suites (default + template integration) +
  sanitization + the post-Option-B guard greps:

```bash
/Users/aahil/Documents/Code/agentic-war-room/coordination/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/coordination -q
/Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q
PYTHONPATH=/Users/aahil/Documents/Code/agentic-war-room/coordination/src /Users/aahil/Documents/Code/agentic-war-room/template/.venv/bin/python -m pytest /Users/aahil/Documents/Code/agentic-war-room/template -q --runintegration
python3 /Users/aahil/Documents/Code/agentic-war-room/template/scripts/sanitize_check.py /Users/aahil/Documents/Code/agentic-war-room/template/
grep -RIn -i "twelvelabs\|twelve labs\|@twelvelabs\|tl-branding" /Users/aahil/Documents/Code/agentic-war-room/template/ /Users/aahil/Documents/Code/agentic-war-room/coordination/
grep -RIn "normalize_unsentineled_blocks\|_strip_bare_block\|_MANAGED_BLOCKS" /Users/aahil/Documents/Code/agentic-war-room/template/
```

Expected: 0 failures in the coordination suite (now +66 tests over the
174-passed/1-skipped baseline: T1-T6=39, T10=8, T11=3, T12=6, T14=4, T15=2,
T16=4 incl. the 3 e2e tests in test_federation_e2e.py) and the template suite
(+17 over the
409-passed/10-skipped baseline); the template `--runintegration` run is green
(0 failures, same +17 federation tests — the `--runintegration` baseline is not
recorded in the Verified-baselines block, so assert 0 failures rather than an
absolute total); `sanitize_check` exits 0; both employer-leak and post-Option-B
guard greps print NOTHING.

- [ ] Commit:

```bash
git add coordination/src/mailbox/protocol.py coordination/tests/test_federation.py coordination/tests/test_federation_e2e.py
git commit -m "AWR federation: expose federated read ops + 3-level real-daemon e2e (re-parent, push-once, fleet/tree) (T16)"
```

---

## Appendix — cross-task symbol consistency (verify before executing)

These symbols are defined once and referenced across tasks; spell them identically.

- **`Message`** (T1, extended T12): `scope: str = "local"`,
  `origin_message_id: Optional[str] = None`. `to_dict()` is SPARSE (omits `scope`
  when `"local"`, omits `origin_message_id` when `None`) — this is what keeps
  `coordination/tests/test_models.py::test_message_to_dict_has_all_fields` green
  UNCHANGED. `from_dict` restores both defaults.
- **`boards.py`** (T2): `parent_of`, `ancestors`, `descendants`, `subtree`,
  `is_ancestor`, `depth`, `height`, `validate_parent(boards, board_id, parent_id) ->
  Optional[str]` (error string or None), `MAX_FEDERATION_DEPTH = 8`. Every helper
  takes the boards-meta dict as its FIRST arg.
- **Engine** (T3/T4/T5/T10/T12/T14): `create_board(name, parent=None)`,
  `set_parent(board, parent=None, detach=False)`, `set_delivery(board, mode)`,
  `tree(board=None)`, `fleet(session_id=None, board=None)`,
  `federated_messages(board_id)`, `federated_presence(board_id)`,
  `federated_claims(board_id)`, `send(..., scope="local")`,
  `poll_inbox(session_id, federated=True)`, `ps(session_id, federated=True)`,
  `list_claims(session_id, scope="board", federated=True)`, and the helpers
  `_resolve_board_ref(ref)`, `_persist_board_meta(board_id)`,
  `_audit_federation(line)`, `_subtree_sessions(sub)` (claims roll up by HOLDER
  presence membership, since claims live on repo boards outside named subtrees),
  `_push_broadcast(msg)`.
- **`protocol.OPS`** additions, in the order they land: `create_board` +
  `set_parent` + `tree` (T3), `fleet` (T10), `set_delivery` (T12),
  `federated_messages` + `federated_presence` (T16). Engine method names == op
  names. `federated_claims` is NOT in `OPS` — it is reached only via `list_claims`/
  `fleet` and in-process tests, never dispatched directly. The e2e test (T16)
  dispatches `federated_messages` and `federated_presence` over the socket, which is
  exactly why T16's first step adds them to `OPS`.
- **CLI verbs**: `create-board`, `set-parent`, `set-delivery`, `tree`, `fleet`,
  `escalate`, `broadcast`, `send --scope`, `ps/claims/inbox --federated|--local`.
  Module sets `_SESSION_OPTIONAL_CMDS` and `_FEDERATION_CMDS` grow in T6/T11/T12.
- **Direction tokens**: `"local"` / `"up"` / `"down"` (NOT `"own"`/`"escalated"`/
  `"broadcast"`); annotation keys `origin_board`, `via_board`, `via_name`.
- **`EnrollState`** (T9): adds `parent: Optional[str] = None`,
  `parent_status: Optional[str] = None` (both defaulted, so existing
  keyword-constructions stay valid). `bootstrap(..., parent=None)` trailing kwarg;
  `_ensure_parent_link(cli, board, parent, env=None) -> str` ("ok"|"parent-failed").
- **Schema/wizard** (T8): `WAR_ROOM_KEYS` has `parent` between `board` and `label`;
  `DEFAULTS["parent"] == ""`; selectables `warroom.parent` field appended LAST with
  `enable_if="warroom.enroll"`; `run_setup`/`cmd_enroll` pass `parent=` only when
  non-empty.
- **Fixture/board names** everywhere: `org`, `team-platform`, `squad-api`,
  `squad-web`, `solo`, `shared`, `alpha-sh`, `beta-sh`, `foreign-sh`, plus session
  labels `org-sh`/`team-sh`/`api-sh`/`web-sh`/`squad-sh`. NEVER a real employer or
  operator handle.
