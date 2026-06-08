import re
from pathlib import Path
from warroom_setup import setup

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_config_enables_plugins():
    cfg = (ROOT / "config.yaml").read_text()
    assert re.search(r"^plugins:\s*$", cfg, re.M)
    assert re.search(r"^\s+enabled:\s*true\s*$", cfg, re.M)


def test_shipped_managed_block_has_gate_keys():
    cfg = (ROOT / "config.yaml").read_text()
    assert "enforce:" in cfg and "show_confidence_badge:" in cfg


def test_patch_writes_gate_keys(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n")
    setup.patch_war_room_block(tmp_path, "incident-9", min_confidence=80, enforce=True)
    text = (tmp_path / "config.yaml").read_text()
    assert "enforce: true" in text and "min_confidence: 80" in text and "show_confidence_badge:" in text
