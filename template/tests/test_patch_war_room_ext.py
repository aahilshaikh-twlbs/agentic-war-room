"""T7: patch_war_room_block reads schema.DEFAULTS and accepts any WAR_ROOM_KEY
kwarg, while staying strictly backward-compatible with existing callers.

Backward-compat for the (board, min_confidence, enforce) calling convention is
also pinned by test_confidence_gate.py and test_gate_wiring.py; this file adds
the new-key surface.
"""
import shutil
from pathlib import Path

from warroom_setup import setup, schema

TEMPLATE_DIR = Path(__file__).resolve().parent.parent


def _cfg(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    return tmp_path / "config.yaml"


def _key_count(text, key):
    return sum(1 for ln in text.splitlines() if ln.startswith(key + ":"))


def _strip_comment_lines(text):
    """Mimic Hermes' PyYAML re-emit: every comment line (incl. sentinels) drops,
    keys + values survive."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    ) + "\n"


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


class TestPatchYamlKeyFallback:
    """Option B: the patchers re-anchor onto a bare top-level key span when a
    PyYAML re-emit has stripped the sentinel comments, instead of appending a
    duplicate block. Exercises the shared-core fallback end-to-end via the public
    patch_*_block entry points (which is what the installer + assimilate call)."""

    def test_war_room_sentinels_intact_in_place_update(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "\n".join([
                "top: 1",
                setup._WR_BEGIN, "war_room:", "  board: old", "  min_confidence: 10",
                setup._WR_END,
                "bottom: 2",
            ]) + "\n",
            encoding="utf-8",
        )
        setup.patch_war_room_block(tmp_path, "shared", min_confidence=70)
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "war_room") == 1
        assert "board: shared" in text and "board: old" not in text
        assert "min_confidence: 70" in text
        assert "top: 1" in text and "bottom: 2" in text

    def test_war_room_sentinels_stripped_block_present_resentineled(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        # Sentinels gone (re-emit), but the war_room: key + body survive.
        cfg.write_text(
            "top: 1\n"
            "war_room:\n"
            "  enabled: false\n"
            "  board: old\n"
            "\n"
            "bottom: 2\n",
            encoding="utf-8",
        )
        setup.patch_war_room_block(tmp_path, "shared", min_confidence=70)
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "war_room") == 1
        assert setup._WR_BEGIN in text and setup._WR_END in text
        assert "board: shared" in text and "board: old" not in text
        # the separator to the next top-level key survived
        assert "bottom: 2" in text

    def test_war_room_block_absent_appends(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("", encoding="utf-8")
        setup.patch_war_room_block(tmp_path, "shared")
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "war_room") == 1
        assert setup._WR_BEGIN in text and setup._WR_END in text

    def test_mailbox_re_sentinels_after_simulated_reemit(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        shutil.copy2(TEMPLATE_DIR / "config.yaml", cfg)
        cfg.write_text(_strip_comment_lines(cfg.read_text(encoding="utf-8")),
                       encoding="utf-8")
        assert ">>> warroom-mailbox" not in cfg.read_text(encoding="utf-8")
        setup.patch_mailbox_block(tmp_path, board="shared", label="alpha-sh")
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "mailbox") == 1
        assert ">>> warroom-mailbox" in text
        assert "board: shared" in text and "label: alpha-sh" in text
        # untouched neighbours survive
        assert _key_count(text, "platform_toolsets") == 1
        assert "hooks:" in text

    def test_mailbox_lookalike_not_clobbered(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "mailbox:\n  board: old\n  label: x\n"
            "mailboxes_other:\n  keep: yes\nbottom: 2\n",
            encoding="utf-8",
        )
        setup.patch_mailbox_block(tmp_path, board="shared", label="alpha-sh")
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "mailbox") == 1
        assert "mailboxes_other:" in text and "keep: yes" in text
        assert ">>> warroom-mailbox" in text

    def test_double_patch_idempotent_after_reemit(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "top: 1\nmailbox:\n  board: old\n  label: x\n\nbottom: 2\n",
            encoding="utf-8",
        )
        # First patch re-anchors onto the bare block; second patch hits sentinels.
        setup.patch_mailbox_block(tmp_path, board="shared", label="alpha-sh")
        setup.patch_mailbox_block(tmp_path, board="shared", label="alpha-sh")
        text = cfg.read_text(encoding="utf-8")
        assert _key_count(text, "mailbox") == 1
        assert text.count(setup._MB_BEGIN) == 1 and text.count(setup._MB_END) == 1


def test_renders_nested_severity_thresholds(tmp_path):
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(
        tmp_path, "board-x",
        severity_thresholds={"alert1": 95, "alert2": 85, "default": 75},
        require_verifier_at="alert1", verifier_label="verify-sh",
        verifier_timeout_s=45, escalate_at="alert2")
    text = cfg.read_text(encoding="utf-8")
    assert "  severity_thresholds:" in text
    assert "    alert1: 95" in text
    assert "    alert2: 85" in text
    assert "    default: 75" in text
    assert "require_verifier_at: alert1" in text
    assert "verifier_label: verify-sh" in text
    assert "verifier_timeout_s: 45" in text
    assert "escalate_at: alert2" in text


def test_empty_severity_thresholds_omitted(tmp_path):
    # Zero-rendered-byte change for non-DEFCON profiles (D2 byte-identical
    # guarantee): the empty dict, the empty-string DEFCON keys, AND the
    # default-valued DEFCON scalars (severity_inference, verifier_timeout_s) are
    # all omitted when no DEFCON surface is configured.
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")
    text = cfg.read_text(encoding="utf-8")
    assert "severity_thresholds:" not in text
    assert "require_verifier_at:" not in text
    assert "verifier_label:" not in text
    assert "escalate_at:" not in text
    # default-valued DEFCON scalars are NOT emitted for a plain profile, so the
    # block matches the pre-DEFCON bytes exactly.
    assert "verifier_timeout_s:" not in text
    assert "severity_inference:" not in text


def test_default_block_is_byte_identical_to_pre_defcon(tmp_path):
    # The whole point of D2: a plain non-DEFCON patch produces the exact same
    # war_room block bytes the pre-DEFCON renderer produced (the shipped
    # config.yaml block shape). Pin every DEFCON key absent.
    cfg = _cfg(tmp_path)
    setup.patch_war_room_block(tmp_path, "board-x")
    text = cfg.read_text(encoding="utf-8")
    for k in ("severity_thresholds", "severity_inference", "require_verifier_at",
              "verifier_label", "verifier_timeout_s", "escalate_at"):
        assert ("%s" % k) not in text, "%s must not render for a non-DEFCON profile" % k


def test_severity_block_survives_reanchor_after_reemit(tmp_path):
    # Option B: nested mapping is captured by the YAML-key fallback span.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "top: 1\n"
        "war_room:\n"
        "  enabled: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "\n"
        "bottom: 2\n", encoding="utf-8")
    setup.patch_war_room_block(
        tmp_path, "shared",
        severity_thresholds={"alert1": 90, "default": 75})
    text = cfg.read_text(encoding="utf-8")
    assert _key_count(text, "war_room") == 1
    assert setup._WR_BEGIN in text and setup._WR_END in text
    assert "    alert1: 90" in text and "alert1: 95" not in text
    assert "bottom: 2" in text
