import os
import stat
import wg_audit as A
import wg_policy as P


def test_log_appends_no_secret_text(tmp_path):
    d = P.Decision(P.ABSTAIN, "below-threshold", "a repro")
    A.log(tmp_path, d, 0.6, "claim", "SECRET answer body with sk-xxx token")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert logf.is_file()
    text = logf.read_text()
    assert "abstain" in text and "below-threshold" in text
    assert "sk-xxx" not in text and "SECRET answer body" not in text   # only a hash prefix


def test_log_file_is_0600(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert stat.S_IMODE(os.stat(logf).st_mode) == 0o600


def test_log_never_raises_on_bad_root(tmp_path):
    # A non-writable / odd root must not raise (logging is best-effort).
    A.log(tmp_path / "nonexistent-parent" / "x", P.Decision(P.PASS, "ok"), None, "chatter", "")


import hashlib


def test_log_emits_verdict_and_features(tmp_path):
    d = P.Decision(P.PASS, "chatter")
    A.log(tmp_path, d, None, "chatter", "thanks", verdict="chatter")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=chatter" in line
    assert "len=xs" in line           # 6 chars -> xs bucket
    assert "ends_q=0" in line
    assert "multiline=0" in line
    assert "matched=thanks" in line
    full = hashlib.sha256("thanks".encode("utf-8")).hexdigest()
    assert ("sha256=%s" % full) in line
    assert " sha=" not in line        # old 8-char field gone


def test_log_features_for_multiline_question_claim(tmp_path):
    d = P.Decision(P.ABSTAIN, "no-envelope")
    text = "is the db down?\nlooks like it from the metrics"
    A.log(tmp_path, d, 0.9, "claim", text, verdict="claim")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=claim" in line
    assert "multiline=1" in line      # contains a newline
    assert "ends_q=0" in line         # whole text does not END with ?
    assert "matched=none" in line     # not a chatter token
    assert "conf=0.90" in line


def test_log_ends_q_true_for_trailing_question(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "chatter"), None, "chatter",
          "which service owns checkout?", verdict="chatter")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "ends_q=1" in line


def test_log_len_buckets(tmp_path):
    # xs < 16 <= s < 64 <= m < 256 <= l
    cases = [("hi", "len=xs"), ("x" * 20, "len=s"),
             ("y" * 100, "len=m"), ("z" * 400, "len=l")]
    for text, expect in cases:
        root = tmp_path / ("p_%d" % len(text))
        A.log(root, P.Decision(P.PASS, "ok"), None, "claim", text, verdict="claim")
        line = (root / "local" / "war_room" / "gate.log").read_text()
        assert expect in line, (text, line)


def test_log_no_body_or_secret_in_extended_line(tmp_path):
    A.log(tmp_path, P.Decision(P.ABSTAIN, "below-threshold", "a repro"),
          0.6, "claim", "SECRET deploy creds sk-xxx in api/pay.py", verdict="claim")
    text = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "sk-xxx" not in text and "SECRET deploy creds" not in text
    assert "api/pay.py" not in text
    assert "verdict=claim" in text     # features present, body absent


def test_log_verdict_omitted_when_not_supplied_backcompat(tmp_path):
    # Old call sites that don't pass verdict still work (token simply absent).
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=" not in line
    assert "len=xs" in line and "sha256=" in line
    assert "action=pass" in line


def test_log_file_still_0600_with_extension(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body", verdict="claim")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert stat.S_IMODE(os.stat(logf).st_mode) == 0o600


def test_log_never_raises_with_extension_on_bad_root(tmp_path):
    A.log(tmp_path / "nope" / "x", P.Decision(P.PASS, "ok"), None,
          "chatter", "anything", verdict="chatter")


def test_log_multiword_matched_token_stays_one_space_free_field(tmp_path):
    # "got it" is a real multi-word _CHATTER token. Its space would otherwise
    # break the whitespace-delimited key=value contract: line.split() +
    # tok.partition("=") would record matched="got" and drop a bare "it" token.
    # The writer encodes the internal space as "_" so the field stays atomic.
    A.log(tmp_path, P.Decision(P.PASS, "chatter"), None, "chatter", "got it",
          verdict="chatter")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "matched=got_it" in line
    # Parse exactly as gate_review.parse_line does (split on whitespace).
    parsed = {}
    for tok in line.split():
        if "=" in tok:
            k, _sep, v = tok.partition("=")
            parsed[k] = v
    assert parsed["matched"] == "got_it"   # whole token preserved, not "got"
    assert "it" not in line.split()        # no orphaned bare "it" token
    full = hashlib.sha256("got it".encode("utf-8")).hexdigest()
    assert parsed["sha256"] == full        # sha256 survives intact, not by luck


def test_log_records_sev_and_verify_extra(tmp_path):
    d = P.Decision(P.PASS, "ok")
    A.log(tmp_path, d, 0.97, "claim", "prod db corrupted",
          verdict="claim", extra={"sev": "alert1", "verify": "signed"})
    text = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "sev=alert1" in text and "verify=signed" in text
    # extra fields land immediately BEFORE sha256= (DV1: this plan adds the extra=
    # kwarg; the classifier plan's INTERFACE CONTRACT keeps sha256= last).
    assert text.index("sev=") < text.index("sha256=")
    assert text.index("verify=") < text.index("sha256=")
    # still no body in the log
    assert "prod db corrupted" not in text
