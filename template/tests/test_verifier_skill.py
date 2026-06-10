"""Byte-level snapshot + semantic guards for the warroom-verifier SKILL.md.

The snapshot pins the exact bytes via sha256 so any edit is INTENTIONAL
(regenerate the hash after a deliberate change). The semantic asserts document
the contract the skill must keep even if someone re-pins the hash.
"""
import hashlib
from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / "skills" / "warroom-verifier" / "SKILL.md")

# Regenerate after an intentional edit:
#   python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('template/skills/warroom-verifier/SKILL.md').read_bytes()).hexdigest())"
EXPECTED_SHA256 = "c55c69a2b833bf21fb9fc1892d45bdf189c917e285afd65a2c5b6c57b0817a0c"


def test_skill_byte_snapshot():
    data = SKILL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    assert data.endswith(b"\n")


def test_skill_frontmatter_and_role():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: warroom-verifier\n")
    assert "war_room.role: verifier" in text


def test_skill_documents_protocol_and_verbs():
    text = SKILL.read_text(encoding="utf-8")
    assert "verify_request" in text and "verify_verdict" in text
    assert "mailbox inbox --json --local" in text
    assert "mailbox send" in text and "--kind verify_verdict" in text
    # adversarial posture + echo discipline + self-verify ban
    assert "Do not echo" in text
    assert "echo the `request_id`" in text or "echo it" in text
    assert "never its own verifier" in text


def test_skill_is_employer_free():
    text = SKILL.read_text(encoding="utf-8").lower()
    for forbidden in ("twelvelabs", "twelve labs", "@twelvelabs"):
        assert forbidden not in text
