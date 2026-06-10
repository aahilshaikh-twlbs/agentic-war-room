import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_references_an_existing_skill():
    bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text()
    # crude: the skills: list names "warroom"
    assert re.search(r"^\s*-\s*warroom\s*$", bundle, re.M)
    skill = ROOT / "skills" / "warroom" / "SKILL.md"
    assert skill.is_file(), "bundle would be suppressed if the skill does not resolve"


def test_skill_has_description_frontmatter():
    text = (ROOT / "skills" / "warroom" / "SKILL.md").read_text()
    assert text.startswith("---")
    assert re.search(r"^description:\s+\S", text, re.M)


def test_config_has_war_room_block():
    cfg = (ROOT / "config.yaml").read_text()
    assert re.search(r"^war_room:", cfg, re.M)


def test_bundle_instruction_names_intake_order():
    bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text()
    m = re.search(r"^instruction:\s*\|\n((?:[ \t]+.*\n?)*)", bundle, re.M)
    assert m, "bundle must carry a block-scalar instruction"
    instr = m.group(1).lower()
    order = ["orient", "triage", "severity", "route", "lane", "first post"]
    idxs = [instr.find(w) for w in order]
    assert -1 not in idxs, "instruction must name every intake step: %r" % order
    assert idxs == sorted(idxs), "intake steps must be named in order"
    assert "confidence-gate" in instr


def test_bundle_skill_list_unchanged():
    bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text()
    skills = re.findall(r"^\s*-\s*([a-z-]+)\s*$", bundle, re.M)
    assert skills == ["warroom", "confidence-gate"]
