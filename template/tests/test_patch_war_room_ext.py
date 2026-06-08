"""T7: patch_war_room_block reads schema.DEFAULTS and accepts any WAR_ROOM_KEY
kwarg, while staying strictly backward-compatible with existing callers.

Backward-compat for the (board, min_confidence, enforce) calling convention is
also pinned by test_confidence_gate.py and test_gate_wiring.py; this file adds
the new-key surface.
"""
from warroom_setup import setup, schema


def _cfg(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    return tmp_path / "config.yaml"


def test_accepts_label_and_role_kwargs(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x", label="zed", role="lead")
    text = cfg.read_text(encoding="utf-8")
    assert "label: zed" in text
    assert "role: lead" in text
    assert "board: board-x" in text


def test_defaults_pulled_from_schema(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")
    text = cfg.read_text(encoding="utf-8")
    assert "enabled: true" in text
    assert "role: %s" % schema.DEFAULTS["role"] in text
    assert "min_confidence: %d" % schema.DEFAULTS["min_confidence"] in text
    assert "gate_action: %s" % schema.DEFAULTS["gate_action"] in text
    assert "enforce: false" in text
    assert "show_confidence_badge: true" in text


def test_empty_label_is_omitted(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")          # no label
    assert "label:" not in cfg.read_text(encoding="utf-8")


def test_unknown_kwarg_raises(tmp_path):
    _cfg(tmp_path)
    try:
        setup.patch_war_room_block(tmp_path, "board-x", bogus=1)
    except TypeError:
        return
    raise AssertionError("expected TypeError for unknown war_room key")


def test_gate_action_and_enabled_override(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x", gate_action="proceed", enabled=False)
    text = cfg.read_text(encoding="utf-8")
    assert "gate_action: proceed" in text
    assert "enabled: false" in text


def test_min_confidence_is_clamped(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x", min_confidence=150)
    assert "min_confidence: 100" in cfg.read_text(encoding="utf-8")


def test_still_idempotent_with_new_keys(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "b1", label="zed")
    setup.patch_war_room_block(tmp_path, "b2", label="zed2")
    text = cfg.read_text(encoding="utf-8")
    assert text.count(setup._WR_BEGIN) == 1
    assert "board: b2" in text and "b1" not in text
    assert "label: zed2" in text and "label: zed\n" not in text
