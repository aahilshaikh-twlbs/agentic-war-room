"""Single-stream subprocess capture for the installer's execute phase.

Per §4: hermes writes errors to stdout, so we merge stderr INTO stdout at the
kernel level (``stderr=subprocess.STDOUT``) -- this preserves true interleaved
ordering without a second reader racing. One reader thread drains the merged
stream into a bounded ``deque`` (last 400 lines). stdin is closed
(``DEVNULL``) so no subprocess can block on a prompt. Timeouts escalate
SIGTERM -> wait 5s -> SIGKILL.

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

import collections
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, TextIO

_ERROR_PATTERNS = ("DistributionError", "ValueError", "error:")
_MAX_LINES = 400


@dataclass
class CommandResult:
    returncode: int
    lines: List[str]
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def tail(self, n: int = 20) -> List[str]:
        return self.lines[-n:]


def build_subprocess_env(
    base: Optional[dict] = None, *, strip_pythonpath: bool = True, extra: Optional[dict] = None
) -> dict:
    """Construct a child environment.

    Defaults strip ``PYTHONPATH`` (so a subprocess like ``hermes`` never picks
    up the installer's ``_substrate`` package) and force ``PYTHONUNBUFFERED=1``
    so progress streams live and merged ordering is exact.
    """
    env = dict(os.environ if base is None else base)
    if strip_pythonpath:
        env.pop("PYTHONPATH", None)
    env["PYTHONUNBUFFERED"] = "1"
    if extra:
        env.update(extra)
    return env


def run_capturing(
    cmd: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: float = 300.0,
    tee: Optional[TextIO] = None,
) -> CommandResult:
    """Run ``cmd``, capturing merged stdout+stderr. Never raises on child error.

    ``tee`` (e.g. ``sys.stderr``) echoes each captured line live -- this backs
    ``--verbose`` (K16). If ``env`` is None a clean env is built via
    :func:`build_subprocess_env`.
    """
    if env is None:
        env = build_subprocess_env()
    lines: "collections.deque[str]" = collections.deque(maxlen=_MAX_LINES)
    start = time.monotonic()
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        env=env,
        text=True,
        bufsize=1,
    )

    def _reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            if tee is not None:
                print(line, file=tee, flush=True)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    reader.join(timeout=5)
    duration = time.monotonic() - start
    rc = proc.returncode if proc.returncode is not None else -1
    return CommandResult(returncode=rc, lines=list(lines), duration_s=duration, timed_out=timed_out)


def tail_for_error_line(lines: Sequence[str], patterns: Sequence[str] = _ERROR_PATTERNS) -> Optional[str]:
    """Return the LAST line matching any error pattern, else None (§4)."""
    for line in reversed(list(lines)):
        for pat in patterns:
            if pat in line:
                return line
    return None
