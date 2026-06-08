import io
from warroom_setup import selectables, render


def _stages():
    return selectables.build_stages(selectables.TOGGLES)


def test_numbered_fallback_toggles_then_accepts(monkeypatch):
    stages = _stages()
    # Stage Persona: toggle entry 1 on, Enter; then Enter through remaining stages; then Enter to apply.
    instream = io.StringIO("1\n\n\n\n\n")
    outstream = io.StringIO()
    result = render._numbered_fallback(stages, set(), instream, outstream)
    first = stages[0].entries[0].id
    assert first in result


def test_run_wizard_uses_fallback_when_not_tty():
    stages = _stages()
    instream = io.StringIO("\n\n\n\n\n")     # accept defaults each stage + apply
    outstream = io.StringIO()                # StringIO.isatty() is False
    result = render.run_wizard(stages, {"model.opus"}, in_stream=instream, out_stream=outstream)
    assert "model.opus" in result


def test_decode_key_arrows_and_enter():
    assert render._decode_key("\x1b[A") == "up"
    assert render._decode_key("\r") == "enter"
    assert render._decode_key(" ") == "space"
    assert render._decode_key("\x1b") == "esc"
