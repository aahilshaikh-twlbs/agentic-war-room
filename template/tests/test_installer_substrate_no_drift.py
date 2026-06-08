"""T2 -- vendored substrate drift guard.

The installer ships byte-identical copies of seven warroom_setup TUI modules in
scripts/installer/_substrate/. These tests enforce that the copies (a) match
their originals byte-for-byte and (b) import cleanly as a `_substrate.*` package
under the installer dir on PYTHONPATH -- the exact contract the launcher uses.
"""
import filecmp
import os
import subprocess
import sys
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parents[1]
WARROOM = TEMPLATE_DIR / "warroom_setup"
INSTALLER_DIR = TEMPLATE_DIR / "scripts" / "installer"
SUBSTRATE = INSTALLER_DIR / "_substrate"

# The manifest -- daemon_probe.py is deliberately excluded (C22).
SUBSTRATE_FILES = [
    "render.py",
    "prompts.py",
    "state.py",
    "selectables.py",
    "validators.py",
    "discord_walkthrough.py",
    "slack_walkthrough.py",
]


def _run_import(code, *, cwd):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(INSTALLER_DIR)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


@pytest.mark.parametrize("name", SUBSTRATE_FILES)
def test_byte_identical(name):
    src = WARROOM / name
    dst = SUBSTRATE / name
    assert dst.exists(), "missing vendored file %s; run sync_substrate.sh" % name
    assert filecmp.cmp(str(src), str(dst), shallow=False), (
        "%s drifted from warroom_setup/%s; run sync_substrate.sh" % (name, name)
    )


def test_imports_cleanly():
    code = (
        "import _substrate.render, _substrate.prompts, _substrate.state, "
        "_substrate.selectables, _substrate.validators, "
        "_substrate.discord_walkthrough, _substrate.slack_walkthrough; "
        "print('ok')"
    )
    res = _run_import(code, cwd=INSTALLER_DIR)
    assert res.returncode == 0, res.stdout
    assert "ok" in res.stdout


def test_slack_walkthrough_imports_step_from_substrate():
    # C21: slack_walkthrough does `from .discord_walkthrough import Step`; that
    # must resolve WITHIN _substrate, not leak in warroom_setup's Step.
    code = (
        "import _substrate.slack_walkthrough as sw, "
        "_substrate.discord_walkthrough as dw; "
        "assert sw.Step is dw.Step, 'Step identity mismatch'; "
        "assert sw.Step.__module__ == '_substrate.discord_walkthrough', sw.Step.__module__; "
        "print('ok')"
    )
    res = _run_import(code, cwd=INSTALLER_DIR)
    assert res.returncode == 0, res.stdout
    assert "ok" in res.stdout


def test_imports_under_random_cwd(tmp_path):
    # The launcher cd's into the installer dir, but imports must not depend on
    # cwd -- only on PYTHONPATH. Run from an unrelated directory.
    res = _run_import("import _substrate.render; print('ok')", cwd=tmp_path)
    assert res.returncode == 0, res.stdout
    assert "ok" in res.stdout
