"""T1 -- launcher + argparse skeleton.

The launcher (`template/install.sh`) resolves python3, puts the installer dir on
PYTHONPATH, and execs `python3 -m awr_install`. The repo-root `install.sh` is a
real-file shim that chains to it. Tests inject a fake interpreter via AWR_PYTHON
to observe the environment the launcher constructs without running the wizard.
"""
import os
import subprocess
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
TEMPLATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TEMPLATE_DIR.parent
TEMPLATE_LAUNCHER = TEMPLATE_DIR / "install.sh"
ROOT_SHIM = REPO_ROOT / "install.sh"

if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install  # noqa: E402


def _fake_python(tmp_path):
    """A fake `python3` that just echoes the PYTHONPATH it was handed."""
    fake = tmp_path / "fakepy"
    fake.write_text("#!/usr/bin/env bash\necho \"PYTHONPATH=$PYTHONPATH\"\n")
    fake.chmod(0o755)
    return fake


def test_resolves_python3_and_pythonpath(tmp_path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["AWR_PYTHON"] = str(_fake_python(tmp_path))
    out = subprocess.run(
        ["bash", str(TEMPLATE_LAUNCHER)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    assert out.returncode == 0
    assert "PYTHONPATH=%s" % INSTALLER_DIR in out.stdout
    # installer dir is the first entry
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("PYTHONPATH=")][0]
    value = line.split("=", 1)[1]
    assert value.split(":")[0] == str(INSTALLER_DIR)


def test_preserves_existing_pythonpath(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = "/foo/bar"
    env["AWR_PYTHON"] = str(_fake_python(tmp_path))
    out = subprocess.run(
        ["bash", str(TEMPLATE_LAUNCHER)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    assert out.returncode == 0
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("PYTHONPATH=")][0]
    value = line.split("=", 1)[1]
    assert value.split(":")[0] == str(INSTALLER_DIR)
    assert "/foo/bar" in value.split(":")


def test_help_exits_zero():
    out = subprocess.run(
        ["bash", str(TEMPLATE_LAUNCHER), "--help"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    assert out.returncode == 0
    assert "usage" in out.stdout.lower()


def test_repo_root_shim_invokes_template_launcher():
    assert ROOT_SHIM.is_file() and not ROOT_SHIM.is_symlink()
    out = subprocess.run(
        ["bash", str(ROOT_SHIM), "--help"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    assert out.returncode == 0
    assert "usage" in out.stdout.lower()


def test_argparse_accepts_all_flags():
    parser = awr_install.build_parser()
    ns = parser.parse_args([
        "--source", "/tmp/template",
        "--name", "alpha-sh",
        "--board", "shared",
        "--label", "alpha-sh",
        "--discord", "--slack",
        "--agent-name", "alpha-sh",
        "--display-name", "Alpha",
        "--handle", "alpha_op",
        "--discord-allowed-users", "u1",
        "--discord-allowed-users", "u2",
        "--min-confidence", "80",
        "--model", "sonnet",
        "--stage-timeout", "120",
        "--force", "--dry-run", "--verbose",
        "--discord-channel-id", "12345678901234567",
        "--anthropic-key-env", "ANTHROPIC_KEY",
        "--discord-token-env", "DISCORD_TOKEN",
        "--slack-app-token-file", "/tmp/app.tok",
        "--slack-bot-token-file", "/tmp/bot.tok",
    ])
    assert ns.name == "alpha-sh"
    assert ns.board == "shared"
    assert ns.discord and ns.slack
    assert ns.agent_name == "alpha-sh"
    assert ns.discord_allowed_users == ["u1", "u2"]
    assert ns.min_confidence == 80
    assert ns.model == "sonnet"
    assert ns.stage_timeout == 120.0
    assert ns.force and ns.dry_run and ns.verbose
    assert ns.anthropic_key_env == "ANTHROPIC_KEY"
    assert ns.slack_app_token_file == "/tmp/app.tok"


def test_uninstall_and_resume_flags_parse():
    parser = awr_install.build_parser()
    assert parser.parse_args(["--uninstall", "alpha-sh"]).uninstall == "alpha-sh"
    assert parser.parse_args(["--resume"]).resume is True


def test_help_invocation_via_main_exits_zero():
    # argparse raises SystemExit(0) on --help even when called in-process.
    try:
        awr_install.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover
        raise AssertionError("--help did not exit")
