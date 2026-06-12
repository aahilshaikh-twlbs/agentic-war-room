"""No-length-heuristic guard for the claim/chatter classifier.

Two complementary checks: a BEHAVIORAL check that classification does not
correlate with length (terse declaratives gate; a long non-token message is NOT
short-circuited to chatter by its length), and a SOURCE-LEVEL check that the only
`len(` comparison in wg_classify.py is the one bounding the pure-question rule.
Reintroducing any length short-circuit on the claim/chatter decision must fail
this test.

See the gate spec (lines 178-182) and the classifier-tuning design (Arch §5):
NEVER route text to chatter because it is short.
"""
import re
from pathlib import Path

import wg_classify as C

SRC = Path(C.__file__)


def test_terse_declaratives_of_increasing_brevity_all_gate():
    # Increasingly terse, but every one is an assertion -> must be a claim.
    for t in ["it's down", "db is corrupted", "prod broke", "oom", "503s"]:
        assert C.is_claim(t) is True, t


def test_length_never_short_circuits_a_long_message_to_chatter():
    # ~285 chars of pure thanks. It is NOT an exact _CHATTER token, so the
    # default-to-gate branch correctly classifies it as a claim. The guard's
    # point is the inverse: a long string is never EXEMPTED to chatter by length.
    # (A genuinely long ack is handled by adding the exact token to _CHATTER
    # during tuning -- never by a length rule.)
    long_thanks = "thanks so much everyone, really appreciate the help here " * 5
    assert len(long_thanks) > 200
    assert C.is_claim(long_thanks) is True


def test_only_len_comparison_is_the_pure_question_bound():
    """Source-level belt-and-suspenders: pin the ONE allowed len( use.

    The pure-question rule bounds a QUESTION's length (len(t) < 200), which is
    not a claim/chatter short-circuit. Any other `len(` comparison in the module
    is a reintroduced length heuristic and must trip this guard.
    """
    src = SRC.read_text(encoding="utf-8")
    len_uses = re.findall(r"len\([^)]*\)", src)
    # Exactly one len( call exists today, inside the pure-question rule.
    assert len_uses == ["len(t)"], len_uses
    assert "len(t) < 200" in src
    # No comparison routes to chatter based on length anywhere else.
    numeric_len_cmp = re.findall(r"len\([^)]*\)\s*[<>]=?\s*\d+", src)
    assert numeric_len_cmp == ["len(t) < 200"], numeric_len_cmp
