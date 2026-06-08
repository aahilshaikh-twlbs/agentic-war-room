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
