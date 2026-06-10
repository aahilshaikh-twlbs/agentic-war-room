"""Tests for the stdlib failure-review CLI (gate_review.py): parse + summarize."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "gate_review.py"
    spec = importlib.util.spec_from_file_location("gate_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GR = _load()

OLD_LINE = "2026-06-09T18:22:01+00:00 action=abstain reason=below-threshold conf=0.62 kind=claim sha=1a2b3c4d"
NEW_CHATTER = ("2026-06-09T18:22:02+00:00 verdict=chatter action=pass reason=chatter "
               "conf=- kind=chatter len=xs ends_q=0 multiline=0 matched=thanks "
               "sha256=a6a2729cbf6bcadce577a31f7f76201d5ce63c57d6c53318000d67714bb354ef")
NEW_CLAIM = ("2026-06-09T18:22:03+00:00 verdict=claim action=abstain reason=ungrounded "
             "conf=0.50 kind=claim len=m ends_q=0 multiline=0 matched=none "
             "sha256=2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae")


def test_parse_new_line_extracts_all_fields():
    d = GR.parse_line(NEW_CHATTER)
    assert d["verdict"] == "chatter"
    assert d["action"] == "pass"
    assert d["reason"] == "chatter"
    assert d["matched"] == "thanks"
    assert d["sha256"].startswith("a6a2729c")   # sha256("thanks"), matches matched=thanks
    assert d["len"] == "xs"


def test_parse_old_line_tolerated_missing_keys_default():
    d = GR.parse_line(OLD_LINE)
    assert d["action"] == "abstain"
    assert d["reason"] == "below-threshold"
    assert d.get("verdict") in (None, "")     # missing additive key -> no KeyError
    assert d.get("matched") in (None, "")
    assert d["sha"] == "1a2b3c4d"


def test_parse_blank_and_garbage_lines_return_none():
    assert GR.parse_line("") is None
    assert GR.parse_line("   ") is None
    assert GR.parse_line("not a log line") is None   # no key=value tokens


def test_summarize_counts_by_verdict_action_matched(tmp_path):
    logf = tmp_path / "gate.log"
    logf.write_text("\n".join([OLD_LINE, NEW_CHATTER, NEW_CLAIM]) + "\n", encoding="utf-8")
    summary = GR.summarize(GR.read_log(logf))
    assert summary["total"] == 3
    assert summary["verdict"]["chatter"] == 1
    assert summary["verdict"]["claim"] == 1
    assert summary["verdict"]["(unset)"] == 1     # the old line
    assert summary["action"]["abstain"] == 2
    assert summary["action"]["pass"] == 1
    assert summary["matched"]["thanks"] == 1


def test_main_review_prints_table(tmp_path, capsys):
    logf = tmp_path / "gate.log"
    logf.write_text(NEW_CHATTER + "\n" + NEW_CLAIM + "\n", encoding="utf-8")
    rc = GR.main(["review", "--log", str(logf)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "verdict" in out and "chatter" in out and "claim" in out
    assert "total: 2" in out


import hashlib
import io
import json as _json

import pytest


def _run_label(monkeypatch, stdin_text, argv):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    return GR.main(argv)


def test_label_appends_fixture_on_hash_match(tmp_path, monkeypatch):
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    original = "rolling back the deploy now"
    sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    logf.write_text(
        ("2026-06-09T18:00:00+00:00 verdict=chatter action=pass reason=chatter "
         "conf=- kind=chatter len=s ends_q=0 multiline=0 matched=none sha256=%s\n" % sha),
        encoding="utf-8")
    rc = _run_label(monkeypatch, original, [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "claim", "--note", "FN: action statement passed as chatter",
        "--fixtures", str(fixtures)])
    assert rc == 0
    rows = _json.loads(fixtures.read_text(encoding="utf-8"))
    assert rows == [{
        "text": "rolling back the deploy now",
        "expected_is_claim": True,
        "note": "FN: action statement passed as chatter",
    }]
    # the original text must NOT have been written into the log
    assert "rolling back the deploy now" not in logf.read_text(encoding="utf-8")


def test_label_rejects_wrong_original(tmp_path, monkeypatch):
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    sha = hashlib.sha256("the real message".encode("utf-8")).hexdigest()
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=%s\n" % sha, encoding="utf-8")
    rc = _run_label(monkeypatch, "a DIFFERENT message", [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "chatter", "--note", "should reject", "--fixtures", str(fixtures)])
    assert rc == 3                                          # sha256 mismatch
    assert _json.loads(fixtures.read_text(encoding="utf-8")) == []   # nothing appended


def test_label_rejects_sha_absent_from_log(tmp_path, monkeypatch):
    # The supplied text hashes to --sha256 (so exit 3 does NOT fire), but no
    # gate.log line carries that sha256 -> the message was never gated, so the
    # tool must refuse (exit 4) rather than label a phantom decision.
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    other = hashlib.sha256("some other gated line".encode("utf-8")).hexdigest()
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=%s\n" % other, encoding="utf-8")
    original = "a message that was never gated"
    sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    rc = _run_label(monkeypatch, original, [
        "label", "--log", str(logf), "--sha256", sha,
        "--expected", "claim", "--note", "should reject: not in log",
        "--fixtures", str(fixtures)])
    assert rc == 4                                          # sha not present in log
    assert _json.loads(fixtures.read_text(encoding="utf-8")) == []   # nothing appended


def test_label_bad_expected_value_exits_2(tmp_path, monkeypatch):
    # argparse choices reject anything but claim|chatter -> SystemExit(2).
    fixtures = tmp_path / "classifier_cases.json"
    fixtures.write_text("[]\n", encoding="utf-8")
    logf = tmp_path / "gate.log"
    logf.write_text("2026-06-09T18:00:00+00:00 sha256=deadbeef\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_label(monkeypatch, "x", [
            "label", "--log", str(logf), "--sha256", "deadbeef",
            "--expected", "maybe", "--note", "n", "--fixtures", str(fixtures)])
    assert exc.value.code == 2
