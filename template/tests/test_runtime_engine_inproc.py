"""T7 (renumbered from T8a) — in-process MailboxEngine integration.

Drives MailboxEngine directly (no socket, no protocol envelope) for fast,
hermetic, envelope-free assertions of the cross-agent semantics.

NOTE (surfaced to team-lead): the engine scopes LANE claims to boards[0] = the
cwd-derived REPO board, while ps/send/inbox route via the NAMED board
(boards[-1]). So cross-cwd peers see each other and exchange messages on the
named board, but they do NOT see each other's lane claims unless they share a
repo board. The plan's T7 used different cwds yet expected a claim-deny; that is
inconsistent with the read-only engine. This test therefore uses a SHARED cwd so
all eleven steps (including the claim-deny path) exercise faithfully. Cross-cwd
named-board meeting is proven by ps/send/inbox here and end-to-end in T8.
"""
import os

import pytest

pytestmark = pytest.mark.integration


def _engine_available():
    # F16: stdlib `mailbox` is a MODULE, not a package, so
    # importlib.util.find_spec("mailbox.engine") RAISES rather than returning
    # None. A plain guarded import is the only robust probe.
    try:
        import mailbox.engine  # noqa: F401
        import mailbox.client  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _engine_available(),
                    reason="coordination mailbox package not importable")
def test_two_sessions_meet_on_named_board_inprocess(tmp_path):
    from mailbox.engine import MailboxEngine

    clock = [1000.0]
    eng = MailboxEngine(state_dir=str(tmp_path / "state"), now_fn=lambda: clock[0])
    eng.load()

    wd = str(tmp_path / "wd")
    os.makedirs(wd, exist_ok=True)

    ra = eng.join(session_id="a", label="alpha-sh", cwd=wd, board_name="shared")
    rb = eng.join(session_id="b", label="beta-sh", cwd=wd, board_name="shared")

    # (4) both land on the same named board (boards[-1]) and the same repo board.
    assert ra["boards"] == rb["boards"]
    named = ra["boards"][-1]
    assert named in eng.presence["a"].boards
    assert named in eng.presence["b"].boards
    labels = {p.label for p in eng.presence.values()}
    assert {"alpha-sh", "beta-sh"} <= labels

    # (5-7) send + read-once inbox across the named board.
    eng.send(session_id="a", to="beta-sh", kind="msg", body="hello")
    inbox = eng.poll_inbox(session_id="b")
    assert any(m["body"] == "hello" for m in inbox)
    assert eng.poll_inbox(session_id="b") == []

    # (8-11) lane claim / deny / release / re-claim.
    r1 = eng.claim_lane(session_id="a", lane="auth", note="refactor")
    assert r1["decision"] == "allow"
    r2 = eng.claim_lane(session_id="b", lane="auth")
    assert r2["decision"] == "deny"
    assert r2["holder"] == "alpha-sh"
    eng.release_lane(session_id="a", lane="auth")
    r3 = eng.claim_lane(session_id="b", lane="auth")
    assert r3["decision"] == "allow"
