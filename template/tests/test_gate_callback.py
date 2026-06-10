import wg_gate
import wg_policy


def _profile(tmp_path, enforce=True, min_conf=75, badge=True):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  min_confidence: %d\n"
        "  show_confidence_badge: %s\n" % (str(enforce).lower(), min_conf, str(badge).lower())
    )
    return tmp_path


def test_disabled_enforce_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, enforce=False)))
    assert wg_gate.gate(response_text="The DB is down.\n⟦conf=0.9 grounded=tool missing=none⟧") is None


def test_chatter_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    assert wg_gate.gate(response_text="thanks!") is None


def test_low_confidence_claim_is_replaced_with_abstention(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, min_conf=75)))
    out = wg_gate.gate(response_text="The outage is X.\n⟦conf=0.50 grounded=tool missing=a prod log⟧")
    assert out is not None
    assert "Holding back" in out and "a prod log" in out


def test_ungrounded_claim_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    out = wg_gate.gate(response_text="It is definitely a memory leak.\n⟦conf=0.95 grounded=none missing=a heap dump⟧")
    assert out is not None and "Holding back" in out


def test_claim_without_envelope_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    out = wg_gate.gate(response_text="The root cause is a race in the scheduler at line 88 of run.py.")
    assert out is not None and "Holding back" in out


def test_high_confidence_grounded_claim_passes_with_badge(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, min_conf=75, badge=True)))
    out = wg_gate.gate(response_text="The fix is api/pay.py:88.\n⟦conf=0.88 grounded=tool,file missing=none⟧")
    # envelope stripped, badge added, no envelope left
    assert out is not None
    assert "⟦" not in out and "88%" in out and "api/pay.py:88" in out


def test_never_raises_even_on_internal_bug(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # Force an internal error by monkeypatching decide to blow up.
    monkeypatch.setattr(wg_gate.wg_policy, "decide", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = wg_gate.gate(response_text="A claim that should error.\n⟦conf=0.9 grounded=tool missing=none⟧")
    assert isinstance(out, str) and "Holding back" in out      # fail closed, no exception


def test_register_wires_transform_llm_output():
    seen = {}

    class Ctx:
        def register_hook(self, name, cb):
            seen[name] = cb

    wg_gate.register(Ctx())
    assert "transform_llm_output" in seen


def _gate_log(tmp_path):
    # Read the gate.log this plan's tests assert against. The classifier plan
    # (position 2) reads the log inline via .read_text(); this plan factors that
    # into one helper. If position 2 already defined a `_gate_log`, drop this
    # definition and reuse theirs (the pre-flight flags that case).
    return (tmp_path / "local" / "war_room" / "gate.log").read_text(encoding="utf-8")


def _sev_profile(tmp_path, table_lines, enforce=True, min_conf=75):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  min_confidence: %d\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n%s" % (str(enforce).lower(), min_conf, table_lines)
    )
    return tmp_path


def test_alert1_below_severity_floor_abstains_endtoend(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.90 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "Holding back" in out


def test_alert1_clears_floor_passes_with_badge_endtoend(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "⟦" not in out and "97%" in out


def test_alert1_audit_records_sev(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_sev_profile(
        tmp_path, "    alert1: 95\n    default: 75\n")))
    wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    line = _gate_log(tmp_path)
    assert "sev=alert1" in line
    # verify field present (none on a no-verifier path)
    assert "verify=none" in line


def test_chatter_branch_now_logs_verdict_chatter(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # chatter -> gate returns None, but it MUST now write a verdict=chatter line.
    assert wg_gate.gate(response_text="thanks!") is None
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert logf.is_file(), "chatter branch must log so under-gating is visible"
    line = logf.read_text()
    assert "verdict=chatter" in line
    assert "reason=chatter" in line
    assert "matched=thanks" in line


def test_claim_branch_logs_verdict_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    wg_gate.gate(response_text="The fix is api/pay.py:88.\n⟦conf=0.88 grounded=tool,file missing=none⟧")
    line = (tmp_path / "local" / "war_room" / "gate.log").read_text()
    assert "verdict=claim" in line
    assert "api/pay.py" not in line     # body never logged, only its hash


def test_chatter_log_does_not_change_return_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # A bare ack is unchanged after stray-envelope strip -> still returns None.
    assert wg_gate.gate(response_text="ok") is None


def _verifier_profile(tmp_path, enforce=True):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "    default: 75\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: verify-sh\n"
        "  verifier_timeout_s: 30\n" % str(enforce).lower()
    )
    return tmp_path


_ALERT1 = ("prod db is corrupted\n"
           "⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")


def test_alert1_signed_verdict_posts_double_signed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "signed", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "⟦" not in out and "97%" in out
    line = _gate_log(tmp_path)
    assert "sev=alert1" in line and "verify=signed" in line


def test_alert1_rejected_verdict_abstains_with_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(
        wg_gate.wg_verify, "request_and_wait",
        lambda **k: {"outcome": "rejected", "gap": "could not reproduce", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out and "could not reproduce" in out
    assert "verify=rejected" in _gate_log(tmp_path)


def test_alert1_timeout_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "timeout", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out
    assert "verify=timeout" in _gate_log(tmp_path)


def test_alert1_unreachable_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: {"outcome": "unreachable", "gap": "", "by": "verify-sh"})
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out
    assert "verify=unreachable" in _gate_log(tmp_path)


def test_below_severity_floor_never_calls_verifier(tmp_path, monkeypatch):
    # The verifier handshake only runs AFTER a PASS; a claim that abstains on the
    # floor must not pay the verifier latency.
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(AssertionError("verifier called")))
    out = wg_gate.gate(
        response_text="prod db is corrupted\n"
                      "⟦conf=0.90 grounded=tool,file missing=none sev=alert1⟧")
    assert out is not None and "Holding back" in out


def test_below_require_verifier_at_passes_without_verifier(tmp_path, monkeypatch):
    # alert2 is below require_verifier_at=alert1, so no handshake; clears its
    # floor (alert2 not in table -> default 75) and posts.
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(AssertionError("verifier called")))
    out = wg_gate.gate(
        response_text="staging is slow\n"
                      "⟦conf=0.80 grounded=tool missing=none sev=alert2⟧")
    assert out is not None and "⟦" not in out and "80%" in out
    assert "verify=none" in _gate_log(tmp_path)


def test_verifier_exception_fails_closed(tmp_path, monkeypatch):
    # If wg_verify itself throws, the top-level try/except still abstains; the
    # callback never raises (extends the fail-closed contract to the verifier).
    monkeypatch.setenv("HERMES_HOME", str(_verifier_profile(tmp_path)))
    monkeypatch.setattr(wg_gate.wg_verify, "request_and_wait",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = wg_gate.gate(response_text=_ALERT1)
    assert isinstance(out, str) and "Holding back" in out


def test_blank_verifier_label_at_gated_severity_abstains(tmp_path, monkeypatch):
    # require_verifier_at=alert1 but verifier_label blank => misconfig => abstain.
    # wg_verify.request_and_wait returns unreachable for a blank label (T5), so
    # the real (un-mocked) call is fine here and must not hit a subprocess.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: \n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    out = wg_gate.gate(response_text=_ALERT1)
    assert out is not None and "Holding back" in out


def test_hybrid_raises_untagged_to_alert2_floor(tmp_path, monkeypatch):
    # hybrid mode: an untagged claim with a prod cue is held to the alert2 floor.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_inference: hybrid\n"
        "  severity_thresholds:\n"
        "    alert2: 90\n"
        "    default: 75\n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # clears default 75 but not the raised alert2 floor 90 -> held back
    out = wg_gate.gate(
        response_text="the prod database is down\n"
                      "⟦conf=0.80 grounded=tool,file missing=none⟧")
    assert out is not None and "Holding back" in out
    assert "sev=alert2" in _gate_log(tmp_path)


def test_explicit_mode_does_not_raise(tmp_path, monkeypatch):
    # default (explicit) mode: the same claim is held only to the default floor.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: true\n"
        "  label: alpha-sh\n"
        "  min_confidence: 75\n"
        "  show_confidence_badge: true\n"
        "  severity_thresholds:\n"
        "    alert2: 90\n"
        "    default: 75\n")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    out = wg_gate.gate(
        response_text="the prod database is down\n"
                      "⟦conf=0.80 grounded=tool,file missing=none⟧")
    assert out is not None and "⟦" not in out and "80%" in out
    assert "sev=default" in _gate_log(tmp_path)
