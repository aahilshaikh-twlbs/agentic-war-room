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
