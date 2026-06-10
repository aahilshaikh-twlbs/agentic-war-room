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
