"""T4 — run_setup wires enroll.bootstrap + the warroom.label field.

enroll.bootstrap is monkeypatched to a recorder so these tests never discover a
real CLI or write to ~/.claude.
"""
import io
import shutil
from pathlib import Path

from warroom_setup import enroll, selectables, setup


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


class _Recorder:
    def __init__(self, status="ok"):
        self.calls = []
        self.status = status

    def __call__(self, profile_root, board, label, dry_run=False, env=None):
        self.calls.append({"profile_root": profile_root, "board": board, "label": label})
        return enroll.EnrollState(board=board, label=label, cli_path=None,
                                  mailbox_home="", socket_path="", last_check_ts=0.0,
                                  status=self.status)


def _run(prof, monkeypatch, rec, extra_lines=""):
    monkeypatch.setenv("HOME", str(prof.parent.parent / "home"))
    monkeypatch.setattr(enroll, "bootstrap", rec)
    instream = io.StringIO(
        "zed\nZed\n\nsk-anthropic\ndt-token\n123,456\n" + extra_lines
    )
    toggle_in = io.StringIO("\n\n\n\n\n")
    return setup.run_setup(prof, yes=False, reconfigure=False,
                           in_stream=instream, out_stream=io.StringIO(),
                           toggle_in_stream=toggle_in)


def test_run_setup_calls_enroll_bootstrap_when_toggle_on(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _Recorder()
    rc = _run(prof, monkeypatch, rec, extra_lines="shared\n")  # board=shared
    assert rc == 0
    assert len(rec.calls) == 1
    assert rec.calls[0]["board"] == "shared"


def test_run_setup_skips_enroll_when_toggle_off(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _Recorder()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(enroll, "bootstrap", rec)
    instream = io.StringIO("zed\nZed\n\nsk-anthropic\n")
    # deselect warroom.enroll: WarRoom stage is last; toggle item 1 off via the
    # numbered fallback. Simpler: drive via answers replay with enroll absent.
    # Here we deselect by toggling in the WarRoom stage.
    toggle_in = io.StringIO("\n\n\n1\n\n")  # toggle first WarRoom entry (enroll) off
    setup.run_setup(prof, yes=False, reconfigure=False, in_stream=instream,
                    out_stream=io.StringIO(), toggle_in_stream=toggle_in)
    assert rec.calls == []


def test_run_setup_label_defaults_to_handle(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _Recorder()
    # handle line blank -> defaults to agent_name "zed"; no label line -> default
    _run(prof, monkeypatch, rec, extra_lines="shared\n\n\n")
    assert rec.calls[0]["label"] == "zed"


def test_run_setup_label_honors_override_value(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _Recorder()
    # order after ANTHROPIC/DISCORD: board, min_confidence, label
    _run(prof, monkeypatch, rec, extra_lines="shared\n80\nalpha-sh\n")
    assert rec.calls[0]["label"] == "alpha-sh"


def test_run_setup_prints_cli_not_found_warning_with_install_pointer(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _Recorder(status="cli-not-found")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(enroll, "bootstrap", rec)
    out = io.StringIO()
    instream = io.StringIO("zed\nZed\n\nsk-anthropic\ndt-token\n123,456\nshared\n")
    setup.run_setup(prof, yes=False, reconfigure=False, in_stream=instream,
                    out_stream=out, toggle_in_stream=io.StringIO("\n\n\n\n\n"))
    assert "mailbox CLI not found" in out.getvalue()
    assert "Installing the mailbox runtime" in out.getvalue()


def test_run_setup_field_order_appends_label_at_end():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    assert ids.index("warroom.label") > ids.index("warroom.min_confidence")
