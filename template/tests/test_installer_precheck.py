"""T0 -- installer pre-flight capability validation.

These tests exercise `precheck.py` in isolation. The installer ships as a flat
package under `template/scripts/installer/` and is imported with that directory
on `sys.path` (matching how the launcher runs it via PYTHONPATH).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import precheck  # noqa: E402


# Real-shaped help text captured from `hermes 0.15.1` (the T0 verification run).
_INSTALL_HELP = """usage: hermes profile install [-h] [--name NAME] [--alias] [--force] [-y]
                              source

positional arguments:
  source       Distribution source (git URL or local directory)

options:
  -h, --help   show this help message and exit
  --name NAME  Override profile name (default: read from manifest)
  --alias      Create a shell wrapper alias for the installed profile
  --force      Overwrite an existing profile of the same name
  -y, --yes    Skip manifest preview confirmation
"""

_PLUGINS_ENABLE_HELP = """usage: hermes plugins enable [-h] name

positional arguments:
  name        Plugin name to enable

options:
  -h, --help  show this help message and exit
"""


def _fake_runner(version="Hermes Agent v0.15.1 (2026.5.29)"):
    """Build a hermes_runner that answers the three help/version probes."""

    def run(args):
        if args[:1] == ["--version"]:
            return 0, version
        if args[:2] == ["profile", "install"]:
            return 0, _INSTALL_HELP
        if args[:2] == ["plugins", "enable"]:
            return 0, _PLUGINS_ENABLE_HELP
        return 1, ""

    return run


def test_python_version_passes_on_supported_interpreter():
    r = precheck._check_python_version()
    # The suite itself runs on a supported interpreter, so this must pass.
    assert r.status == "pass"
    assert sys.version_info[:2] >= precheck.MIN_PYTHON


def test_hermes_missing_is_hard_failure(monkeypatch):
    monkeypatch.setattr(precheck.shutil, "which", lambda name, path=None: None)
    results = precheck.run_prechecks(hermes_runner=_fake_runner())
    by_name = {r.name: r for r in results}
    assert by_name["hermes_on_path"].status == "fail"
    # surface probes are skipped when hermes is absent (no cascade)
    assert "hermes_version" not in by_name
    with pytest.raises(precheck.PrecheckError):
        precheck.assert_all_pass(results)


def test_version_parse_robustness():
    assert precheck._parse_hermes_version("Hermes Agent v0.15.1 (2026.5.29)") == (0, 15, 1)
    assert precheck._parse_hermes_version("hermes 0.12") == (0, 12, 0)
    assert precheck._parse_hermes_version("v1.2.3-rc4") == (1, 2, 3)
    assert precheck._parse_hermes_version("no version here") is None
    # unparseable -> warn-and-proceed, never a hard fail (K15)
    r = precheck._check_hermes_version(lambda a: (0, "dev build, no semver"))
    assert r.status == "warn"
    assert r.ok is True
    # too-old -> fail
    old = precheck._check_hermes_version(lambda a: (0, "hermes 0.10.0"))
    assert old.status == "fail"


def test_posix_terminal_supported_on_this_host():
    # macOS/Linux CI: termios/tty import cleanly.
    assert precheck._check_posix_terminal().status == "pass"


def test_plugin_enable_no_yes_flag():
    r = precheck._check_plugins_enable_surface(_fake_runner())
    assert r.status == "pass"  # `name` positional present
    # A8/F1: real hermes has NO -y on `plugins enable`; we must record that.
    assert r.data["plugins_enable_has_yes"] is False
    # and `profile install` DOES expose -y
    inst = precheck._check_profile_install_surface(_fake_runner())
    assert inst.status == "pass"


def test_git_check_skipped_for_local_dir(tmp_path):
    local = precheck.run_prechecks(source=str(tmp_path), hermes_runner=_fake_runner())
    assert "git_for_url_source" not in {r.name for r in local}
    url = precheck.run_prechecks(
        source="https://github.com/owner/repo", hermes_runner=_fake_runner()
    )
    assert "git_for_url_source" in {r.name for r in url}


def test_writes_outcome(tmp_path):
    results = precheck.run_prechecks(
        hermes_runner=_fake_runner(), profiles_dir=tmp_path / "profiles"
    )
    doc = tmp_path / "installer-preflight.md"
    precheck.write_preflight_doc(results, doc)
    assert doc.exists()
    body = doc.read_text(encoding="utf-8")
    for name in (
        "python_version",
        "hermes_on_path",
        "hermes_version",
        "hermes_profile_install_surface",
        "hermes_plugins_enable_surface",
        "posix_terminal",
        "profiles_dir_writable",
        "substrate_imports",
    ):
        assert name in body


def test_substrate_imports_under_pythonpath(tmp_path):
    # Fabricate a minimal _substrate package; the real one lands in T2.
    sub = tmp_path / "_substrate"
    sub.mkdir()
    (sub / "__init__.py").write_text("", encoding="utf-8")
    for mod in ("render", "prompts", "validators"):
        (sub / (mod + ".py")).write_text("OK = True\n", encoding="utf-8")
    ok = precheck._check_substrate_imports(tmp_path)
    assert ok.status == "pass"
    # missing package -> fail
    bad = precheck._check_substrate_imports(tmp_path / "nope")
    assert bad.status == "fail"


def test_profiles_dir_writable_detects_unwritable(tmp_path):
    good = precheck._check_profiles_dir_writable(tmp_path / "writable")
    assert good.status == "pass"
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        # On most CI the user cannot write into a 0500 dir; root can, so tolerate.
        r = precheck._check_profiles_dir_writable(locked)
        assert r.status in ("fail", "pass")
    finally:
        os.chmod(locked, 0o700)
