"""T3 — template SessionStart hook: re-export mailbox routing from config.yaml.

The hook is copied into each tmp profile and imported from there so its
_profile_root() (Path(__file__).parents[1]) resolves to the tmp profile.
"""
import importlib.util
import shutil
from pathlib import Path

from warroom_setup import setup

HOOK_SRC = Path(__file__).resolve().parents[1] / "hooks" / "session_start.py"
_counter = [0]


def _load_hook(prof):
    (prof / "hooks").mkdir(parents=True, exist_ok=True)
    dst = prof / "hooks" / "session_start.py"
    shutil.copy2(HOOK_SRC, dst)
    _counter[0] += 1
    name = "wr_session_start_%d" % _counter[0]
    spec = importlib.util.spec_from_file_location(name, str(dst))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _profile(tmp_path):
    prof = tmp_path / "profiles" / "alpha-sh"
    (prof / "hooks").mkdir(parents=True)
    (prof / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    return prof


def _default_home(home):
    return str(Path(home) / ".claude" / "mailbox")


def test_session_start_writes_exports_to_claude_env_file(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    setup.patch_mailbox_block(prof, board="shared", label="alpha-sh")
    home = str(tmp_path / "home")
    monkeypatch.setenv("HOME", home)
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    assert _load_hook(prof).main() == 0
    txt = env_file.read_text()
    assert "export MAILBOX_BOARD=shared" in txt
    assert "export MAILBOX_LABEL=alpha-sh" in txt


def test_session_start_is_idempotent(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    setup.patch_mailbox_block(prof, board="shared", label="alpha-sh")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    hook = _load_hook(prof)
    hook.main()
    hook.main()
    assert env_file.read_text().count("export MAILBOX_BOARD=shared") == 1


def test_session_start_omits_mailbox_home_when_default(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    home = str(tmp_path / "home")
    dh = _default_home(home)
    setup.patch_mailbox_block(prof, board="shared", label="a", mailbox_home=dh,
                              socket_path=str(Path(dh) / "mailboxd.sock"))
    monkeypatch.setenv("HOME", home)
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    _load_hook(prof).main()
    assert "MAILBOX_HOME" not in env_file.read_text()


def test_session_start_includes_mailbox_home_when_custom(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    setup.patch_mailbox_block(prof, board="shared", label="a",
                              mailbox_home="/custom/mb")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    _load_hook(prof).main()
    assert "export MAILBOX_HOME=/custom/mb" in env_file.read_text()


def test_session_start_omits_mailbox_socket_when_default(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    home = str(tmp_path / "home")
    dh = _default_home(home)
    setup.patch_mailbox_block(prof, board="shared", label="a", mailbox_home=dh,
                              socket_path=str(Path(dh) / "mailboxd.sock"))
    monkeypatch.setenv("HOME", home)
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    _load_hook(prof).main()
    assert "MAILBOX_SOCKET" not in env_file.read_text()


def test_session_start_fails_open_on_missing_config(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    (prof / "config.yaml").unlink()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(tmp_path / "env.sh"))
    assert _load_hook(prof).main() == 0


def test_session_start_fails_open_on_missing_env_file_var(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    setup.patch_mailbox_block(prof, board="shared", label="a")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    assert _load_hook(prof).main() == 0
    # sidecar still written
    assert (prof / "local" / "runtime_env.json").is_file()


def test_session_start_logs_warning_when_board_empty(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    # patch_mailbox_block coerces "" -> "default", so write an empty-board block
    # by hand to exercise the fail-closed-but-exit-0 warning path.
    (prof / "config.yaml").write_text(
        "model: {}\n"
        + setup._MB_BEGIN + "\nmailbox:\n  board: \"\"\n  label: a\n"
        "  mailbox_home: \"\"\n  socket_path: \"\"\n" + setup._MB_END + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(tmp_path / "env.sh"))
    _load_hook(prof).main()
    log = (prof / "local" / "warroom-enroll.log").read_text()
    assert "WARN" in log and "board empty" in log


def test_session_start_writes_label_from_config(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    setup.patch_mailbox_block(prof, board="shared", label="beta-sh")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    env_file = tmp_path / "env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    _load_hook(prof).main()
    assert "export MAILBOX_LABEL=beta-sh" in env_file.read_text()
