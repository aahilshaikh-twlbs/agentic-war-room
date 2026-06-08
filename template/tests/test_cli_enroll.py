"""T5 — `warroom enroll` CLI subcommand + exit-code contract."""
import json
import socket
import sys
import tempfile
import threading
from pathlib import Path

from warroom_setup import cli, enroll, runtime_state


def _profile(tmp_path):
    prof = tmp_path / "profiles" / "alpha-sh"
    (prof / "hooks").mkdir(parents=True)
    prof.joinpath("config.yaml").write_text("model: {}\n", encoding="utf-8")
    return prof


def _write_state(prof, **over):
    local = prof / "local"
    local.mkdir(parents=True, exist_ok=True)
    data = {"board": "shared", "label": "alpha-sh", "cli_path": "/x/mailbox",
            "mailbox_home": "/x", "socket_path": "/x/mailboxd.sock",
            "last_check_ts": 0.0, "status": "ok"}
    data.update(over)
    runtime_state.save_state(local / "warroom-enroll.json", data)
    return data


def test_cli_enroll_invokes_bootstrap_with_args(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    calls = []
    monkeypatch.setattr(enroll, "bootstrap", lambda pr, b, l, dry_run=False, env=None: (
        calls.append((b, l)) or enroll.EnrollState(b, l, None, "", "", 0.0, "ok")))
    rc = cli.main(["enroll", "--board", "shared", "--label", "alpha-sh",
                   "--profile-root", str(prof)])
    assert rc == 0
    assert calls == [("shared", "alpha-sh")]


def test_cli_enroll_status_prints_json_when_state_exists(tmp_path, capsys):
    prof = _profile(tmp_path)
    _write_state(prof, socket_path=str(tmp_path / "nope.sock"))
    cli.main(["enroll", "--status", "--profile-root", str(prof)])
    out = json.loads(capsys.readouterr().out)
    assert out["board"] == "shared" and out["label"] == "alpha-sh"
    assert "daemon_reachable" in out


def test_cli_enroll_status_handles_no_state_returns_exit_3(tmp_path):
    prof = _profile(tmp_path)
    rc = cli.main(["enroll", "--status", "--profile-root", str(prof)])
    assert rc == 3


def test_cli_enroll_status_returns_exit_2_when_daemon_unreachable(tmp_path):
    prof = _profile(tmp_path)
    _write_state(prof, status="ok", socket_path=str(tmp_path / "absent.sock"))
    rc = cli.main(["enroll", "--status", "--profile-root", str(prof)])
    assert rc == 2


def test_cli_enroll_status_returns_exit_1_when_cli_not_found(tmp_path):
    prof = _profile(tmp_path)
    _write_state(prof, status="cli-not-found", cli_path=None)
    rc = cli.main(["enroll", "--status", "--profile-root", str(prof)])
    assert rc == 1


def test_cli_enroll_status_returns_exit_0_when_all_ok(tmp_path):
    prof = _profile(tmp_path)
    # AF_UNIX sun_path is ~104 chars; pytest tmp paths blow past it, so bind in
    # a short /tmp dir.
    sock_dir = tempfile.mkdtemp(dir="/tmp", prefix="awrc")
    sock_path = Path(sock_dir) / "s.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)
    stop = threading.Event()

    def _serve():
        srv.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    try:
        _write_state(prof, status="ok", socket_path=str(sock_path))
        rc = cli.main(["enroll", "--status", "--profile-root", str(prof)])
        assert rc == 0
    finally:
        stop.set()
        srv.close()
        t.join(timeout=2)
        import shutil
        shutil.rmtree(sock_dir, ignore_errors=True)


def test_cli_enroll_dry_run_propagates_flag(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    seen = {}
    monkeypatch.setattr(enroll, "bootstrap", lambda pr, b, l, dry_run=False, env=None: (
        seen.update(dry_run=dry_run) or enroll.EnrollState(b, l, None, "", "", 0.0, "dry-run")))
    cli.main(["enroll", "--board", "shared", "--dry-run", "--profile-root", str(prof)])
    assert seen["dry_run"] is True


def test_cli_enroll_reconfigure_bypasses_idempotency_guard(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    _write_state(prof)  # pre-existing enrollment
    calls = []
    monkeypatch.setattr(enroll, "bootstrap", lambda pr, b, l, dry_run=False, env=None: (
        calls.append(b) or enroll.EnrollState(b, l, None, "", "", 0.0, "ok")))
    # without --reconfigure: no-op guard skips bootstrap
    cli.main(["enroll", "--board", "shared", "--profile-root", str(prof)])
    assert calls == []
    # with --reconfigure: bootstrap runs
    cli.main(["enroll", "--board", "shared", "--reconfigure", "--profile-root", str(prof)])
    assert calls == ["shared"]


def test_enroll_status_does_not_import_mailbox_client(tmp_path):
    prof = _profile(tmp_path)
    _write_state(prof, socket_path=str(tmp_path / "nope.sock"))
    before = set(sys.modules)
    enroll.enroll_status(prof)
    added = set(sys.modules) - before
    assert not any("mailbox.client" in m for m in added)
    assert "mailbox.client" not in sys.modules or "mailbox.client" in before
