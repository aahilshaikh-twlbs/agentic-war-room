"""T8 (revised) — end-to-end runtime proof: <profile>/.env → mailbox hook → real
daemon join, two profiles meeting on a forced named board.

Load-bearing proof of Feature C under the revised T3 (.env propagation, no
template-side hook). enroll.bootstrap writes MAILBOX_BOARD/LABEL into
<profile>/.env; Hermes would load that into the env that reaches mailbox's own
SessionStart hook. We SIMULATE that load by reading <profile>/.env and running
the REAL mailbox hook with those vars set, against a REAL (tmp-isolated) daemon.
Two profiles with DIFFERENT cwds still meet on board "shared" — provable only
because .env forced MAILBOX_BOARD.

NOTE (surfaced): lane CLAIMS are scoped to the cwd-derived repo board, not the
named board, so a cross-cwd claim-deny does NOT fire (covered in-process by T7
with a shared cwd). T8 asserts the cross-cwd meeting + messaging hero path and
single-session lane claim/release.

Gated: @integration + --runintegration; skipped unless coordination mailbox is
importable.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "template"
MAILBOX_HOOK = REPO / "coordination" / "hooks" / "session_start.py"


def _mailbox_importable():
    try:
        import mailbox.client  # noqa: F401
        import mailbox.engine  # noqa: F401
        return True
    except Exception:
        return False


pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not _mailbox_importable(),
                                 reason="coordination mailbox not importable")]


@pytest.fixture
def mailbox_runtime():
    # Short /tmp home: AF_UNIX sun_path is ~104 chars; pytest tmp is too long.
    mh = tempfile.mkdtemp(dir="/tmp", prefix="awr8")
    prev = {k: os.environ.get(k) for k in ("MAILBOX_HOME", "MAILBOX_SOCKET")}
    os.environ["MAILBOX_HOME"] = mh
    os.environ["MAILBOX_SOCKET"] = os.path.join(mh, "d.sock")
    try:
        yield mh
    finally:
        pidfile = os.path.join(mh, "mailboxd.pid")
        sock = os.path.join(mh, "d.sock")
        try:
            pid = int(Path(pidfile).read_text().strip())
        except (OSError, ValueError):
            pid = None
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            deadline = time.time() + 5
            while time.time() < deadline and os.path.exists(sock):
                time.sleep(0.1)
            if os.path.exists(sock):
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(mh, ignore_errors=True)


def _build_profile(root, handle):
    from warroom_setup import enroll
    prof = root / handle
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    # bootstrap writes the mailbox: block AND <profile>/.env routing.
    enroll.bootstrap(prof, "shared", handle, env=dict(os.environ))
    return prof


def _parse_env(prof):
    out = {}
    p = prof / ".env"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _, v = s.partition("=")
            out[k.strip()] = v.strip()
    return out


def _run_mailbox_hook(profile, session_id, cwd):
    """Simulate Hermes loading <profile>/.env, then run the real mailbox hook."""
    env = dict(os.environ)
    env.update(_parse_env(profile))  # the vars Hermes would have loaded
    env["PYTHONPATH"] = str(REPO / "coordination" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    import json
    payload = json.dumps({"session_id": session_id, "cwd": cwd})
    r = subprocess.run([sys.executable, str(MAILBOX_HOOK)],
                       input=payload, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_two_profiles_meet_via_real_hook_chain(tmp_path, mailbox_runtime):
    # 1-3. Two profiles, different cwds, same board; routing lands in .env.
    alpha = _build_profile(tmp_path, "alpha-sh")
    beta = _build_profile(tmp_path, "beta-sh")
    assert "board: shared" in (alpha / "config.yaml").read_text()
    a_env = _parse_env(alpha)
    assert a_env.get("MAILBOX_BOARD") == "shared"
    assert a_env.get("MAILBOX_LABEL") == "alpha-sh"
    assert _parse_env(beta).get("MAILBOX_BOARD") == "shared"

    # 4-5. .env -> mailbox hook joins the forced board (real daemon).
    _run_mailbox_hook(alpha, "sess-a", "/tmp/alpha")
    _run_mailbox_hook(beta, "sess-b", "/tmp/beta")

    # 6. Despite different cwds, they meet on board "shared".
    import mailbox.client as client
    resp = client.request("ps", {"session_id": "sess-a"})
    assert resp.get("ok") is True, resp
    labels = {row["label"] for row in resp["data"]}
    assert "beta-sh" in labels, resp["data"]

    # 7-9. send + read-once inbox across the named board.
    s = client.request("send", {"session_id": "sess-a", "to": "beta-sh",
                                 "kind": "msg", "body": "hello"})
    assert s.get("ok") is True, s
    inbox = client.request("poll_inbox", {"session_id": "sess-b"})
    assert any(m["body"] == "hello" for m in inbox["data"]), inbox["data"]
    inbox2 = client.request("poll_inbox", {"session_id": "sess-b"})
    assert all(m["body"] != "hello" for m in inbox2["data"])

    # 10-13. single-session lane claim/release (cross-cwd deny is repo-scoped;
    # proven in-process by T7).
    c = client.request("claim_lane", {"session_id": "sess-a", "lane": "auth"})
    assert c["data"]["decision"] == "allow", c
    r = client.request("release_lane", {"session_id": "sess-a", "lane": "auth"})
    assert r.get("ok") is True, r
