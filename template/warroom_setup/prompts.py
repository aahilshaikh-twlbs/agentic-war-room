"""Line + secret text prompts. Stdlib only, Python >=3.9.

Streams are injectable so tests run without a TTY. On a real interactive stdin,
secret fields use getpass (no echo); otherwise they read a normal line.
"""
import sys
from typing import Dict, List, Set

from .selectables import TextField


def _read_line(in_stream):
    line = in_stream.readline()
    if line == "":          # EOF
        return None
    return line.rstrip("\n")


def _prompt_once(field, in_stream, out_stream):
    label = "%s: " % field.prompt
    use_getpass = field.secret and _is_real_tty(in_stream)
    if use_getpass:
        import getpass
        try:
            return getpass.getpass(label)
        except Exception:
            out_stream.write(label)
            out_stream.flush()
            return _read_line(in_stream)
    out_stream.write(label)
    out_stream.flush()
    return _read_line(in_stream)


def _is_real_tty(stream):
    try:
        return bool(stream.isatty()) and stream is sys.stdin
    except Exception:
        return False


def collect(fields, selected_toggles, in_stream=None, out_stream=None):
    # type: (List[TextField], Set[str], object, object) -> Dict[str, str]
    in_stream = in_stream if in_stream is not None else sys.stdin
    out_stream = out_stream if out_stream is not None else sys.stdout
    values = {}  # type: Dict[str, str]
    for field in fields:
        if field.enable_if and field.enable_if not in selected_toggles:
            continue
        while True:
            val = _prompt_once(field, in_stream, out_stream)
            if val is None:                 # EOF: stop asking
                if field.required:
                    out_stream.write("  (required field left empty at EOF)\n")
                return values
            val = val.strip()
            if val == "" and field.required:
                out_stream.write("  required - please enter a value\n")
                continue
            values[field.id] = val
            break
    return values
