"""Lane claims: subtask/work-unit coordination for dogpile boards.

A *lane* is a named work-unit (e.g. "fix-auth-bug") that an agent stakes so
that two agents dogpiling the same problem don't both grab the same piece.
Lanes reuse the exact claim-conflict machinery as file claims -- a lane is a
claim whose "path" is the URI ``lane://<id>`` -- so deny-on-live-holder,
warn-on-stale, release, and seize all behave identically. These tests pin the
lane-specific surface (claim_lane / release_lane / list_lanes) and prove lanes
never collide with real file paths.
"""

from mailbox import config


def _join_two(engine, cwd):
    engine.join("sessA", "alice", cwd)
    engine.join("sessB", "bob", cwd)


def test_claim_lane_allows_when_free(engine, tmp_path):
    engine.join("sessA", "alice", str(tmp_path))

    res = engine.claim_lane("sessA", "fix-auth", note="taking auth")

    assert res["decision"] == "allow"
    assert res["lane"] == "fix-auth"
    assert res["claim_id"].startswith("clm_")
    claim = engine.claims[res["claim_id"]]
    assert claim.session_id == "sessA"
    assert claim.kind == "explicit"
    assert claim.paths == ["lane://fix-auth"]
    assert claim.note == "taking auth"


def test_claiming_same_lane_twice_is_idempotent(engine, tmp_path):
    engine.join("sessA", "alice", str(tmp_path))

    first = engine.claim_lane("sessA", "fix-auth")
    second = engine.claim_lane("sessA", "fix-auth")

    assert first["claim_id"] == second["claim_id"]
    assert second["decision"] == "allow"
    # exactly one claim was created for this lane
    lane_claims = [c for c in engine.claims.values()
                   if "lane://fix-auth" in c.paths and not c.released]
    assert len(lane_claims) == 1


def test_live_lane_conflict_denies(engine, tmp_path):
    _join_two(engine, str(tmp_path))

    a = engine.claim_lane("sessA", "fix-auth")
    assert a["decision"] == "allow"

    b = engine.claim_lane("sessB", "fix-auth")
    assert b["decision"] == "deny"
    assert b["lane"] == "fix-auth"
    assert b["holder"] == "alice"
    assert b["holder_session"] == "sessA"
    assert b["claim_id"] == a["claim_id"]
    assert b["since_seconds"] >= 0


def test_stale_lane_conflict_warns(engine, tmp_path, clock):
    _join_two(engine, str(tmp_path))

    engine.claim_lane("sessA", "fix-auth")
    clock.t += config.HEARTBEAT_STALE_SECONDS + 1

    b = engine.claim_lane("sessB", "fix-auth")
    assert b["decision"] == "warn"
    assert b["holder"] == "alice"
    assert b["stale_seconds"] >= config.HEARTBEAT_STALE_SECONDS


def test_different_lanes_dont_collide(engine, tmp_path):
    _join_two(engine, str(tmp_path))

    a = engine.claim_lane("sessA", "fix-auth")
    b = engine.claim_lane("sessB", "fix-billing")

    assert a["decision"] == "allow"
    assert b["decision"] == "allow"
    assert a["claim_id"] != b["claim_id"]


def test_lane_never_collides_with_file_path(engine, tmp_path):
    """A lane URI and a real file path must be mutually invisible."""
    import os
    _join_two(engine, str(tmp_path))

    # A stakes a lane that textually resembles a path component
    engine.claim_lane("sessA", "src/app.py")
    # B writes the actual file -- must NOT be denied by the lane claim
    fp = os.path.join(str(tmp_path), "src", "app.py")
    b = engine.check_write("sessB", fp)
    assert b["decision"] == "allow"


def test_file_claim_never_denies_a_lane(engine, tmp_path):
    import os
    _join_two(engine, str(tmp_path))

    fp = os.path.join(str(tmp_path), "src", "app.py")
    engine.check_write("sessA", fp)
    # B claims a lane -- the file auto-claim must not interfere
    b = engine.claim_lane("sessB", "src/app.py")
    assert b["decision"] == "allow"


def test_release_lane_frees_it(engine, tmp_path):
    _join_two(engine, str(tmp_path))

    engine.claim_lane("sessA", "fix-auth")
    rel = engine.release_lane("sessA", "fix-auth")
    assert len(rel["released"]) == 1

    # now B can take it
    b = engine.claim_lane("sessB", "fix-auth")
    assert b["decision"] == "allow"


def test_list_lanes_shows_active_lanes(engine, tmp_path):
    _join_two(engine, str(tmp_path))

    engine.claim_lane("sessA", "fix-auth", note="auth work")
    engine.claim_lane("sessB", "fix-billing")

    lanes = engine.list_lanes("sessA")
    by_name = {l["lane"]: l for l in lanes}
    assert set(by_name) == {"fix-auth", "fix-billing"}
    assert by_name["fix-auth"]["label"] == "alice"
    assert by_name["fix-auth"]["note"] == "auth work"
    assert by_name["fix-auth"]["live"] is True
    assert by_name["fix-billing"]["label"] == "bob"


def test_list_lanes_excludes_released(engine, tmp_path):
    engine.join("sessA", "alice", str(tmp_path))
    engine.claim_lane("sessA", "fix-auth")
    engine.release_lane("sessA", "fix-auth")

    assert engine.list_lanes("sessA") == []


def test_list_lanes_excludes_file_claims(engine, tmp_path):
    import os
    engine.join("sessA", "alice", str(tmp_path))
    engine.check_write("sessA", os.path.join(str(tmp_path), "f.py"))
    engine.claim_lane("sessA", "fix-auth")

    lanes = engine.list_lanes("sessA")
    assert len(lanes) == 1
    assert lanes[0]["lane"] == "fix-auth"


def test_lanes_survive_reload(engine, tmp_path, clock):
    """Lane claims persist to disk and reload cleanly (crash recovery)."""
    from mailbox.engine import MailboxEngine
    engine.join("sessA", "alice", str(tmp_path))
    engine.claim_lane("sessA", "fix-auth", note="auth")

    reloaded = MailboxEngine(str(tmp_path), now_fn=clock)
    lane_claims = [c for c in reloaded.claims.values()
                   if "lane://fix-auth" in c.paths]
    assert len(lane_claims) == 1
    assert lane_claims[0].note == "auth"
