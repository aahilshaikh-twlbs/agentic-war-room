"""T8 (renumbered from T8b) — end-to-end runtime proof: template hook → mailbox
hook → real daemon join, two profiles meeting on a forced named board.

This is the load-bearing proof of Feature C. It runs the REAL mailbox
session_start hook against a REAL (tmp, isolated) daemon and shows that two
profiles with DIFFERENT cwds still land on the same named board — provable only
because the template hook forced MAILBOX_BOARD into the mailbox hook's env.

NOTE (surfaced): lane CLAIMS are scoped to the cwd-derived repo board, not the
named board, so a cross-cwd claim-deny does NOT fire (covered in-process by T7
with a shared cwd). T8 asserts the cross-cwd *meeting* + messaging hero path and
single-session lane claim/release.

Gated: @integration + --runintegration; skipped unless the coordination mailbox
package is importable.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

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
        pid = None
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
    from warroom_setup import setup
    prof = root / handle
    (prof / "hooks").mkdir(parents=True)
    (prof / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_mailbox_block(prof, board="shared", label=handle)
    shutil.copy2(TEMPLATE / "hooks" / "session_start.py", prof / "hooks" / "session_start.py")
    return prof


def _run_template_hook(prof, env_file, home):
    env = dict(os.environ)
    env["HOME"] = home
    env["CLAUDE_ENV_FILE"] = str(env_file)
    r = subprocess.run([sys.executable, str(prof / "hooks" / "session_start.py")],
                       input="", capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return Path(env_file).read_text(encoding="utf-8") if Path(env_file).exists() else ""


def _exports_to_env(env_text):
    out = {}
    for line in env_text.splitlines():
        if line.startswith("export ") and "=" in line:
            k, _, v = line[len("export "):].partition("=")
            out[k] = v
    return out


def _run_mailbox_hook(extra_env, session_id, cwd):
    env = dict(os.environ)
    env.update(extra_env)
    env["PYTHONPATH"] = str(REPO / "coordination" / "src") + os.pathsep + env.get("PYTHONPATH", "")
    payload = json.dumps({"session_id": session_id, "cwd": cwd})
    r = subprocess.run([sys.executable, str(MAILBOX_HOOK)],
                       input=payload, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_two_profiles_meet_via_real_hook_chain(tmp_path, mailbox_runtime):
    home = str(tmp_path / "home")
    os.makedirs(home, exist_ok=True)

    # 1-3. Two profiles, different cwds, same board.
    alpha = _build_profile(tmp_path, "alpha-sh")
    beta = _build_profile(tmp_path, "beta-sh")
    assert "board: shared" in (alpha / "config.yaml").read_text()
    assert "board: shared" in (beta / "config.yaml").read_text()

    # 4-5. Template hook -> env_file exports -> mailbox hook joins forced board.
    a_env = _exports_to_env(_run_template_hook(alpha, tmp_path / "a.env", home))
    assert a_env.get("MAILBOX_BOARD") == "shared"
    assert a_env.get("MAILBOX_LABEL") == "alpha-sh"
    _run_mailbox_hook(a_env, "sess-a", "/tmp/alpha")

    b_env = _exports_to_env(_run_template_hook(beta, tmp_path / "b.env", home))
    assert b_env.get("MAILBOX_BOARD") == "shared"
    _run_mailbox_hook(b_env, "sess-b", "/tmp/beta")

    # 6. Real daemon: despite different cwds, they meet on board "shared".
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

    # 10-13. Single-session lane claim/release (cross-cwd deny is engine-scoped to
    # the repo board; proven in-process by T7).
    c = client.request("claim_lane", {"session_id": "sess-a", "lane": "auth"})
    assert c["data"]["decision"] == "allow", c
    r = client.request("release_lane", {"session_id": "sess-a", "lane": "auth"})
    assert r.get("ok") is True, r
