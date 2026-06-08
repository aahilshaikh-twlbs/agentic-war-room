"""T9 -- headless mode (flags + secret resolution via --*-env / --*-file)."""
import io as _io
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install as awr  # noqa: E402

_FAKE_DISCORD = "FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL"


class _Args:
    def __init__(self, **kw):
        defaults = dict(
            headless=True, name=None, source=None, board=None, label=None,
            discord=False, slack=False, agent_name=None, display_name=None,
            handle=None, discord_allowed_users=None, min_confidence=75, model="opus",
            anthropic_key_env=None, anthropic_key_file=None,
            discord_token_env=None, discord_token_file=None,
            discord_channel_id=None, discord_second_channel_id=None,
            slack_app_token_env=None, slack_app_token_file=None,
            slack_bot_token_env=None, slack_bot_token_file=None,
            slack_channel_id=None, slack_second_channel_id=None,
            force=False, dry_run=False, verbose=False, stage_timeout=300.0, resume=False,
            uninstall=None,
        )
        defaults.update(kw)
        for k, v in defaults.items():
            setattr(self, k, v)


def _base(**kw):
    base = dict(name="alpha-sh", source="/tmpl", board="shared",
                agent_name="alpha-sh", display_name="Alpha")
    base.update(kw)
    return _Args(**base)


def test_requires_name_and_identity():
    with pytest.raises(awr.HeadlessError):
        awr.build_headless_answers(_Args(headless=True, source="/t", board="shared"), env={})
    # missing agent-name/display-name
    with pytest.raises(awr.HeadlessError):
        awr.build_headless_answers(_Args(headless=True, name="x", source="/t", board="shared"), env={})


def test_reads_from_env_vars():
    args = _base(discord=True, anthropic_key_env="ANTH", discord_token_env="DTOK",
                 discord_channel_id="12345678901234567")
    env = {"ANTH": "sk-ant-" + "x" * 40, "DTOK": _FAKE_DISCORD}
    answers = awr.build_headless_answers(args, env=env)
    assert answers.anthropic_key == "sk-ant-" + "x" * 40
    assert answers.discord_creds.bot_token == _FAKE_DISCORD
    assert answers.discord_creds.channel_id == "12345678901234567"
    assert answers.channels == {"discord"}


def test_reads_from_token_file(tmp_path):
    tok = tmp_path / "discord.tok"
    tok.write_text(_FAKE_DISCORD + "\n", encoding="utf-8")
    args = _base(discord=True, discord_token_file=str(tok))
    answers = awr.build_headless_answers(args, env={})
    assert answers.discord_creds.bot_token == _FAKE_DISCORD


def test_aborts_when_required_env_missing():
    args = _base(discord=True, discord_token_env="DTOK")
    with pytest.raises(awr.HeadlessError) as exc:
        awr.build_headless_answers(args, env={})  # DTOK unset
    assert "DTOK" in str(exc.value)


def test_aborts_on_collision_without_force(tmp_path, monkeypatch, capsys):
    # Point ~/.hermes/profiles at a tmp HOME holding a foreign Hermes profile.
    home = tmp_path / "home"
    prof = home / ".hermes" / "profiles" / "alpha-sh"
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("name: alpha-sh\n", encoding="utf-8")  # hermes, no warroom -> abort
    monkeypatch.setenv("HOME", str(home))
    argv = [
        "--headless", "--name", "alpha-sh", "--source", "/tmpl", "--board", "shared",
        "--agent-name", "alpha-sh", "--display-name", "Alpha",
    ]
    rc = awr.main(argv)
    assert rc == 2  # collision -> abort (no --force)
    assert "Refusing to install" in capsys.readouterr().out


def test_skips_walkthrough_when_tokens_provided():
    # Tokens supplied via flags -> creds built without any walkthrough/prompt.
    args = _base(discord=True, slack=True,
                 discord_token_env="DTOK",
                 slack_app_token_env="SAPP", slack_bot_token_env="SBOT")
    env = {"DTOK": _FAKE_DISCORD, "SAPP": "xapp-1-A012345678-0123456789-abcdef",
           "SBOT": "xoxb-123456789012-abcdefABCDEF"}
    answers = awr.build_headless_answers(args, env=env)
    assert answers.discord_creds.bot_token == _FAKE_DISCORD
    assert answers.slack_creds.app_token.startswith("xapp-")
    assert answers.slack_creds.bot_token.startswith("xoxb-")


def test_runs_no_prompts_with_stdin_devnull():
    args = _base(discord=True, discord_token_env="DTOK", anthropic_key_env="ANTH")

    class Boom:
        def readline(self):
            raise AssertionError("headless must not read stdin")

    # env provides secrets; run_tui must not prompt.
    import os
    os.environ["DTOK"] = _FAKE_DISCORD
    os.environ["ANTH"] = "sk-ant-" + "x" * 40
    try:
        answers = awr.run_tui(args, io=awr.WizardIO(infile=Boom(), outfile=_io.StringIO()))
    finally:
        os.environ.pop("DTOK", None)
        os.environ.pop("ANTH", None)
    assert answers.profile_name == "alpha-sh"
    assert answers.anthropic_key == "sk-ant-" + "x" * 40
