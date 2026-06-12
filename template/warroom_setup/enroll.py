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
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import daemon_probe, runtime_state


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
    # Federation (optional): the home board's parent link, recorded
    # engine-side at bootstrap. parent_status: None (no parent requested) |
    # "ok" | "parent-failed" | "cli-not-found".
    parent: Optional[str] = None
    parent_status: Optional[str] = None

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
            "parent": self.parent,
            "parent_status": self.parent_status,
        }


def _runtime_env_values(state, env=None):
    # type: (EnrollState, Optional[dict]) -> dict
    """The MAILBOX_* vars to deliver via <profile>/.env. Always BOARD + LABEL;
    HOME/SOCKET only when non-default (F15) so default profiles share a daemon."""
    values = {
        "MAILBOX_BOARD": state.board or "",
        "MAILBOX_LABEL": state.label or "",
    }
    # Compute the runtime defaults from the same env the hook will see.
    e = _env(env)
    dflt_home = str((_home(e) / ".claude" / "mailbox"))
    if state.mailbox_home and state.mailbox_home != dflt_home:
        values["MAILBOX_HOME"] = state.mailbox_home
    effective_home = state.mailbox_home or dflt_home
    dflt_sock = str(Path(effective_home) / "mailboxd.sock")
    if state.socket_path and state.socket_path != dflt_sock:
        values["MAILBOX_SOCKET"] = state.socket_path
    return values


def write_runtime_env(profile_root, state, env=None):
    # type: (Path, EnrollState, Optional[dict]) -> None
    """Deliver cross-agent routing to mailbox's hook via <profile>/.env.

    Revised T3 (per lead): Hermes loads <profile>/.env into the gateway
    os.environ, which propagates to the Claude Code subprocess and thus to
    mailbox's own SessionStart hook (which reads MAILBOX_BOARD / MAILBOX_LABEL
    from os.environ). No template-side hook, no settings.json edit, no touching
    mailbox's registration. config.yaml's mailbox: block stays the canonical
    human-readable source; .env is the runtime delivery channel. Uses shared-core
    write_env, whose merge semantics preserve existing keys (e.g. tokens)."""
    # Lazy `from . import setup` avoids an import cycle and the no-cross-import
    # lint (which forbids the dotted-import form here).
    from . import setup as _setup
    _setup.write_env(profile_root, _runtime_env_values(state, env), filename=".env")


def _append_log(log_path, state):
    # type: (Path, EnrollState) -> None
    ts = datetime.fromtimestamp(state.last_check_ts, tz=timezone.utc).isoformat()
    line = ("%s status=%s board=%s label=%s cli=%s home=%s socket=%s\n" % (
        ts, state.status, state.board, state.label,
        state.cli_path, state.mailbox_home, state.socket_path,
    ))
    with open(str(log_path), "a", encoding="utf-8") as fh:
        fh.write(line)


def _ensure_parent_link(cli, board, parent, env=None):
    # type: (Path, str, str, Optional[dict]) -> str
    """Best-effort: ask the mailbox engine (via the discovered CLI — enroll
    NEVER imports mailbox.client) to mint the home board and record its
    parent link: `mailbox create-board <board> --parent <parent>`. The
    engine requires the parent to already exist (operators build top-down).
    Returns "ok" | "parent-failed"; never raises — federation is additive
    and enrollment stays fail-warn."""
    e = _env(env)
    sub_env = dict(os.environ)
    for k in ("MAILBOX_HOME", "MAILBOX_SOCKET"):
        v = (e.get(k) or "").strip()
        if v:
            sub_env[k] = v
    try:
        proc = subprocess.run(
            [str(cli), "create-board", board, "--parent", parent],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=sub_env, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return "parent-failed"
    return "ok" if proc.returncode == 0 else "parent-failed"


def bootstrap(profile_root, board, label, dry_run=False, env=None, parent=None):
    # type: (Path, str, str, bool, Optional[dict], Optional[str]) -> EnrollState
    """Idempotent first-run wiring. Discovers the mailbox CLI, writes the
    `mailbox:` config block, delivers MAILBOX_BOARD/LABEL to <profile>/.env (the
    runtime channel mailbox's own SessionStart hook reads), and persists runtime
    state + a log line. Fail-warn: a missing CLI yields status="cli-not-found"
    without raising (routing is still written so it activates once the CLI lands).
    dry_run performs NO writes and returns status="dry-run".

    Revised T3 (per lead): no template-side SessionStart hook and no
    ~/.claude/settings.json edit — Hermes loads <profile>/.env into the
    environment that reaches mailbox's hook.
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
        parent=(parent or None),
        parent_status=None,
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

    # Deliver routing to mailbox's hook via <profile>/.env (runtime channel).
    write_runtime_env(profile_root, state, env=env)

    # Federation (optional): record the home board's parent link engine-side.
    # `.env` stays single-board; the engine resolves federation at read time.
    if state.parent:
        if cli is None:
            state.parent_status = "cli-not-found"
        else:
            state.parent_status = _ensure_parent_link(
                cli, state.board, state.parent, env=env)

    local = profile_root / "local"
    local.mkdir(parents=True, exist_ok=True)
    runtime_state.save_state(local / "warroom-enroll.json", state.to_dict())
    _append_log(local / "warroom-enroll.log", state)

    return state


def enroll_status(profile_root, env=None):
    # type: (Path, Optional[dict]) -> dict
    """Read local/warroom-enroll.json and ping the recorded socket. Raises
    FileNotFoundError when the profile was never enrolled. Returns the state dict
    augmented with `daemon_reachable`. The ping is a stdlib AF_UNIX connect
    (daemon_probe) — NEVER imports mailbox.client, NEVER auto-spawns."""
    profile_root = Path(profile_root)
    data = runtime_state.load_state(profile_root / "local" / "warroom-enroll.json")
    sock_path = data.get("socket_path") or str(resolve_socket_path(env))
    data["daemon_reachable"] = daemon_probe.ping_socket(sock_path)
    return data
