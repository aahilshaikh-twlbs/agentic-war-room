"""Atomic runtime-state persistence (cross-agent enrollment state, T1.5).

Stdlib only, Python >=3.9.

NOTE: this lives in its own module rather than `state.py` because `state.py` is
the PURE wizard FSM and is contractually forbidden from importing os/io
(test_security.test_state_module_is_pure_no_io). The plan named `state.save_state`;
the purity invariant forces the split. Surfaced to team-lead.
"""
import json
import os
import tempfile
from pathlib import Path


def save_state(path, payload, mode=0o600):
    # type: (Path, dict, int) -> None
    """Atomically write `payload` as JSON to `path` with the given file mode.

    Mirrors setup._secure_file's chmod-after-rename intent: write to a temp file
    in the SAME directory (so os.replace is atomic on one fs), fsync, chmod, then
    os.replace over the target. Last-writer-wins. The parent directory must
    already exist — we fail loudly rather than create it (the caller owns layout).
    Best-effort cleanup of the temp file on error.
    """
    path = Path(path)
    fd = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(path.parent),
        prefix=path.name + ".", suffix=".tmp", delete=False,
    )
    tmp_name = fd.name
    try:
        with fd:
            json.dump(payload, fd, indent=2, sort_keys=True)
            fd.flush()
            os.fsync(fd.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_state(path):
    # type: (Path) -> dict
    """Read JSON state from `path`. Raises FileNotFoundError if absent."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
