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
