#!/usr/bin/env python3
"""War-room SessionStart hook (Claude Code harness hook). Fail-OPEN.

Registered into ~/.claude/settings.json by enroll.bootstrap. Reads the
`mailbox:` block from <profile>/config.yaml and re-exports the cross-agent
routing into the session environment so mailbox's own SessionStart hook joins
the operator-chosen board (not just the cwd-derived one).

T0 pre-flight #3 result was NO: a SessionStart hook's $CLAUDE_ENV_FILE writes are
applied to *subsequent Bash commands* only, AFTER all SessionStart hooks run in
parallel — they are NOT visible to a sibling SessionStart hook's os.environ in
the same event. So we cannot seed env for mailbox's *sibling* hook via the env
file alone. This hook therefore ALSO writes a sidecar `<profile>/local/
runtime_env.json` that the deployment wrapper (or a future mailbox PR) consumes
to populate mailbox's hook env before it joins. See template/docs/
runtime-preflight.md and README "Cross-agent coordination" for the mechanism and
its open production wiring item.

This script is intentionally self-contained (no warroom_setup import): it runs
standalone via `python3 <profile>/hooks/session_start.py`.
"""
import json
import os
import re
import sys
from pathlib import Path

_MB_BEGIN = "# >>> warroom-mailbox >>>"
_MB_END = "# <<< warroom-mailbox <<<"


def _profile_root():
    # <profile>/hooks/session_start.py -> profile root is one up.
    return Path(__file__).resolve().parents[1]


def _read_mailbox_block(config_path):
    """Extract the sentinel-anchored `mailbox:` block into a flat dict."""
    try:
        text = Path(config_path).read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.search(
        r"^%s$(.*?)^%s$" % (re.escape(_MB_BEGIN), re.escape(_MB_END)),
        text, re.MULTILINE | re.DOTALL,
    )
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s{2}(\w+):\s*(.*)$", line)
        if not mm:
            continue
        val = mm.group(2).strip()
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        out[mm.group(1)] = val
    return out


def _default_home():
    home = os.environ.get("HOME") or os.path.expanduser("~")
    return str(Path(home) / ".claude" / "mailbox")


def _compute_exports(block):
    """Always export BOARD + LABEL; export HOME/SOCKET only when non-empty AND
    different from the runtime defaults (F15)."""
    exports = {
        "MAILBOX_BOARD": block.get("board", "") or "",
        "MAILBOX_LABEL": block.get("label", "") or "",
    }
    home = (block.get("mailbox_home", "") or "").strip()
    default_home = _default_home()
    if home and home != default_home:
        exports["MAILBOX_HOME"] = home
    effective_home = home or default_home
    sock = (block.get("socket_path", "") or "").strip()
    default_sock = str(Path(effective_home) / "mailboxd.sock")
    if sock and sock != default_sock:
        exports["MAILBOX_SOCKET"] = sock
    return exports


def _append_exports(env_file, values):
    """Append `export K=V` lines to env_file, deduped against existing lines."""
    p = Path(env_file)
    have = set(p.read_text(encoding="utf-8").splitlines()) if p.exists() else set()
    new = []
    for k, v in values.items():
        line = "export %s=%s" % (k, v)
        if line not in have:
            new.append(line)
    if new:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(new) + "\n")


def _log(local_dir, message):
    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        with open(str(local_dir / "warroom-enroll.log"), "a", encoding="utf-8") as fh:
            fh.write("event=session_start_hook %s\n" % message)
    except OSError:
        pass


def main():
    try:
        profile = _profile_root()
        local = profile / "local"
        block = _read_mailbox_block(profile / "config.yaml")
        exports = _compute_exports(block)

        # Sidecar (audit/debug + deployment-wrapper source).
        try:
            local.mkdir(parents=True, exist_ok=True)
            (local / "runtime_env.json").write_text(
                json.dumps(exports, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            pass

        env_file = os.environ.get("CLAUDE_ENV_FILE")
        if env_file:
            _append_exports(env_file, exports)

        if not exports.get("MAILBOX_BOARD"):
            # fail-CLOSED semantics = still exit 0, but log loudly.
            _log(local, "WARN: mailbox.board empty; cross-agent routing will use "
                        "cwd-derived board only")
        else:
            _log(local, "board=%s label=%s" % (
                exports.get("MAILBOX_BOARD"), exports.get("MAILBOX_LABEL", "")))
        return 0
    except Exception:
        return 0  # fail-open: never block session start


if __name__ == "__main__":
    sys.exit(main())
