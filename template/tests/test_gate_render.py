import wg_render as R
import wg_policy as P


def test_below_threshold_abstention_names_gap_and_numbers():
    d = P.Decision(P.ABSTAIN, "below-threshold", "a prod log line")
    msg = R.abstention(d, conf_pct=62, threshold_pct=75)
    assert "62%" in msg and "75%" in msg and "a prod log line" in msg


def test_ungrounded_abstention():
    d = P.Decision(P.ABSTAIN, "ungrounded", "a citation")
    msg = R.abstention(d, None, None)
    assert "isn't grounded" in msg and "a citation" in msg


def test_no_envelope_abstention():
    d = P.Decision(P.ABSTAIN, "no-envelope")
    msg = R.abstention(d, None, None)
    assert "no confidence envelope" in msg.lower()


def test_with_badge_appends_when_shown():
    out = R.with_badge("The fix is in api/pay.py.", 0.82, True)
    assert "82%" in out and out.startswith("The fix")


def test_with_badge_noop_when_hidden():
    assert R.with_badge("body", 0.82, False) == "body"
