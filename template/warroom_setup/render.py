"""Raw-mode termios renderer + numbered fallback for the toggle picker.
Stdlib only, Python >=3.9. Direct port of ccpkg/wizard.py (the renderer half).
"""
import select
import sys
from typing import List, Set

from .selectables import Stage
from .state import WizardState

_CLEAR = "\x1b[2J\x1b[H"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"


def _decode_key(seq):
    mapping = {
        "\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left",
        "\r": "enter", "\n": "enter", " ": "space", "\x1b": "esc", "\x03": "ctrl-c",
    }
    return mapping.get(seq, seq)


def _is_tty(stream):
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _render_numbered(state, out):
    stage = state.current_stage()
    out.write("\nStage %d/%d - %s\n" % (state.stage_index + 1, len(state.stages), stage.name))
    for i, e in enumerate(stage.entries, 1):
        mark = "x" if state.is_selected(e.id) else " "
        out.write("  %d. [%s] %-26s %s\n" % (i, mark, e.id, e.desc))
    out.write("Toggle # / 'a' all / 'n' none / Enter=continue: ")
    out.flush()


def _render_review_numbered(state, out):
    out.write("\nReview your selection:\n")
    for stage in state.stages:
        out.write("  %s:\n" % stage.name)
        chosen = [e for e in stage.entries if state.is_selected(e.id)]
        for e in chosen:
            out.write("    [x] %s\n" % e.id)
        if not chosen:
            out.write("    (none)\n")
    out.write("Enter=apply / 'b'=back: ")
    out.flush()


def _numbered_fallback(stages, preselected, in_stream, out_stream):
    state = WizardState(stages, preselected)
    while not state.is_done():
        if state.is_review():
            _render_review_numbered(state, out_stream)
            line = in_stream.readline()
            if line == "":
                state.confirm()
                break
            if line.strip().lower() == "b":
                state.prev_stage()
            else:
                state.confirm()
            continue
        _render_numbered(state, out_stream)
        line = in_stream.readline()
        if line == "":
            break
        cmd = line.strip().lower()
        if cmd == "":
            state.next_stage()
        elif cmd == "a":
            state.select_all()
        elif cmd == "n":
            state.select_none()
        elif cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(state.current_stage().entries):
                state.cursor = idx
                state.toggle()
    return state.selected_ids()


def _render_raw(state, out):
    stage = state.current_stage()
    out.write(_CLEAR)
    out.write("  warroom setup - select features      [stage %d/%d: %s]\r\n\r\n"
              % (state.stage_index + 1, len(state.stages), stage.name))
    out.write("   Space toggle - up/down move - Enter next - a all - n none - Esc back\r\n\r\n")
    for i, e in enumerate(stage.entries):
        pointer = ">" if i == state.cursor else " "
        mark = "x" if state.is_selected(e.id) else " "
        out.write(" %s [%s] %-26s %s\r\n" % (pointer, mark, e.id, e.desc))
    out.write("\r\n   [ Esc Back ]              [ Enter Continue -> ]\r\n")
    out.flush()


def _render_review_raw(state, out):
    out.write(_CLEAR)
    out.write("  warroom setup - review selection\r\n\r\n")
    for stage in state.stages:
        out.write("  %s:\r\n" % stage.name)
        chosen = [e for e in stage.entries if state.is_selected(e.id)]
        for e in chosen:
            out.write("    [x] %s\r\n" % e.id)
        if not chosen:
            out.write("    (none)\r\n")
    out.write("\r\n   [ Esc Back ]              [ Enter Apply ]\r\n")
    out.flush()


def _read_key(in_stream):
    ch = in_stream.read(1)
    if ch == "\x1b":
        rest = ""
        try:
            fd = in_stream.fileno()
            while len(rest) < 2:
                r, _, _ = select.select([fd], [], [], 0)
                if not r:
                    break
                nxt = in_stream.read(1)
                if nxt == "":
                    break
                rest += nxt
        except Exception:
            return "esc"
        return _decode_key(ch + rest) if rest else _decode_key(ch)
    return _decode_key(ch)


def _raw_mode_loop(stages, preselected, in_stream, out_stream):
    import termios
    import tty
    state = WizardState(stages, preselected)
    fd = in_stream.fileno()
    old = termios.tcgetattr(fd)
    out_stream.write(_HIDE_CURSOR)
    try:
        tty.setraw(fd)
        while not state.is_done():
            if state.is_review():
                _render_review_raw(state, out_stream)
            else:
                _render_raw(state, out_stream)
            key = _read_key(in_stream)
            if key == "" or key == "ctrl-c":
                raise KeyboardInterrupt
            if state.is_review():
                if key == "enter":
                    state.confirm()
                elif key in ("esc", "left"):
                    state.prev_stage()
                continue
            if key == "up":
                state.move(-1)
            elif key == "down":
                state.move(1)
            elif key == "space":
                state.toggle()
            elif key == "a":
                state.select_all()
            elif key == "n":
                state.select_none()
            elif key == "enter":
                state.next_stage()
            elif key in ("esc", "left"):
                state.prev_stage()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out_stream.write(_SHOW_CURSOR)
        out_stream.flush()
    return state.selected_ids()


def run_wizard(stages, preselected, in_stream=None, out_stream=None):
    # type: (List[Stage], Set[str], object, object) -> Set[str]
    in_stream = in_stream if in_stream is not None else sys.stdin
    out_stream = out_stream if out_stream is not None else sys.stdout
    if not stages:
        return set(preselected)
    if _is_tty(in_stream) and _is_tty(out_stream):
        try:
            return _raw_mode_loop(stages, preselected, in_stream, out_stream)
        except KeyboardInterrupt:
            raise
        except Exception:
            return _numbered_fallback(stages, preselected, in_stream, out_stream)
    return _numbered_fallback(stages, preselected, in_stream, out_stream)
