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


def _count_key(text, key):
    return sum(1 for ln in text.splitlines() if ln.startswith(key + ":"))


# --------------------------------------------------------------------------- #
# Option B -- YAML-key fallback (re-anchor onto a bare top-level key span when
# sentinels are absent, e.g. after a PyYAML re-emit stripped the comments).
# --------------------------------------------------------------------------- #
def test_fallback_replaces_bare_yaml_key_block():
    text = "top: 1\nmailbox:\n  board: shared\n  label: x\n\nother: 2\n"
    new_mb = "\n".join([MB_B, "mailbox:", "  board: shared", "  label: y", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb, yaml_key="mailbox")
    assert _count_key(out, "mailbox") == 1
    assert MB_B in out and MB_E in out
    assert "top: 1" in out and "other: 2" in out
    # The blank-line separator that trailed the bare span must survive so the new
    # sentinelled block does not butt directly against the next top-level key.
    assert MB_E + "\n\nother: 2" in out


def test_fallback_does_not_match_lookalike_key():
    text = "top: 1\nmailboxes_other:\n  board: shared\n  keep: yes\nbottom: 2\n"
    new_mb = "\n".join([MB_B, "mailbox:", "  board: x", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb, yaml_key="mailbox")
    # lookalike NOT matched -> the block is appended, lookalike survives verbatim.
    assert "mailboxes_other:" in out and "  keep: yes" in out
    assert _count_key(out, "mailbox") == 1
    assert MB_B in out and MB_E in out


def test_fallback_preserves_indented_continuation():
    text = ("mailbox:\n  board: shared\n  nested:\n    deep: 1\n\n"
            "  more: 2\nnext_top: 3\n")
    new_mb = "\n".join([MB_B, "mailbox:", "  board: shared", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb, yaml_key="mailbox")
    assert _count_key(out, "mailbox") == 1
    assert "next_top: 3" in out
    # the entire bare span (incl. nested map + interior blank line) is replaced
    assert "nested:" not in out and "deep: 1" not in out and "more: 2" not in out
    # there was no blank line before next_top -> none is fabricated
    assert MB_E + "\nnext_top: 3" in out


def test_fallback_ignored_when_sentinels_present():
    # Pathological: a sentinelled block AND a stray bare mailbox: key.
    text = "\n".join([
        MB_B, "mailbox:", "  board: old", MB_E,
        "",
        "mailbox:", "  board: stray",
        "",
        "bottom: 1",
    ]) + "\n"
    new_mb = "\n".join([MB_B, "mailbox:", "  board: new", MB_E])
    out = setup._replace_sentinel_block(text, MB_B, MB_E, new_mb, yaml_key="mailbox")
    # Sentinel match wins; only the sentinelled block is rewritten. The bare one
    # survives (caller's responsibility) -- fallback is strictly secondary.
    assert "board: new" in out and "board: stray" in out
    assert _count_key(out, "mailbox") == 2


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
