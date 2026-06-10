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
