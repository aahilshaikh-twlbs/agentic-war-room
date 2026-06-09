"""T10 -- byte-level snapshot + semantic guards for the assimilate SKILL.md.

The snapshot pins the exact bytes via sha256 so any edit is an INTENTIONAL act
(regenerate the hash below after a deliberate change). The semantic asserts
document the contract the skill must keep even if someone re-pins the hash.
"""
import hashlib
from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "skills" / "assimilate-warroom" / "SKILL.md")

# Regenerate after an intentional edit:
#   python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('template/skills/assimilate-warroom/SKILL.md').read_bytes()).hexdigest())"
EXPECTED_SHA256 = "5efebc25ed613b5e3ac8314daafa51620cd30a52f6d160fc2ee1f1b602f651e5"


def test_skill_byte_snapshot():
    data = SKILL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    assert data.endswith(b"\n")


def test_skill_frontmatter_and_triggers():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: assimilate-warroom\n")
    # trigger phrases the loader keys on
    for phrase in ("join the war room", "assimilate", "wire me into the war"):
        assert phrase in text


def test_skill_documents_command_and_exit_codes():
    text = SKILL.read_text(encoding="utf-8")
    assert 'python -m warroom_setup assimilate "$CLAUDE_PROJECT_DIR"' in text
    # exit-code contract mirrors the CLI
    for code in ("`0`", "`1`", "`2`", "`3`", "`4`"):
        assert code in text
    # synthesis-mandated guidance
    assert "Restart this Claude Code session" in text
    assert "BEFORE enrolling" in text  # creds-before-bootstrap promise
    assert "--reconfigure" in text and "--dry-run" in text and "--no-walkthrough" in text
