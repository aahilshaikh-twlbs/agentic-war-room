import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "warroom-gate"


def test_plugin_dir_has_manifest_and_init():
    assert (PLUGIN / "plugin.yaml").is_file()
    assert (PLUGIN / "__init__.py").is_file()


def test_manifest_has_name_and_kind():
    text = (PLUGIN / "plugin.yaml").read_text()
    assert re.search(r"^name:\s*warroom-gate\s*$", text, re.M)
    assert re.search(r"^kind:\s*standalone\s*$", text, re.M)
