"""Installer-local raw-tty masked secret entry (A7/F7/F19).

~30 LoC of raw-mode input that echoes one asterisk per character to stdout, so
secrets integrate with the TUI screen buffer instead of the opaque, non-echoing
``getpass`` (which also can't share the renderer's terminal state). On a
non-TTY stdin (tests/CI without ``--headless``) it falls back to a cooked
line read so callers still work.

A module-global captures the last raw-mode terminal attrs so a SIGINT handler
(installed by the TUI in T5) can :func:`emergency_restore` the terminal.

Stdlib only, Python >=3.9, POSIX (termios/tty).
"""
from __future__ import annotations

import os
import sys
from typing import Optional, TextIO

try:  # POSIX only; precheck hard-fails on platforms without these.
    import termios
    import tty
except ImportError:  # pragma: no cover - guarded by T0 precheck
    termios = None  # type: ignore
    tty = None  # type: ignore

# (fd, saved_attrs) captured at raw-mode entry for emergency restore (C11/F6).
_LAST_TTY: Optional[tuple] = None

_SHOW_CURSOR = "\x1b[?25h"


def emergency_restore() -> None:
    """Re-show the cursor and restore the last raw-mode terminal attrs.

    Safe to call from a signal handler or atexit; a no-op if nothing was put
    into raw mode.
    """
    global _LAST_TTY
    try:
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()
    except Exception:  # pragma: no cover - defensive
        pass
    if _LAST_TTY and termios is not None:
        fd, attrs = _LAST_TTY
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        except Exception:  # pragma: no cover - defensive
            pass
        _LAST_TTY = None


def prompt_secret(
    label: str,
    *,
    infile: Optional[TextIO] = None,
    outfile: Optional[TextIO] = None,
    mask: str = "*",
) -> str:
    """Prompt for a secret, echoing ``mask`` per char. Returns the entered text.

    Raises ``KeyboardInterrupt`` on Ctrl-C. On EOF (Ctrl-D / closed stdin)
    returns whatever was typed so far.
    """
    global _LAST_TTY
    infile = infile if infile is not None else sys.stdin
    outfile = outfile if outfile is not None else sys.stdout

    try:
        fd = infile.fileno()
    except (AttributeError, OSError, ValueError):
        fd = -1

    if fd < 0 or termios is None or not os.isatty(fd):
        # Cooked fallback: no masking possible without a TTY.
        outfile.write("%s: " % label)
        outfile.flush()
        line = infile.readline()
        return line.rstrip("\r\n")

    outfile.write("%s: " % label)
    outfile.flush()
    old = termios.tcgetattr(fd)
    _LAST_TTY = (fd, old)
    chars = []
    try:
        # TCSANOW (not setraw's default TCSAFLUSH) so typed-ahead input is
        # preserved, not discarded. TCSADRAIN can drop queued input on a pty
        # slave (observed on macOS); TCSANOW applies raw mode immediately and
        # keeps the input queue intact.
        tty.setraw(fd, termios.TCSANOW)
        while True:
            ch = os.read(fd, 1)
            if not ch or ch == b"\x04":  # EOF / Ctrl-D
                break
            if ch in (b"\r", b"\n"):
                break
            if ch == b"\x03":  # Ctrl-C
                raise KeyboardInterrupt
            if ch in (b"\x7f", b"\x08"):  # backspace / delete
                if chars:
                    chars.pop()
                    outfile.write("\b \b")
                    outfile.flush()
                continue
            dec = ch.decode("utf-8", "ignore")
            if dec and dec.isprintable():
                chars.append(dec)
                outfile.write(mask)
                outfile.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        _LAST_TTY = None
        outfile.write("\n")
        outfile.flush()
    return "".join(chars)
