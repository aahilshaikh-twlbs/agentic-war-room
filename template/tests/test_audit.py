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
