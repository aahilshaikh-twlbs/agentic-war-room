"""T6 — warroom SKILL.md is the real cross-agent protocol (not a placeholder)."""
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "warroom" / "SKILL.md"

REQUIRED_VERBS = [
    "mailbox ps",
    "mailbox claim-lane",
    "mailbox release-lane",
    "mailbox list-lanes",
    "mailbox send",
    "mailbox inbox",
]


def _code_block_text(md):
    out, infence = [], False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            infence = not infence
            continue
        if infence:
            out.append(line)
    return "\n".join(out)


def _frontmatter(md):
    lines = md.splitlines()
    assert lines[0].strip() == "---", "frontmatter must open with ---"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fm = lines[1:end]
    data = {}
    key = None
    for line in fm:
        if line and not line[0].isspace() and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            data[key] = val.strip()
        elif key and line.strip():  # folded continuation
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def test_skill_md_contains_required_verbs():
    code = _code_block_text(SKILL.read_text(encoding="utf-8"))
    for verb in REQUIRED_VERBS:
        assert verb in code, "missing verb in code blocks: %r" % verb


def test_skill_md_frontmatter_valid():
    fm = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fm.get("name") == "warroom"
    desc = fm.get("description", "")
    assert isinstance(desc, str) and desc.strip()
    assert len(desc) <= 500
    # the fictional metadata.hermes.tags field must be gone
    assert "tags" not in fm
