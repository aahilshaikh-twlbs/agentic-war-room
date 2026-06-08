"""T2.5 — anchored-regex sentinel block replacer + atomic config writes."""
from pathlib import Path

import pytest

from warroom_setup import setup

WR_B, WR_E = setup._WR_BEGIN, setup._WR_END
MB_B, MB_E = setup._MB_BEGIN, setup._MB_END


def test_replace_preserves_unrelated_blocks():
    text = "\n".join([
        "top: 1",
        WR_B, "war_room:", "  board: a", WR_E,
        "middle: 2",
        MB_B, "mailbox:", "  board: a", MB_E,
        "bottom: 3",
    ]) + "\n"
    new_wr = "\n".join([WR_B, "war_room:", "  board: REPLACED", WR_E])
    out = setup._replace_sentinel_block(text, WR_B, WR_E, new_wr)
    assert "board: REPLACED" in out
    # the mailbox block + surrounding lines are untouched
    assert MB_B in out and "mailbox:" in out
    assert "top: 1" in out and "middle: 2" in out and "bottom: 3" in out
    assert out.count(WR_B) == 1 and out.count(MB_B) == 1


def test_replace_handles_sentinel_string_in_comment_body():
    # A decoy line that contains the sentinel text but is NOT a bare line (indented).
    decoy = "  " + MB_B  # leading spaces -> not anchored ^...$
    text = "\n".join([
        WR_B, "war_room:", "  note: " + decoy.strip(), WR_E,
    ]) + "\n"
    # Replacing the mailbox block must NOT match the decoy inside the war_room body.
    new_mb = "\n".join([MB_B, "mailbox:", "  board: x", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb)
    # No real mailbox sentinel present -> appended, decoy left intact inside war_room.
    assert out.count(MB_E) == 1  # only the appended one
    assert "note: " + MB_B in out  # decoy preserved verbatim
    assert "mailbox:" in out


def test_replace_appends_when_sentinels_missing():
    text = "model: {}\n"
    new_mb = "\n".join([MB_B, "mailbox:", "  board: x", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb)
    assert out.startswith("model: {}")
    assert MB_B in out and MB_E in out
    assert out.count(MB_B) == 1


def test_replace_atomic_under_simulated_sigterm(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: {}\n", encoding="utf-8")
    orig = cfg.read_text()

    real_write = Path.write_text

    def boom(self, *a, **k):
        if str(self).endswith(".tmp"):
            raise RuntimeError("SIGTERM mid-write")
        return real_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(RuntimeError):
        setup.patch_mailbox_block(tmp_path, board="x", label="alpha-sh")
    # original config untouched (os.replace never ran)
    assert cfg.read_text() == orig
