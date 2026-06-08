"""T6.5 — run_setup injects the war-room coordination rule into decisions.md."""
import io
import shutil
from pathlib import Path

from warroom_setup import enroll, setup


def _fake_profile(tmp_path):
    src = Path(__file__).resolve().parents[1]
    prof = tmp_path / "profiles" / "zed"
    prof.mkdir(parents=True)
    for d in ("persona", "templates", "shared"):
        shutil.copytree(src / d, prof / d)
    shutil.copy2(src / "manifest.json", prof / "manifest.json")
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n")
    (prof / "config.yaml").write_text("model:\n  name: opus\n")
    return prof


def _noop_bootstrap(pr, b, l, dry_run=False, env=None):
    return enroll.EnrollState(b, l, None, "", "", 0.0, "ok")


def _run(prof, monkeypatch, enroll_on=True):
    monkeypatch.setenv("HOME", str(prof.parent.parent / "home"))
    monkeypatch.setattr(enroll, "bootstrap", _noop_bootstrap)
    toggle = io.StringIO("\n\n\n\n\n") if enroll_on else io.StringIO("\n\n\n1\n\n")
    instream = io.StringIO("zed\nZed\n\nsk-anthropic\ndt-token\n123,456\nshared\n")
    return setup.run_setup(prof, yes=False, reconfigure=False, in_stream=instream,
                           out_stream=io.StringIO(), toggle_in_stream=toggle)


def _decisions(prof):
    return (prof / "local" / "persona" / "decisions.md").read_text(encoding="utf-8")


def test_persona_decision_injected_when_warroom_enroll_on(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    _run(prof, monkeypatch, enroll_on=True)
    text = _decisions(prof)
    assert "mailbox claim-lane" in text
    assert "mailbox release-lane" in text


def test_persona_decision_skipped_when_warroom_enroll_off(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    _run(prof, monkeypatch, enroll_on=False)
    text = _decisions(prof)
    assert "mailbox claim-lane" not in text


def test_persona_decision_is_idempotent(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    _run(prof, monkeypatch, enroll_on=True)
    _run(prof, monkeypatch, enroll_on=True)
    text = _decisions(prof)
    assert text.count("mailbox claim-lane") == 1
