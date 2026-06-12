"""matched_chatter(): which _CHATTER token a message normalized to (read-only)."""
import wg_classify as C


def test_matched_chatter_returns_exact_token():
    assert C.matched_chatter("thanks") == "thanks"
    assert C.matched_chatter("Thanks!") == "thanks"   # same normalization as is_claim
    assert C.matched_chatter("OK.") == "ok"
    assert C.matched_chatter("ty") == "ty"


def test_matched_chatter_none_for_claims_and_questions():
    assert C.matched_chatter("the db is down") is None
    assert C.matched_chatter("which service owns checkout?") is None
    assert C.matched_chatter("") is None
    assert C.matched_chatter("   ") is None


def test_matched_chatter_emoji_only_normalizes_to_empty_not_a_token():
    # Emoji-only strips to "" (not a _CHATTER member name) -> no matched token,
    # even though is_claim treats it as chatter.
    assert C.matched_chatter("👍") is None
    assert C.is_claim("👍") is False


def test_matched_chatter_does_not_change_classification():
    # The helper is read-only: is_claim must be unaffected.
    for t in ["ok", "it's down", "thanks", "prod broke", "  "]:
        before = C.is_claim(t)
        C.matched_chatter(t)
        assert C.is_claim(t) is before, t
