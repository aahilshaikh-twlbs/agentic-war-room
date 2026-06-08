"""T1.5 — runtime_state.save_state atomic JSON writer.

(Lives in runtime_state.py, not state.py: state.py is the pure wizard FSM and is
contractually forbidden from importing os — see test_security.)
"""
import json
import stat
from pathlib import Path

import pytest

from warroom_setup import runtime_state as state


def test_save_state_writes_atomically(tmp_path):
    target = tmp_path / "enroll.json"
    state.save_state(target, {"board": "shared", "n": 1})
    state.save_state(target, {"board": "shared", "n": 2})
    assert json.loads(target.read_text()) == {"board": "shared", "n": 2}
    leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], "no .tmp file should remain"


def test_save_state_sets_0600_mode(tmp_path):
    target = tmp_path / "enroll.json"
    state.save_state(target, {"x": 1})
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_save_state_survives_simulated_failure_mid_write(tmp_path, monkeypatch):
    target = tmp_path / "enroll.json"
    target.write_text(json.dumps({"original": True}))

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(state.json, "dump", boom)
    with pytest.raises(RuntimeError):
        state.save_state(target, {"new": True})
    # original file untouched
    assert json.loads(target.read_text()) == {"original": True}
    # tmp cleaned up
    leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_save_state_creates_parent_dir_if_missing(tmp_path):
    # documented behavior: do NOT create the parent; fail loudly.
    target = tmp_path / "nope" / "enroll.json"
    with pytest.raises((FileNotFoundError, OSError)):
        state.save_state(target, {"x": 1})
