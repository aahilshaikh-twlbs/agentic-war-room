"""Cross-agent enrollment: mailbox CLI discovery + idempotent first-run wiring.

Stdlib only, Python >=3.9. This module owns:
  - discovery of the mailbox CLI (precedence ladder below),
  - resolution of mailbox home / socket paths,
  - (T2) `bootstrap()` which persists the `mailbox:` config block + runtime
    state and installs the Claude Code SessionStart hook.

The mailbox package itself is treated as READ-ONLY; enroll never imports
`mailbox.client` (see enroll_status, T5). Status pings use raw stdlib sockets.
"""
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env(env):
    return env if env is not None else os.environ


def _home(env=None):
    env = _env(env)
    return Path(env.get("HOME") or os.path.expanduser("~"))


def resolve_mailbox_home(env=None):
    # type: (Optional[dict]) -> Path
    """MAILBOX_HOME env override, else `<home>/.claude/mailbox`."""
    env = _env(env)
    mh = (env.get("MAILBOX_HOME") or "").strip()
    if mh:
        return Path(mh)
    return _home(env) / ".claude" / "mailbox"


def resolve_socket_path(env=None):
    # type: (Optional[dict]) -> Path
    """MAILBOX_SOCKET env override, else `<mailbox_home>/mailboxd.sock`."""
    env = _env(env)
    sp = (env.get("MAILBOX_SOCKET") or "").strip()
    if sp:
        return Path(sp)
    return resolve_mailbox_home(env) / "mailboxd.sock"


def _is_executable_file(p):
    # type: (Path) -> bool
    try:
        return os.path.isfile(str(p)) and os.access(str(p), os.X_OK)
    except OSError:
        return False


def _dev_fallback(repo_search_start=None):
    # type: (Optional[Path]) -> Optional[Path]
    """Walk up from `repo_search_start` (default: this file) looking for
    `coordination/bin/mailbox`. This is ONLY meaningful when running from a repo
    checkout — installed Hermes profiles do not carry the coordination/ tree, so
    this branch yields nothing there (by design)."""
    start = Path(repo_search_start) if repo_search_start is not None else Path(__file__).resolve()
    for parent in [start, *start.parents]:
        cand = parent / "coordination" / "bin" / "mailbox"
        if _is_executable_file(cand):
            return cand
    return None


def discover_mailbox_cli(env=None, repo_search_start=None):
    # type: (Optional[dict], Optional[Path]) -> Optional[Path]
    """Locate an executable `mailbox` CLI. Precedence:
      1. `$MAILBOX_HOME/mailbox`         (explicit override)
      2. `<home>/.claude/mailbox/mailbox` (standard install location)
      3. `<repo>/coordination/bin/mailbox` (dev checkout fallback only)
      4. `shutil.which("mailbox")`        (whatever is on PATH)
    Returns the resolved Path or None.
    """
    env = _env(env)
    candidates = []
    mh = (env.get("MAILBOX_HOME") or "").strip()
    if mh:
        candidates.append(Path(mh) / "mailbox")
    candidates.append(_home(env) / ".claude" / "mailbox" / "mailbox")
    dev = _dev_fallback(repo_search_start)
    if dev is not None:
        candidates.append(dev)

    for c in candidates:
        if _is_executable_file(c):
            return c

    which = shutil.which("mailbox", path=env.get("PATH"))
    if which:
        return Path(which)
    return None


@dataclass
class EnrollState:
    board: str
    label: str
    cli_path: Optional[str]
    mailbox_home: str
    socket_path: str
    last_check_ts: float
    status: str  # "ok" | "cli-not-found" | "socket-unreachable" | "dry-run"

    def to_dict(self):
        # type: () -> dict
        return {
            "board": self.board,
            "label": self.label,
            "cli_path": self.cli_path,
            "mailbox_home": self.mailbox_home,
            "socket_path": self.socket_path,
            "last_check_ts": self.last_check_ts,
            "status": self.status,
        }
