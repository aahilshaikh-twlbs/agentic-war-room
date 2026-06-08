"""T5 -- interactive TUI orchestration.

Stages read cooked, line-based input from an injected stream. The ESC sentinel
("\\x1b" on a line) drives back-navigation; the Ctrl-C sentinel ("\\x03") raises
KeyboardInterrupt; EOF aborts. This lets us drive every key-binding without a TTY.
"""
import io as _io
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install as awr  # noqa: E402
from _substrate.discord_walkthrough import Step  # noqa: E402


def make_io(lines):
    """A WizardIO fed by `lines` (each becomes one readline())."""
    text = "".join(l if l.endswith("\n") else l + "\n" for l in lines)
    return awr.WizardIO(infile=_io.StringIO(text), outfile=_io.StringIO())


class _Args:
    def __init__(self, **kw):
        defaults = dict(
            headless=False, source=None, name=None, board=None, label=None,
            discord=False, slack=False, agent_name=None, display_name=None,
            handle=None, discord_allowed_users=None, min_confidence=75, model="opus",
        )
        defaults.update(kw)
        for k, v in defaults.items():
            setattr(self, k, v)


# --------------------------------------------------------------------------- #
def test_source_validates_distribution_yaml(tmp_path):
    good = tmp_path / "tmpl"
    good.mkdir()
    (good / "distribution.yaml").write_text("x", encoding="utf-8")
    bad = tmp_path / "empty"
    bad.mkdir()
    io = make_io([str(bad), str(good)])  # bad retried, then good accepted
    val = awr._stage_source(io, default=str(good), git_runner=lambda u: True)
    assert val == str(good)
    assert "distribution.yaml" in io.outfile.getvalue()


def test_source_validates_git_url():
    io = make_io(["https://github.com/owner/repo"])
    val = awr._stage_source(io, default="x", git_runner=lambda u: True)
    assert val == "https://github.com/owner/repo"
    # unreachable URL retries
    io2 = make_io(["https://github.com/owner/repo", "https://github.com/owner/repo"])
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        return calls["n"] >= 2

    assert awr._stage_source(io2, default="x", git_runner=flaky) == "https://github.com/owner/repo"


def test_name_rejects_invalid_slug():
    io = make_io(["Bad Name", "1bad", "alpha-sh"])
    assert awr._stage_name(io) == "alpha-sh"
    assert "invalid slug" in io.outfile.getvalue()


def test_channels_returns_selected_set():
    assert awr._stage_channels(make_io(["discord"])) == {"discord"}
    assert awr._stage_channels(make_io(["both"])) == {"discord", "slack"}
    assert awr._stage_channels(make_io(["none"])) == set()
    assert awr._stage_channels(make_io(["discord, slack"])) == {"discord", "slack"}


def test_identity_collects_all_fields():
    io = make_io(["alpha-sh", "Alpha", "alpha_op", "u1, u2", "80"])
    ident = awr._stage_identity(io, default_name="alpha-sh")
    assert ident["agent_name"] == "alpha-sh"
    assert ident["display_name"] == "Alpha"
    assert ident["handle"] == "alpha_op"
    assert ident["discord_allowed_users"] == ["u1", "u2"]
    assert ident["min_confidence"] == 80


def test_model_dual_toggle_precedence():
    assert awr.resolve_model({"model.opus", "model.sonnet"}) == "opus"
    assert awr.resolve_model({"model.sonnet"}) == "sonnet"
    assert awr.resolve_model({"model.opus"}) == "opus"
    assert awr.resolve_model(set()) == "opus"
    # via the stage
    assert awr._stage_model(make_io(["sonnet"])) == "sonnet"
    assert awr._stage_model(make_io(["both"])) == "opus"


def test_confirm_lists_settings_json_modification():
    acc = awr._Acc(source="/s", profile_name="alpha-sh", channels={"discord"},
                   model="opus", board="shared", label="alpha-sh", anthropic_key="sk-ant-x")
    summary = awr.render_confirmation(acc)
    assert "~/.claude/settings.json" in summary
    assert "mailbox hooks" in summary
    # the masked key is shown, not the literal
    assert "sk-ant-x" not in summary


def test_confirm_back_returns_to_source():
    assert awr._back_target("confirm", {"discord"}) == "source"


def test_esc_returns_to_predecessor():
    assert awr._back_target("name", set()) == "source"
    # identity's predecessor with no channels is anthropic (discord/slack skipped)
    assert awr._back_target("identity", set()) == "anthropic"
    # with discord active, anthropic's predecessor is discord
    assert awr._back_target("anthropic", {"discord"}) == "discord"
    # discord skipped when not selected
    assert awr._back_target("anthropic", set()) == "channels"


def test_headless_skips_prompts():
    args = _Args(headless=True, name="alpha-sh", source="/tmpl", board="shared",
                 agent_name="alpha-sh", display_name="Alpha", discord=True)
    # an exploding stream proves no prompt is read
    class Boom:
        def readline(self):
            raise AssertionError("headless must not read input")

    answers = awr.run_tui(args, io=awr.WizardIO(infile=Boom(), outfile=_io.StringIO()))
    assert answers.profile_name == "alpha-sh"
    assert answers.channels == {"discord"}
    assert answers.board == "shared"


def test_ctrl_c_writes_sidecar_restores_terminal():
    # Ctrl-C sentinel at the first prompt -> sidecar saved + terminal restored.
    recorded = {"saved": None, "restored": False}

    class FakeSidecar:
        def save(self, payload):
            recorded["saved"] = payload

    def fake_restore():
        recorded["restored"] = True

    args = _Args()
    io = awr.WizardIO(infile=_io.StringIO("\x03\n"), outfile=_io.StringIO())
    result = awr.run_tui(args, io=io, sidecar=FakeSidecar(), restore=fake_restore)
    assert result is None
    assert recorded["restored"] is True
    assert recorded["saved"] is not None  # non-secret payload persisted


def test_walkthrough_retries_on_validator_failure():
    step = Step(n=2, title="token", body_lines=["copy it"],
                prompt_label="Bot token", validator=lambda v: v == "good-token")
    io = make_io(["bad", "stillbad", "good-token"])
    val = awr._run_walkthrough_step(io, step)
    assert val == "good-token"
    # exhausts retries -> skip-with-warning
    io2 = make_io(["x", "y", "z"])
    assert awr._run_walkthrough_step(io2, step, max_retries=3) == ""
    assert "skipping" in io2.outfile.getvalue()


def test_walkthrough_optional_skippable():
    step = Step(n=6, title="second channel", body_lines=["optional"],
                prompt_label="Second channel ID (optional)",
                validator=lambda v: v.isdigit(), optional=True)
    io = make_io([""])  # empty -> skip
    assert awr._run_walkthrough_step(io, step) == ""


def test_walkthrough_drives_real_discord_steps():
    # End-to-end: the adapter + driver collect creds from the real step list.
    # token step (#2), channel id (#5), optional second channel (#6) skipped.
    answers = []
    for s in awr.WALKTHROUGH_STEPS:
        if not s.prompt_label:
            continue
        if "token" in s.prompt_label.lower():
            answers.append("FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL")
        elif s.optional:
            answers.append("")  # skip optional
        else:
            answers.append("12345678901234567")
    io = make_io(answers)
    creds = awr._stage_discord(io)
    assert creds.bot_token.startswith("FAKE_TEST_TOKEN")
    assert creds.channel_id == "12345678901234567"
    assert creds.second_channel_id == ""
