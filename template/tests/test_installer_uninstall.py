"""T11 -- uninstall subcommand."""
import io
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install as awr  # noqa: E402
import subprocess_runner as sr  # noqa: E402


def _profile(root, *, user_data=False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text("name: alpha-sh\n", encoding="utf-8")
    (root / "warroom_setup").mkdir()
    (root / "warroom_setup" / "__init__.py").write_text("", encoding="utf-8")
    if user_data:
        (root / "local").mkdir()
        (root / "local" / "agent.json").write_text("{}", encoding="utf-8")
    return root


class _FakeSidecar:
    def __init__(self):
        self.cleaned = False

    def cleanup(self):
        self.cleaned = True


def _ok_runner(captured):
    def run(cmd, *, timeout, tee=None):
        captured["cmd"] = cmd
        return sr.CommandResult(returncode=0, lines=["deleted"], duration_s=0.1)
    return run


def test_invokes_hermes_profile_delete(tmp_path):
    _profile(tmp_path / "alpha-sh")
    captured = {}
    out = io.StringIO()
    rc = awr.uninstall("alpha-sh", profiles_root=tmp_path,
                       hermes_runner=_ok_runner(captured), sidecar=_FakeSidecar(), out=out)
    assert rc == 0
    assert captured["cmd"] == ["hermes", "profile", "delete", "alpha-sh", "-y"]


def test_prompts_confirm_on_user_data(tmp_path):
    _profile(tmp_path / "alpha-sh", user_data=True)
    captured = {}
    asked = {"n": 0}

    def deny(prompt):
        asked["n"] += 1
        return False

    rc = awr.uninstall("alpha-sh", profiles_root=tmp_path,
                       hermes_runner=_ok_runner(captured), confirm=deny,
                       sidecar=_FakeSidecar(), out=io.StringIO())
    assert asked["n"] == 1
    assert rc == 3
    assert "cmd" not in captured  # delete NOT invoked when denied


def test_cleans_sidecar(tmp_path):
    _profile(tmp_path / "alpha-sh")
    sc = _FakeSidecar()
    awr.uninstall("alpha-sh", profiles_root=tmp_path,
                  hermes_runner=_ok_runner({}), sidecar=sc, out=io.StringIO())
    assert sc.cleaned is True


def test_warns_about_settings_json(tmp_path):
    _profile(tmp_path / "alpha-sh")
    out = io.StringIO()
    awr.uninstall("alpha-sh", profiles_root=tmp_path,
                  hermes_runner=_ok_runner({}), sidecar=_FakeSidecar(), out=out)
    assert "~/.claude/settings.json" in out.getvalue()
    assert "NOT auto-removed" in out.getvalue()


def test_exits_nonzero_when_profile_missing(tmp_path):
    captured = {}
    out = io.StringIO()
    rc = awr.uninstall("ghost", profiles_root=tmp_path,
                       hermes_runner=_ok_runner(captured), sidecar=_FakeSidecar(), out=out)
    assert rc != 0
    assert "cmd" not in captured  # no delete attempted
    assert "not found" in out.getvalue()
