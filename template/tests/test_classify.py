import wg_classify as C


def test_chatter_is_not_a_claim():
    for t in ["ok", "got it", "thanks!", "on it", "👍", "hey", "yes"]:
        assert C.is_claim(t) is False, t


def test_pure_question_is_not_a_claim():
    assert C.is_claim("which service owns the checkout flow?") is False


def test_substantive_assertion_is_a_claim():
    assert C.is_claim("The outage is caused by a 30s timeout in api/pay.py:88.") is True


def test_terse_declarative_is_a_claim():
    # Short, no period, but still an assertion — must be gated, not exempted.
    for t in ["it's down", "payments are failing", "db is corrupted"]:
        assert C.is_claim(t) is True, t


def test_empty_is_not_a_claim():
    assert C.is_claim("   ") is False
