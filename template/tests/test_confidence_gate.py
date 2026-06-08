import re
from pathlib import Path
from warroom_setup import setup

ROOT = Path(__file__).resolve().parents[1]


def test_confidence_gate_skill_exists_with_description():
    s = ROOT / "skills" / "confidence-gate" / "SKILL.md"
    assert s.is_file()
    assert re.search(r"^description:\s+\S", s.read_text(), re.M)


def test_warroom_bundle_includes_confidence_gate():
    b = (ROOT / "skill-bundles" / "warroom.yaml").read_text()
    assert re.search(r"^\s*-\s*confidence-gate\s*$", b, re.M)


def test_shipped_config_has_min_confidence_in_managed_block():
    cfg = (ROOT / "config.yaml").read_text()
    assert setup._WR_BEGIN in cfg and setup._WR_END in cfg
    assert re.search(r"min_confidence:\s*\d+", cfg)


def test_patch_war_room_block_is_idempotent_update(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: {}\n")
    setup.patch_war_room_block(tmp_path, "incident-1", min_confidence=80)
    setup.patch_war_room_block(tmp_path, "incident-2", min_confidence=90)
    text = cfg.read_text()
    assert text.count(setup._WR_BEGIN) == 1          # exactly one managed block
    assert "board: incident-2" in text and "incident-1" not in text
    assert "min_confidence: 90" in text


def test_clamp_min_confidence():
    assert setup._clamp_pct("150") == 100
    assert setup._clamp_pct("-5") == 0
    assert setup._clamp_pct("") == 75
    assert setup._clamp_pct("abc") == 75
    assert setup._clamp_pct("82") == 82
