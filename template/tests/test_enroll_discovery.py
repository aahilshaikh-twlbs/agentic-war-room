"""T1 — mailbox CLI discovery + home/socket resolution."""
import os
import shutil
import stat
from pathlib import Path

from warroom_setup import enroll

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fake_mailbox_bin.sh"


def _install_fake(dst):
    # type: (Path) -> Path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE, dst)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def test_discover_prefers_mailbox_home_env_when_executable(tmp_path):
    mh = tmp_path / "mhome"
    _install_fake(mh / "mailbox")
    # also seed the claude-default so we prove precedence, not just presence
    _install_fake(tmp_path / "home" / ".claude" / "mailbox" / "mailbox")
    env = {"MAILBOX_HOME": str(mh), "HOME": str(tmp_path / "home")}
    got = enroll.discover_mailbox_cli(env=env, repo_search_start=tmp_path / "empty")
    assert got == mh / "mailbox"


def test_discover_falls_back_to_claude_default_when_env_absent(tmp_path):
    home = tmp_path / "home"
    claude_bin = _install_fake(home / ".claude" / "mailbox" / "mailbox")
    env = {"HOME": str(home)}  # no MAILBOX_HOME
    got = enroll.discover_mailbox_cli(env=env, repo_search_start=tmp_path / "empty")
    assert got == claude_bin


def test_discover_dev_fallback_when_running_from_repo_checkout(tmp_path):
    repo = tmp_path / "checkout"
    dev_bin = _install_fake(repo / "coordination" / "bin" / "mailbox")
    home = tmp_path / "home"  # empty, no .claude/mailbox
    env = {"HOME": str(home), "PATH": ""}
    start = repo / "template" / "warroom_setup"
    start.mkdir(parents=True)
    got = enroll.discover_mailbox_cli(env=env, repo_search_start=start)
    assert got == dev_bin


def test_discover_returns_none_when_nothing_present(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": ""}
    got = enroll.discover_mailbox_cli(env=env, repo_search_start=tmp_path / "empty")
    assert got is None


def test_resolve_socket_path_honors_env_override(tmp_path):
    sock = tmp_path / "custom.sock"
    assert enroll.resolve_socket_path(env={"MAILBOX_SOCKET": str(sock)}) == sock
    # default derives from mailbox home
    env = {"HOME": str(tmp_path / "h")}
    assert enroll.resolve_socket_path(env=env) == tmp_path / "h" / ".claude" / "mailbox" / "mailboxd.sock"
    # MAILBOX_HOME flows into the default socket location
    env2 = {"MAILBOX_HOME": str(tmp_path / "mh")}
    assert enroll.resolve_socket_path(env=env2) == tmp_path / "mh" / "mailboxd.sock"
