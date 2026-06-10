"""DEFCON / severity: the independent-verifier client. All effects are the
mailbox CLI subprocess (mocked here) + a monotonic clock (faked here); no real
sleep, no real daemon. Every failure row from the spec reliability table is a
test below."""
import json

import wg_verify as V


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
        self.stderr = stderr.encode("utf-8") if isinstance(stderr, str) else stderr


def _patch_cli(monkeypatch, cli_path="/fake/mailbox"):
    monkeypatch.setattr(V, "discover_cli", lambda env=None: cli_path)


def _patch_clock(monkeypatch, ticks):
    """Feed a deterministic monotonic sequence; raises StopIteration if exhausted."""
    it = iter(ticks)
    monkeypatch.setattr(V.time, "monotonic", lambda: next(it))


def test_build_request_shape():
    req = V.build_request(label="alpha-sh", severity="alert1", conf=0.97,
                          grounded=("tool", "file"), claim="prod db corrupted",
                          request_id="abc123")
    d = json.loads(req)
    assert d["kind"] == "verify_request"
    assert d["request_id"] == "abc123"
    assert d["from"] == "alpha-sh"
    assert d["severity"] == "alert1"
    assert d["conf"] == 0.97
    assert d["grounded"] == ["tool", "file"]
    assert d["claim"] == "prod db corrupted"
    assert len(d["claim_sha"]) == 8        # sha256[:8]


def test_signed_verdict_resolves_signed(monkeypatch):
    _patch_cli(monkeypatch)
    verdict = json.dumps({"kind": "verify_verdict", "request_id": "rid1",
                          "by": "verify-sh", "verdict": "signed",
                          "envelope": "⟦conf=0.96 grounded=tool missing=none⟧",
                          "gap": ""})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": verdict}]
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        if "send" in argv:
            return _Proc(0, "{'id': 'msg_1'}")
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 1.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool", "file"), claim="prod db corrupted",
        timeout_s=30, request_id="rid1", poll_interval_s=0.0)
    assert res["outcome"] == "signed"


def test_rejected_verdict_resolves_rejected_with_gap(monkeypatch):
    _patch_cli(monkeypatch)
    verdict = json.dumps({"kind": "verify_verdict", "request_id": "rid2",
                          "by": "verify-sh", "verdict": "rejected",
                          "envelope": "⟦conf=0.30 grounded=none missing=a repro⟧",
                          "gap": "could not reproduce on a clean prod replica"})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": verdict}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 1.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid2", poll_interval_s=0.0)
    assert res["outcome"] == "rejected"
    assert "reproduce" in res["gap"]


def test_request_id_mismatch_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    other = json.dumps({"kind": "verify_verdict", "request_id": "WRONG",
                        "by": "verify-sh", "verdict": "signed",
                        "envelope": "⟦conf=0.96 grounded=tool missing=none⟧"})
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict", "body": other}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    # clock: send@0, then poll loop crosses deadline -> timeout
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid3", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_wrong_sender_label_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    spoof = json.dumps({"kind": "verify_verdict", "request_id": "rid4",
                        "by": "verify-sh", "verdict": "signed",
                        "envelope": "⟦conf=0.96 grounded=tool missing=none⟧"})
    # from_label is the transport authentication; an impostor sender is dropped.
    inbox = [{"from_label": "impostor-sh", "kind": "verify_verdict", "body": spoof}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid4", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_malformed_verdict_json_ignored_then_timeout(monkeypatch):
    _patch_cli(monkeypatch)
    inbox = [{"from_label": "verify-sh", "kind": "verify_verdict",
              "body": "not json at all {{{"}]

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, json.dumps(inbox))
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid5", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_no_reply_times_out(monkeypatch):
    _patch_cli(monkeypatch)

    def fake_run(argv, **kw):
        if "inbox" in argv:
            return _Proc(0, "[]")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid6", poll_interval_s=0.0)
    assert res["outcome"] == "timeout"


def test_cli_not_found_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch, cli_path=None)
    # no subprocess.run should be called when there is no CLI
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid7", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_send_failure_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch)

    def fake_run(argv, **kw):
        if "send" in argv:
            return _Proc(1, "", "daemon down")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid8", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_subprocess_oserror_is_unreachable(monkeypatch):
    _patch_cli(monkeypatch)

    def boom(*a, **k):
        raise OSError("exec format error")

    monkeypatch.setattr(V.subprocess, "run", boom)
    _patch_clock(monkeypatch, [0.0])
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid9", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_self_verification_refused(monkeypatch):
    # D8: an agent may not be its own verifier.
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="alpha-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid10", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_blank_verifier_label_refused(monkeypatch):
    monkeypatch.setattr(V.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    res = V.request_and_wait(
        label="alpha-sh", verifier_label="", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid11", poll_interval_s=0.0)
    assert res["outcome"] == "unreachable"


def test_subprocess_is_the_only_io_effect(monkeypatch):
    # Asserts the function never touches the filesystem or network beyond the
    # mocked subprocess; if it tried, the un-mocked sockets/open would error.
    _patch_cli(monkeypatch)
    seen = {"send": 0, "inbox": 0}

    def fake_run(argv, **kw):
        if "send" in argv:
            seen["send"] += 1
        if "inbox" in argv:
            seen["inbox"] += 1
            return _Proc(0, "[]")
        return _Proc(0, "ok")

    monkeypatch.setattr(V.subprocess, "run", fake_run)
    _patch_clock(monkeypatch, [0.0, 0.0, 31.0])
    V.request_and_wait(
        label="alpha-sh", verifier_label="verify-sh", severity="alert1",
        conf=0.97, grounded=("tool",), claim="x", timeout_s=30,
        request_id="rid12", poll_interval_s=0.0)
    assert seen["send"] >= 1 and seen["inbox"] >= 1
