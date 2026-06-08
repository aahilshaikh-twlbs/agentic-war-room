"""T3 (revised) — enroll.write_runtime_env delivers routing via <profile>/.env.

Per lead's redirect: no template-side SessionStart hook and no settings.json
edit. Hermes loads <profile>/.env into the env that reaches mailbox's own hook,
which reads MAILBOX_BOARD / MAILBOX_LABEL from os.environ.
"""
from pathlib import Path

from warroom_setup import enroll


def _state(board="shared", label="alpha-sh", home="", sock=""):
    return enroll.EnrollState(board=board, label=label, cli_path=None,
                              mailbox_home=home, socket_path=sock,
                              last_check_ts=0.0, status="ok")


def _read_env(prof):
    return (prof / ".env").read_text(encoding="utf-8")


def test_write_runtime_env_writes_board_and_label(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    enroll.write_runtime_env(prof, _state(), env={"HOME": str(tmp_path / "h")})
    txt = _read_env(prof)
    assert "MAILBOX_BOARD=shared" in txt
    assert "MAILBOX_LABEL=alpha-sh" in txt


def test_write_runtime_env_preserves_existing_keys_and_is_idempotent(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    (prof / ".env").write_text("ANTHROPIC_API_KEY=sk-secret\n", encoding="utf-8")
    env = {"HOME": str(tmp_path / "h")}
    enroll.write_runtime_env(prof, _state(board="b1"), env=env)
    enroll.write_runtime_env(prof, _state(board="b2"), env=env)
    txt = _read_env(prof)
    assert "ANTHROPIC_API_KEY=sk-secret" in txt   # preserved
    assert "MAILBOX_BOARD=b2" in txt              # updated in place
    assert "MAILBOX_BOARD=b1" not in txt
    assert txt.count("MAILBOX_BOARD=") == 1       # no duplicate lines
    assert txt.count("MAILBOX_LABEL=") == 1


def test_write_runtime_env_empty_board_writes_empty_value_no_error(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    enroll.write_runtime_env(prof, _state(board="", label=""), env={"HOME": str(tmp_path / "h")})
    txt = _read_env(prof)
    assert "MAILBOX_BOARD=" in txt  # present, empty value, no crash


def test_write_runtime_env_omits_home_socket_when_default(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    home = str(tmp_path / "h")
    default_home = str(Path(home) / ".claude" / "mailbox")
    st = _state(home=default_home, sock=str(Path(default_home) / "mailboxd.sock"))
    enroll.write_runtime_env(prof, st, env={"HOME": home})
    txt = _read_env(prof)
    assert "MAILBOX_HOME" not in txt
    assert "MAILBOX_SOCKET" not in txt


def test_write_runtime_env_includes_home_socket_when_custom(tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    st = _state(home="/custom/mb", sock="/custom/mb/x.sock")
    enroll.write_runtime_env(prof, st, env={"HOME": str(tmp_path / "h")})
    txt = _read_env(prof)
    assert "MAILBOX_HOME=/custom/mb" in txt
    assert "MAILBOX_SOCKET=/custom/mb/x.sock" in txt
