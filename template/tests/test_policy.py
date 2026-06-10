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


def _envs(conf, sev="default", grounded=("tool",)):
    return Envelope(conf=conf, grounded=grounded, missing="none", sev=sev)


_TABLE = {"alert1": 95, "alert2": 85, "default": 75}


def test_default_sev_uses_default_floor():
    d = P.decide(True, _envs(0.80, "default"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"


def test_alert2_below_its_floor_is_below_severity_floor():
    # clears default 75 but not alert2 85
    d = P.decide(True, _envs(0.80, "alert2"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-severity-floor"


def test_alert1_below_its_floor_is_below_severity_floor():
    d = P.decide(True, _envs(0.90, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-severity-floor"


def test_alert1_clears_its_floor_passes():
    d = P.decide(True, _envs(0.97, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"


def test_below_baseline_is_below_threshold_not_severity_floor():
    # below even the default floor -> the generic below-threshold reason
    d = P.decide(True, _envs(0.50, "alert1"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.ABSTAIN and d.reason == "below-threshold"


def test_unknown_sev_maps_to_default_floor():
    # An envelope can only carry an in-vocab sev (regex-enforced), but a config
    # table missing that sev key falls back to the default floor (lenient, D7).
    d = P.decide(True, _envs(0.80, "alert3"), 0.75, severity_thresholds=_TABLE)
    assert d.action == P.PASS and d.reason == "ok"      # alert3 absent -> default 75


def test_no_table_falls_back_to_scalar_threshold():
    # severity_thresholds None/empty -> the passed threshold is the floor for all.
    d = P.decide(True, _envs(0.80, "alert1"), 0.75)
    assert d.action == P.PASS and d.reason == "ok"
