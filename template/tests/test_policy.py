import wg_policy as P
from wg_envelope import Envelope


def _env(conf, grounded=("tool",), missing="none"):
    return Envelope(conf=conf, grounded=grounded, missing=missing)


def test_chatter_passes():
    d = P.decide(False, None, 0.75)
    assert d.action == P.PASS and d.reason == "chatter"


def test_claim_no_envelope_abstains():
    d = P.decide(True, None, 0.75)
    assert d.action == P.ABSTAIN and d.reason == "no-envelope"


def test_claim_ungrounded_abstains():
    d = P.decide(True, _env(0.9, grounded=("none",)), 0.75)
    assert d.action == P.ABSTAIN and d.reason == "ungrounded"


def test_claim_below_threshold_abstains_with_missing():
    d = P.decide(True, _env(0.60, missing="a repro"), 0.75)
    assert d.action == P.ABSTAIN and d.reason == "below-threshold" and d.missing == "a repro"


def test_claim_grounded_and_confident_passes():
    d = P.decide(True, _env(0.80), 0.75)
    assert d.action == P.PASS and d.reason == "ok"
