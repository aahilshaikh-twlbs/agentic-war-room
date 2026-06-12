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


# --------------------------------------------------------------------------- #
# Task 8 -- prebrief.py: parse_pack, show, verify
# --------------------------------------------------------------------------- #
from warroom_setup import prebrief  # noqa: E402


def _profile_with_pack(tmp_path, *, members=("confidence-gate", "warroom"),
                       pack_version="1.0.0", with_skills=True,
                       with_bundle=True, with_doc=True, body_version=None):
    """Build a tmp profile with a pack doc, member skills, and a bundle."""
    if body_version is None:
        body_version = pack_version
    if with_doc:
        (tmp_path / "shared" / "prebrief").mkdir(parents=True)
        ml = "\n".join("  - %s" % m for m in members)
        (tmp_path / "shared" / "prebrief" / "warroom.md").write_text(
            "---\npack: warroom\npack_version: %s\nsummary: >\n  s\nmembers:\n%s\n---\n"
            "# War-room pre-brief\n\nPack version: %s\n" % (pack_version, ml, body_version),
            encoding="utf-8")
    if with_skills:
        for m in members:
            (tmp_path / "skills" / m).mkdir(parents=True)
            (tmp_path / "skills" / m / "SKILL.md").write_text(
                "---\nname: %s\ndescription: d\n---\n# %s\n" % (m, m), encoding="utf-8")
    if with_bundle:
        (tmp_path / "skill-bundles").mkdir(parents=True)
        sk = "\n".join("  - %s" % m for m in members)
        (tmp_path / "skill-bundles" / "warroom.yaml").write_text(
            "name: warroom\ndescription: d\nskills:\n%s\ninstruction: |\n  x\n" % sk,
            encoding="utf-8")
    return tmp_path


def test_parse_pack_reads_frontmatter(tmp_path):
    root = _profile_with_pack(tmp_path)
    pack = prebrief.parse_pack(root, "warroom")
    assert pack["pack"] == "warroom"
    assert pack["pack_version"] == "1.0.0"
    assert pack["members"] == ["confidence-gate", "warroom"]


def test_parse_pack_missing_doc_raises(tmp_path):
    root = _profile_with_pack(tmp_path, with_doc=False)
    import pytest
    with pytest.raises(FileNotFoundError):
        prebrief.parse_pack(root, "warroom")


def test_show_prints_version_members_and_install_status(tmp_path):
    root = _profile_with_pack(tmp_path)
    out = io.StringIO()
    rc = prebrief.show(root, "warroom", out=out)
    assert rc == 0
    text = out.getvalue()
    assert "pack: warroom" in text and "version: 1.0.0" in text
    assert "confidence-gate" in text and "warroom" in text
    assert "installed" in text  # member install status column


def test_show_reports_pin_gap(tmp_path):
    root = _profile_with_pack(tmp_path, pack_version="1.2.0")
    (root / "local" / "prebrief").mkdir(parents=True)
    (root / "local" / "prebrief" / "warroom.md").write_text(
        "---\npack: warroom\npack_version: 1.0.0\n---\n# x\nPack version: 1.0.0\n",
        encoding="utf-8")
    out = io.StringIO()
    prebrief.show(root, "warroom", out=out)
    text = out.getvalue()
    assert "pinned: 1.0.0" in text and "available: 1.2.0" in text


def test_verify_passes_on_healthy_pack(tmp_path):
    root = _profile_with_pack(tmp_path)
    out = io.StringIO()
    assert prebrief.verify(root, "warroom", out=out) == 0
    assert "OK" in out.getvalue()


def test_verify_fails_on_missing_member_skill(tmp_path):
    root = _profile_with_pack(tmp_path, with_skills=False)
    out = io.StringIO()
    assert prebrief.verify(root, "warroom", out=out) == 1
    assert "does not resolve" in out.getvalue()


def test_verify_fails_on_bundle_mismatch(tmp_path):
    root = _profile_with_pack(tmp_path)
    # bundle drops a member
    (root / "skill-bundles" / "warroom.yaml").write_text(
        "name: warroom\ndescription: d\nskills:\n  - warroom\ninstruction: |\n  x\n",
        encoding="utf-8")
    out = io.StringIO()
    assert prebrief.verify(root, "warroom", out=out) == 1
    assert "bundle" in out.getvalue()


def test_verify_fails_on_version_mirror_drift(tmp_path):
    root = _profile_with_pack(tmp_path, pack_version="1.0.0", body_version="9.9.9")
    out = io.StringIO()
    assert prebrief.verify(root, "warroom", out=out) == 1
    assert "version" in out.getvalue().lower()


def test_verify_missing_doc_returns_1(tmp_path):
    root = _profile_with_pack(tmp_path, with_doc=False)
    out = io.StringIO()
    assert prebrief.verify(root, "warroom", out=out) == 1
    assert "pack doc" in out.getvalue().lower()


# --------------------------------------------------------------------------- #
# Task 9 -- sync / pin / unpin
# --------------------------------------------------------------------------- #
def test_pin_copies_shared_to_local_atomically(tmp_path):
    root = _profile_with_pack(tmp_path)
    out = io.StringIO()
    assert prebrief.pin(root, "warroom", out=out) == 0
    pin = root / "local" / "prebrief" / "warroom.md"
    assert pin.is_file()
    assert pin.read_text(encoding="utf-8") == \
        (root / "shared" / "prebrief" / "warroom.md").read_text(encoding="utf-8")
    assert "pinned" in out.getvalue()


def test_pin_leaves_no_tmp_file(tmp_path):
    root = _profile_with_pack(tmp_path)
    prebrief.pin(root, "warroom", out=io.StringIO())
    leftovers = list((root / "local" / "prebrief").glob("*.tmp"))
    assert leftovers == []


def test_pin_missing_source_returns_1(tmp_path):
    root = _profile_with_pack(tmp_path, with_doc=False)
    out = io.StringIO()
    assert prebrief.pin(root, "warroom", out=out) == 1


def test_unpin_removes_local_override(tmp_path):
    root = _profile_with_pack(tmp_path)
    prebrief.pin(root, "warroom", out=io.StringIO())
    out = io.StringIO()
    assert prebrief.unpin(root, "warroom", out=out) == 0
    assert not (root / "local" / "prebrief" / "warroom.md").exists()
    assert "unpinned" in out.getvalue()


def test_unpin_when_not_pinned_is_noop_zero(tmp_path):
    root = _profile_with_pack(tmp_path)
    out = io.StringIO()
    assert prebrief.unpin(root, "warroom", out=out) == 0
    assert "not pinned" in out.getvalue()


def test_sync_delegates_to_persona_sync(tmp_path, monkeypatch):
    root = _profile_with_pack(tmp_path)
    (root / "local").mkdir(exist_ok=True)
    (root / "local" / "agent.json").write_text(
        json.dumps({"agent_name": "aria", "handle": "aria-sh",
                    "display_name": "Aria", "model": "opus",
                    "specialist_prefix": "aria", "agent_fingerprint": "aria-xyz"}),
        encoding="utf-8")
    calls = {}

    def fake_run(manifest, repo_root, ident, check=False):
        calls["manifest"] = Path(manifest)
        calls["repo_root"] = Path(repo_root)
        return 0

    monkeypatch.setattr(prebrief.persona_sync, "run", fake_run)
    (root / "manifest.json").write_text('{"header":"h","outputs":[]}', encoding="utf-8")
    out = io.StringIO()
    assert prebrief.sync(root, out=out) == 0
    assert calls["manifest"] == root / "manifest.json"


def test_sync_no_identity_returns_2(tmp_path):
    root = _profile_with_pack(tmp_path)
    out = io.StringIO()
    assert prebrief.sync(root, out=out) == 2
    assert "warroom setup" in out.getvalue()
