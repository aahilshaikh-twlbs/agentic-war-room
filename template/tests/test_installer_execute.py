"""T6 -- execute phase: in-process orchestration.

Stage-1 (hermes install) and Stage-4 (plugins enable) subprocesses are faked.
Stages 2/3/5 run in-process against the REAL profile warroom_setup modules
(injected via `importer`) so we exercise the actual setup.write_env /
agent_model.save / patch_*_block / enroll.bootstrap code paths.
"""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install as awr  # noqa: E402
import in_process_orchestrator as orch  # noqa: E402
import subprocess_runner as sr  # noqa: E402
from _substrate.discord_walkthrough import DiscordCreds  # noqa: E402
from _substrate.slack_walkthrough import SlackCreds  # noqa: E402

import warroom_setup.agent_model as am_mod  # noqa: E402
import warroom_setup.enroll as enroll_mod  # noqa: E402
import warroom_setup.setup as setup_mod  # noqa: E402

_FAKE_DISCORD = "FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL"


def real_importer(profile_root):
    return SimpleNamespace(setup=setup_mod, agent_model=am_mod, enroll=enroll_mod)


def ok(lines=None, dur=0.1):
    return sr.CommandResult(returncode=0, lines=lines or ["ok"], duration_s=dur)


def fail(rc=1, lines=None):
    return sr.CommandResult(returncode=rc, lines=lines or ["error: boom"], duration_s=0.1)


def make_answers(name="alpha-sh", **over):
    base = dict(
        source="/src/template",
        profile_name=name,
        channels={"discord"},
        discord_creds=DiscordCreds(bot_token=_FAKE_DISCORD, channel_id="12345678901234567"),
        slack_creds=None,
        anthropic_key="sk-ant-" + "x" * 40,
        agent_name=name,
        display_name="Alpha",
        handle=name,
        discord_allowed_users=["u1"],
        min_confidence=80,
        model="opus",
        board="shared",
        label=name,
    )
    base.update(over)
    return awr.InstallerAnswers(**base)


def run(answers, tmp_path, *, hermes=None, plugin=None, **kw):
    return orch.execute(
        answers,
        profiles_root=tmp_path,
        hermes_runner=hermes or (lambda c, *, timeout, tee=None: ok()),
        plugin_runner=plugin or (lambda c, *, timeout, tee=None: ok()),
        importer=real_importer,
        out=kw.pop("out", io.StringIO()),
        **kw,
    )


# --------------------------------------------------------------------------- #
def test_dry_run_no_subprocesses(tmp_path):
    called = {"h": 0, "p": 0}

    def h(c, *, timeout, tee=None):
        called["h"] += 1
        return ok()

    def p(c, *, timeout, tee=None):
        called["p"] += 1
        return ok()

    out = io.StringIO()
    res = orch.execute(make_answers(), dry_run=True, profiles_root=tmp_path,
                       hermes_runner=h, plugin_runner=p, importer=real_importer, out=out)
    assert res.exit_code == 0
    assert called == {"h": 0, "p": 0}
    assert "dry-run" in out.getvalue()


def test_stage1_correct_hermes_args(tmp_path):
    captured = {}

    def h(c, *, timeout, tee=None):
        captured["cmd"] = c
        return ok()

    res = run(make_answers(source="/path/tmpl", name="alpha-sh"), tmp_path, hermes=h)
    assert captured["cmd"] == [
        "hermes", "profile", "install", "/path/tmpl",
        "--name", "alpha-sh", "--alias", "--force", "-y",
    ]
    assert 1 in res.completed_stages


def test_stage2_writes_env_with_secrets(tmp_path):
    a = make_answers(anthropic_key="sk-ant-" + "k" * 40)
    run(a, tmp_path)
    env = (tmp_path / a.profile_name / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-ant-" in env
    assert "DISCORD_BOT_TOKEN=" + _FAKE_DISCORD in env
    assert "DISCORD_HOME_CHANNEL=12345678901234567" in env
    assert "DISCORD_ALLOWED_USERS=u1" in env


def test_stage2_writes_identity(tmp_path):
    a = make_answers()
    run(a, tmp_path)
    agent = json.loads((tmp_path / a.profile_name / "local" / "agent.json").read_text(encoding="utf-8"))
    assert agent["agent_name"] == "alpha-sh"
    assert agent["display_name"] == "Alpha"
    assert agent["handle"] == "alpha-sh"
    assert agent["model"] == "opus"
    assert agent["agent_fingerprint"]


def test_stage3_patches_war_room(tmp_path):
    a = make_answers(board="shared", min_confidence=80)
    run(a, tmp_path)
    cfg = (tmp_path / a.profile_name / "config.yaml").read_text(encoding="utf-8")
    assert "war_room:" in cfg
    assert "board: shared" in cfg
    assert "min_confidence: 80" in cfg


def test_stage3_patches_mailbox(tmp_path):
    a = make_answers(board="shared", label="alpha-sh")
    run(a, tmp_path)
    cfg = (tmp_path / a.profile_name / "config.yaml").read_text(encoding="utf-8")
    assert "mailbox:" in cfg
    assert "label: alpha-sh" in cfg


def test_stage4_profile_scoped_no_yes(tmp_path):
    captured = {}

    def p(c, *, timeout, tee=None):
        captured["cmd"] = c
        return ok()

    run(make_answers(name="alpha-sh"), tmp_path, plugin=p)
    assert captured["cmd"] == ["hermes", "-p", "alpha-sh", "plugins", "enable", "warroom-gate"]
    assert "-y" not in captured["cmd"]
    assert "--yes" not in captured["cmd"]


def test_stage4_failure_does_not_abort(tmp_path):
    res = run(make_answers(), tmp_path, plugin=lambda c, *, timeout, tee=None: fail(rc=2))
    assert res.exit_code == 0  # advisory; does NOT abort
    assert 5 in res.completed_stages
    assert any("plugins enable failed" in w for w in res.warnings)


def test_stage5_calls_bootstrap_in_process(tmp_path):
    a = make_answers()
    res = run(a, tmp_path)
    # bootstrap persists runtime state in-process (no subprocess to warroom setup).
    assert (tmp_path / a.profile_name / "local" / "warroom-enroll.json").exists()
    assert res.enroll_status is not None
    assert 5 in res.completed_stages


def test_stage5_handles_enroll_status_codes(tmp_path):
    # No mailbox CLI in a tmp profile -> status cli-not-found, but execute
    # treats it as success-with-warning (routing still written).
    a = make_answers()
    res = run(a, tmp_path)
    assert res.enroll_status in ("cli-not-found", "socket-unreachable", "ok")
    assert res.exit_code == 0


def test_install_log_truncated(tmp_path):
    a = make_answers()
    local = tmp_path / a.profile_name / "local"
    local.mkdir(parents=True)
    (local / "install.log").write_text("OLDOLDOLD\n" * 100, encoding="utf-8")
    run(a, tmp_path)
    body = (local / "install.log").read_text(encoding="utf-8")
    assert "OLDOLDOLD" not in body  # truncated at start (K14)
    assert "hermes profile install" in body


def test_total_time_in_summary(tmp_path):
    out = io.StringIO()
    run(make_answers(), tmp_path, out=out)
    assert "Total time:" in out.getvalue()


def test_verbose_tees_to_stderr(tmp_path):
    captured = {}

    def h(c, *, timeout, tee=None):
        captured["tee"] = tee
        return ok()

    run(make_answers(), tmp_path, hermes=h, verbose=True)
    assert captured["tee"] is sys.stderr


def test_import_error_treated_as_stage1_failure(tmp_path):
    # Default importer: a profile without warroom_setup/__init__.py is not
    # importable -> Stage 1 failure (Risk #1).
    a = make_answers()
    res = orch.execute(
        a, profiles_root=tmp_path,
        hermes_runner=lambda c, *, timeout, tee=None: ok(),
        plugin_runner=lambda c, *, timeout, tee=None: ok(),
        out=io.StringIO(),  # default importer (no injection)
    )
    assert res.failed_stage == 1
    assert res.exit_code == 1


def test_skip_install_reconfigure(tmp_path):
    a = make_answers()
    called = {"h": 0}

    def h(c, *, timeout, tee=None):
        called["h"] += 1
        return ok()

    res = run(a, tmp_path, hermes=h, skip_install=True)
    assert called["h"] == 0  # Stage 1 skipped
    assert 1 in res.completed_stages  # recorded as completed (skip)
    assert (tmp_path / a.profile_name / ".env").exists()  # later stages still run


def test_verify_profile_importable(tmp_path):
    p = tmp_path / "prof"
    (p / "warroom_setup").mkdir(parents=True)
    with pytest.raises(ImportError):
        orch.verify_profile_importable(p)  # no __init__.py yet
    (p / "warroom_setup" / "__init__.py").write_text("", encoding="utf-8")
    orch.verify_profile_importable(p)  # now ok
