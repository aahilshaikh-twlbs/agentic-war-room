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


def test_shipped_config_orchestrate_on():
    cfg = (ROOT / "config.yaml").read_text()
    m = re.search(r"^war_room:\n((?:[ \t].*\n)*)", cfg, re.M)
    assert m, "shipped config must carry a war_room block"
    assert re.search(r"^\s{2}orchestrate:\s*true\s*$", m.group(1), re.M)


# ---- Pre-brief pack ↔ bundle ↔ skills consistency ----

def _pack_members():
    text = (ROOT / "shared" / "prebrief" / "warroom.md").read_text(encoding="utf-8")
    fm = text.split("---", 2)[1]  # frontmatter between the first two '---'
    return re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)


def _bundle_skills():
    bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text(encoding="utf-8")
    # skills: list only — stop at the next top-level key (e.g. instruction:)
    m = re.search(r"^skills:\s*\n((?:\s+-\s*.*\n)+)", bundle, re.M)
    assert m, "bundle must carry a skills: list"
    return re.findall(r"-\s*([a-z][a-z0-9-]*)", m.group(1))


def test_pack_members_each_resolve_to_a_skill_dir():
    for member in _pack_members():
        skill = ROOT / "skills" / member / "SKILL.md"
        assert skill.is_file(), "pack member %r has no skills/%s/SKILL.md" % (member, member)


def test_pack_members_equal_bundle_skills_as_sets():
    # no orphan in either direction: every member is in the bundle and vice versa
    assert set(_pack_members()) == set(_bundle_skills())


def test_pack_doc_lists_exactly_warroom_and_confidence_gate():
    assert set(_pack_members()) == {"warroom", "confidence-gate"}


def test_sanitize_check_scans_shared_prebrief():
    # The pack doc lands under shared/prebrief/; lock in that the sanitizer walks
    # it (shared is NOT excluded; .md IS a scan suffix). If a future change drops
    # shared/** from the walked tree this fails loudly (the spec's "extend scope").
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts import sanitize_check
    assert "shared" not in sanitize_check.EXCLUDE_DIRS
    assert ".md" in sanitize_check.SCAN_SUFFIXES
    scanned = list(sanitize_check._iter_files(str(ROOT / "shared")))
    assert any(p.endswith("prebrief/warroom.md") for p in scanned)


def test_bundle_instruction_references_prebrief_without_regressing_intake():
    bundle = (ROOT / "skill-bundles" / "warroom.yaml").read_text(encoding="utf-8")
    m = re.search(r"^instruction:\s*\|\n((?:[ \t]+.*\n?)*)", bundle, re.M)
    assert m, "bundle must carry a block-scalar instruction"
    instr = m.group(1).lower()
    # pre-brief reference is present
    assert "pre-brief" in instr or "prebrief" in instr
    # AND the L1 intake order is NOT regressed (same guard L1 ships)
    order = ["orient", "triage", "severity", "route", "lane", "first post"]
    idxs = [instr.find(w) for w in order]
    assert -1 not in idxs, "intake steps must still be named: %r" % order
    assert idxs == sorted(idxs), "intake steps must stay in order"
    assert "confidence-gate" in instr
