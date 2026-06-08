"""Cross-agent enrollment: mailbox CLI discovery + idempotent first-run wiring.

Stdlib only, Python >=3.9. This module owns:
  - discovery of the mailbox CLI (precedence ladder below),
  - resolution of mailbox home / socket paths,
  - (T2) `bootstrap()` which persists the `mailbox:` config block + runtime
    state and installs the Claude Code SessionStart hook.

The mailbox package itself is treated as READ-ONLY; enroll never imports
`mailbox.client` (see enroll_status, T5). Status pings use raw stdlib sockets.
"""
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import runtime_state


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


def _claude_settings_path(env=None):
    # type: (Optional[dict]) -> Path
    env = _env(env)
    base = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
    root = Path(base) if base else (_home(env) / ".claude")
    return root / "settings.json"


def _atomic_json_write(path, data):
    # type: (Path, dict) -> None
    path = Path(path)
    fd = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(path.parent),
        prefix=path.name + ".", suffix=".tmp", delete=False,
    )
    tmp_name = fd.name
    try:
        with fd:
            json.dump(data, fd, indent=2)
            fd.flush()
            os.fsync(fd.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _install_claude_code_hook(profile_root, env=None):
    # type: (Path, Optional[dict]) -> None
    """Register `<profile>/hooks/session_start.py` as a Claude Code SessionStart
    hook at index 0 of `hooks.SessionStart` in settings.json. Idempotent: keyed
    on the absolute script path appearing in any existing command. Creates the
    settings file if absent. The settings path honors CLAUDE_CONFIG_DIR (env) so
    tests never touch the operator's real ~/.claude/settings.json."""
    profile_root = Path(profile_root)
    settings = _claude_settings_path(env)
    hook_script = str(profile_root / "hooks" / "session_start.py")
    command = '[ -f "%s" ] && python3 "%s" || true' % (hook_script, hook_script)

    if settings.exists():
        data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    else:
        settings.parent.mkdir(parents=True, exist_ok=True)
        data = {}
    if not isinstance(data, dict):
        data = {}
    hooks = data.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    for entry in session_start:
        for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
            if hook_script in (h.get("command") or ""):
                return  # already registered — idempotent no-op

    session_start.insert(0, {"hooks": [{"type": "command", "command": command}]})
    _atomic_json_write(settings, data)


def _append_log(log_path, state):
    # type: (Path, EnrollState) -> None
    ts = datetime.fromtimestamp(state.last_check_ts, tz=timezone.utc).isoformat()
    line = ("%s status=%s board=%s label=%s cli=%s home=%s socket=%s\n" % (
        ts, state.status, state.board, state.label,
        state.cli_path, state.mailbox_home, state.socket_path,
    ))
    with open(str(log_path), "a", encoding="utf-8") as fh:
        fh.write(line)


def bootstrap(profile_root, board, label, dry_run=False, env=None):
    # type: (Path, str, str, bool, Optional[dict]) -> EnrollState
    """Idempotent first-run wiring. Discovers the mailbox CLI, writes the
    `mailbox:` config block, persists runtime state + a log line, and (when the
    CLI is present) installs the Claude Code SessionStart hook. Fail-warn: a
    missing CLI yields status="cli-not-found" without raising. dry_run performs
    NO writes and returns status="dry-run".
    """
    env = _env(env)
    profile_root = Path(profile_root)
    # Anchor the dev-fallback walk at the profile (its own tree), not at this
    # module's location: an installed profile carries no coordination/, while a
    # dev checkout's profile lives under the repo so the walk still finds it.
    cli = discover_mailbox_cli(env=env, repo_search_start=profile_root)
    home = resolve_mailbox_home(env)
    sock = resolve_socket_path(env)

    if dry_run:
        status = "dry-run"
    elif cli is None:
        status = "cli-not-found"
    else:
        status = "ok"

    state = EnrollState(
        board=(board or "default"),
        label=(label or ""),
        cli_path=(str(cli) if cli is not None else None),
        mailbox_home=str(home),
        socket_path=str(sock),
        last_check_ts=time.time(),
        status=status,
    )

    if dry_run:
        return state

    # mailbox: block (atomic). Lazy `from . import setup` avoids an import cycle
    # and the no-cross-import lint (which forbids the dotted-import form here).
    from . import setup as _setup
    _setup.patch_mailbox_block(
        profile_root, board=state.board, label=state.label,
        mailbox_home=state.mailbox_home, socket_path=state.socket_path,
    )

    local = profile_root / "local"
    local.mkdir(parents=True, exist_ok=True)
    runtime_state.save_state(local / "warroom-enroll.json", state.to_dict())
    _append_log(local / "warroom-enroll.log", state)

    if cli is not None:
        _install_claude_code_hook(profile_root, env=env)

    return state
