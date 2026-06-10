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


import json
from pathlib import Path

import pytest

_CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "classifier_cases.json"


def _load_cases():
    rows = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    return [(r["text"], r["expected_is_claim"], r["note"]) for r in rows]


def test_classifier_cases_file_is_valid_list():
    # Ships empty ([]); the tuning loop (Phase 3, data-gated) appends rows.
    rows = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    for r in rows:
        assert set(r) >= {"text", "expected_is_claim", "note"}
        assert isinstance(r["expected_is_claim"], bool)


@pytest.mark.parametrize("text,expected,note", _load_cases())
def test_classifier_regression_cases(text, expected, note):
    # One confirmed real-traffic failure per row. Empty today by design.
    assert C.is_claim(text) is expected, note


def test_infer_severity_raises_untagged_on_prod_cue():
    # cue words bump a default/untagged claim to alert2 (never alert1).
    assert C.infer_severity("the prod database is down", "default") == "alert2"
    assert C.infer_severity("we have an outage in payments", "default") == "alert2"
    assert C.infer_severity("possible data loss on the primary", "default") == "alert2"


def test_infer_severity_never_lowers_an_explicit_tag():
    # An explicit alert1 stays alert1 even with no cue words.
    assert C.infer_severity("everything is calm", "alert1") == "alert1"
    # An explicit alert2 is not lowered, and not raised past alert2 by a cue.
    assert C.infer_severity("prod outage", "alert2") == "alert2"


def test_infer_severity_no_cue_keeps_default():
    assert C.infer_severity("the test suite is a bit slow", "default") == "default"


def test_infer_severity_never_produces_alert1():
    # Raise-only and conservative: the classifier can demand alert2 rigor at most;
    # alert1 must be an explicit human/agent tag.
    assert C.infer_severity("prod data loss outage breach", "default") != "alert1"
