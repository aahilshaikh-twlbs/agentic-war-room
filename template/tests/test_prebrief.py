"""Pre-brief pack: doc parse, persona-sync injection, pin override, verify CLI.

Accretes across Tasks 1, 5, 6, 8, 9, 10, 11. Stdlib + pytest only.
"""
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_DOC = ROOT / "shared" / "prebrief" / "warroom.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _frontmatter(text):
    """Return the raw frontmatter block (between the first two '---' lines)."""
    lines = text.split("\n")
    assert lines and lines[0].strip() == "---", "doc must open with YAML frontmatter"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(out)
        out.append(line)
    raise AssertionError("unclosed frontmatter")


# --------------------------------------------------------------------------- #
# Task 1 -- pack doc shape
# --------------------------------------------------------------------------- #
def test_pack_doc_exists_and_opens_with_frontmatter():
    assert PACK_DOC.is_file()
    text = PACK_DOC.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert text.endswith("\n")


def test_pack_doc_frontmatter_has_required_keys():
    fm = _frontmatter(PACK_DOC.read_text(encoding="utf-8"))
    assert re.search(r"^pack:\s*warroom\s*$", fm, re.M)
    assert re.search(r"^pack_version:\s*\S+", fm, re.M)
    assert re.search(r"^summary:\s*>", fm, re.M)
    assert re.search(r"^members:\s*$", fm, re.M)
    members = re.findall(r"^\s+-\s*([a-z][a-z0-9-]*)\s*$", fm, re.M)
    assert members == ["confidence-gate", "warroom"]


def test_pack_doc_version_is_semver():
    fm = _frontmatter(PACK_DOC.read_text(encoding="utf-8"))
    m = re.search(r"^pack_version:\s*(\S+)\s*$", fm, re.M)
    assert m and _SEMVER.match(m.group(1)), "pack_version must be semver"


def test_pack_doc_body_mirrors_version_and_points_to_warroom():
    text = PACK_DOC.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    ver = re.search(r"^pack_version:\s*(\S+)\s*$", fm, re.M).group(1)
    # version mirrored into the body so a running agent can state its pack
    assert ("Pack version: %s" % ver) in text
    assert "/warroom" in text  # points at the full-protocol expansion
    assert "confidence-gate" in text  # names the gate contract member


# --------------------------------------------------------------------------- #
# Task 5 -- persona-sync injection (present / pinned / omitted)
# --------------------------------------------------------------------------- #
from warroom_setup import persona_sync  # noqa: E402
from warroom_setup.agent_model import AgentIdentity  # noqa: E402

_IDENT = AgentIdentity(
    agent_name="aria", handle="aria-sh", display_name="Aria",
    model="opus", specialist_prefix="aria", agent_fingerprint="aria-xyz",
)


def _prebrief_fixture(tmp_path, *, override_body=None, omit_source=False):
    """A minimal profile with one output whose sections include a prebrief
    section (source = shared/prebrief/warroom.md, local_override =
    local/prebrief/warroom.md, optional = true)."""
    (tmp_path / "shared" / "prebrief").mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "soul-preamble.md").write_text(
        "# {{display_name}} - Persona\n", encoding="utf-8")
    if not omit_source:
        (tmp_path / "shared" / "prebrief" / "warroom.md").write_text(
            "---\npack: warroom\npack_version: 1.0.0\n---\n"
            "# War-room pre-brief\n\nShared briefing body.\n", encoding="utf-8")
    if override_body is not None:
        (tmp_path / "local" / "prebrief").mkdir(parents=True)
        (tmp_path / "local" / "prebrief" / "warroom.md").write_text(
            override_body, encoding="utf-8")
    manifest = {
        "header": "<!-- gen for {{handle}} -->",
        "outputs": [
            {"name": "soul",
             "target": str(tmp_path / "out" / "{{handle}}" / "SOUL.md"),
             "preamble": "templates/soul-preamble.md", "trailer": "",
             "sections": [
                 {"title": "War-room pre-brief",
                  "source": "shared/prebrief/warroom.md",
                  "local_override": "local/prebrief/warroom.md",
                  "optional": True},
             ]},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_prebrief_section_injected_from_shared(tmp_path):
    root = _prebrief_fixture(tmp_path)
    rc = persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
    assert rc == 0
    out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
    assert "## War-room pre-brief" in out
    assert "Shared briefing body." in out
    assert "{{" not in out


def test_prebrief_local_override_wins(tmp_path):
    root = _prebrief_fixture(
        tmp_path, override_body="---\npack: warroom\n---\n# Pinned\n\nPinned body.\n")
    persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
    out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
    assert "Pinned body." in out
    assert "Shared briefing body." not in out  # override wins over source


def test_prebrief_section_omitted_when_optional_source_absent(tmp_path):
    root = _prebrief_fixture(tmp_path, omit_source=True)
    rc = persona_sync.run(root / "manifest.json", root, _IDENT, check=False)
    assert rc == 0  # optional + absent -> graceful omit, SOUL still valid
    out = (root / "out" / "aria-sh" / "SOUL.md").read_text(encoding="utf-8")
    assert "## War-room pre-brief" not in out
    assert "# Aria - Persona" in out  # preamble still rendered; SOUL is valid


def test_nonoptional_missing_source_still_raises(tmp_path):
    # regression guard: a NON-optional missing source must still raise (existing
    # _read contract for the persona sections must not be loosened globally)
    import pytest
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "soul-preamble.md").write_text("# x\n", encoding="utf-8")
    manifest = {
        "header": "h", "outputs": [
            {"name": "soul", "target": str(tmp_path / "o" / "SOUL.md"),
             "preamble": "templates/soul-preamble.md", "trailer": "",
             "sections": [{"title": "Role", "source": "local/persona/role.md"}]}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        persona_sync.run(tmp_path / "manifest.json", tmp_path, _IDENT, check=False)
