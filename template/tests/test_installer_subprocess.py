"""T3 -- subprocess runner, progress renderer, masked prompt."""
import io
import os
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import masked_prompt  # noqa: E402
import progress  # noqa: E402
import subprocess_runner as sr  # noqa: E402


# --------------------------------------------------------------------------- #
# subprocess_runner
# --------------------------------------------------------------------------- #
def test_merges_streams_in_kernel_order():
    code = (
        "import sys\n"
        "print('out1')\n"
        "sys.stderr.write('err1\\n'); sys.stderr.flush()\n"
        "print('out2')\n"
    )
    res = sr.run_capturing([sys.executable, "-c", code], timeout=30)
    assert res.ok
    assert res.lines == ["out1", "err1", "out2"]


def test_returns_nonzero_on_failure():
    res = sr.run_capturing([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30)
    assert res.returncode == 3
    assert res.ok is False


def test_terminates_on_timeout():
    res = sr.run_capturing(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5
    )
    assert res.timed_out is True
    assert res.ok is False
    assert res.duration_s < 15  # SIGTERM/SIGKILL escalation, not a 30s hang


def test_strips_pythonpath():
    res = sr.run_capturing(
        [sys.executable, "-c", "import os; print(os.environ.get('PYTHONPATH', '<none>'))"],
        timeout=30,
    )
    assert res.lines == ["<none>"]
    env = sr.build_subprocess_env(base={"PYTHONPATH": "/x", "FOO": "1"})
    assert "PYTHONPATH" not in env
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["FOO"] == "1"


def test_tail_finds_error():
    lines = ["starting", "ValueError: bad input", "more", "error: second"]
    # returns the LAST matching line
    assert sr.tail_for_error_line(lines) == "error: second"
    assert sr.tail_for_error_line(["x", "DistributionError: nope"]) == "DistributionError: nope"


def test_tail_returns_none_when_clean():
    assert sr.tail_for_error_line(["all", "fine", "here"]) is None


# --------------------------------------------------------------------------- #
# progress
# --------------------------------------------------------------------------- #
def test_stage_runner_ok():
    buf = io.StringIO()
    clock = iter([0.0, 2.3]).__next__
    with progress.StageRunner(1, 5, "hermes profile install", stream=buf, clock=clock) as st:
        st.ok()
    out = buf.getvalue()
    assert "[1/5]" in out
    assert "hermes profile install" in out
    assert "ok" in out
    assert "(2.3s)" in out


def test_stage_runner_fail():
    buf = io.StringIO()
    with progress.StageRunner(4, 5, "plugin enable", stream=buf) as st:
        st.fail("nonzero exit")
    out = buf.getvalue()
    assert "fail" in out
    assert "nonzero exit" in out
    # auto-fail on exception
    buf2 = io.StringIO()
    with pytest.raises(RuntimeError):
        with progress.StageRunner(2, 5, "boom", stream=buf2):
            raise RuntimeError("kaboom")
    assert "fail" in buf2.getvalue()


# --------------------------------------------------------------------------- #
# masked_prompt (raw-tty via a pty pair)
# --------------------------------------------------------------------------- #
# NOTE: switching a pty slave from canonical -> raw discards any *unread*
# canonical input buffer (observed on macOS), so we must feed the input from a
# thread AFTER the prompt enters raw mode -- which is exactly how real typing
# arrives anyway.
def _pty_infile():
    import pty
    master, slave = pty.openpty()
    infile = os.fdopen(slave, "rb", buffering=0)
    return master, slave, infile


def _feed_after(master, data, delay=0.1):
    import threading
    import time

    def writer():
        time.sleep(delay)
        os.write(master, data)

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    return t


def test_masked_prompt_returns_value():
    master, slave, infile = _pty_infile()
    try:
        _feed_after(master, b"sk-ant-secretvalue\n")
        out = io.StringIO()
        val = masked_prompt.prompt_secret("Anthropic key", infile=infile, outfile=out)
        assert val == "sk-ant-secretvalue"
        assert "*" in out.getvalue()  # masked, not echoed
        assert "sk-ant" not in out.getvalue()
    finally:
        infile.close()
        os.close(master)


def test_masked_prompt_restores_terminal():
    import termios
    master, slave, infile = _pty_infile()
    try:
        before = termios.tcgetattr(slave)
        _feed_after(master, b"hunter2\n")
        masked_prompt.prompt_secret("Token", infile=infile, outfile=io.StringIO())
        after = termios.tcgetattr(slave)
        # macOS sets the transient PENDIN (0x20000000) lflag bit during a
        # canonical->raw->canonical round-trip; it is not part of the terminal
        # config. The meaningful flags (low bits, incl. the ECHO/ICANON that raw
        # mode toggled) must be restored exactly, and all other fields unchanged.
        assert after[:3] == before[:3]
        assert after[4:] == before[4:]
        assert (after[3] & 0xFFFF) == (before[3] & 0xFFFF)
        assert after[3] & termios.ICANON and after[3] & termios.ECHO
        # module global cleared after a clean prompt
        assert masked_prompt._LAST_TTY is None
    finally:
        infile.close()
        os.close(master)


def test_masked_prompt_cooked_fallback_for_non_tty():
    # Non-TTY infile -> cooked line read, still returns the value.
    val = masked_prompt.prompt_secret(
        "Key", infile=io.StringIO("plain-line\n"), outfile=io.StringIO()
    )
    assert val == "plain-line"
