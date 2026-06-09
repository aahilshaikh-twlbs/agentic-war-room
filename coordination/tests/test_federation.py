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
