"""Slack Socket Mode walkthrough (Task T9), parallel to the Discord one."""
from warroom_setup import slack_walkthrough as sw
from warroom_setup import discord_walkthrough as dw
from warroom_setup import validators


def test_step_shape_is_shared_with_discord():
    # One dataclass for both walkthroughs.
    assert sw.Step is dw.Step


def test_eight_steps_numbered_in_order():
    assert len(sw.SLACK_WALKTHROUGH_STEPS) == 8
    assert [s.n for s in sw.SLACK_WALKTHROUGH_STEPS] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_socket_mode_flow_mentioned():
    blob = "\n".join("\n".join(s.body_lines) for s in sw.SLACK_WALKTHROUGH_STEPS)
    assert "Socket Mode" in blob
    assert "xapp-" in blob   # app-level token
    assert "xoxb-" in blob   # bot user token


def test_validators_reexported():
    assert sw._validate_token is validators.valid_bot_token
    assert sw._validate_channel_id is validators.valid_channel_id


def test_two_token_steps_and_two_channel_steps():
    token_steps = [s for s in sw.SLACK_WALKTHROUGH_STEPS if s.validator is sw._validate_token]
    chan_steps = [s for s in sw.SLACK_WALKTHROUGH_STEPS if s.validator is sw._validate_channel_id]
    assert len(token_steps) == 2          # app-level + bot
    assert len(chan_steps) == 2           # primary + optional second
    assert any(s.optional for s in chan_steps)


def test_run_collects_creds():
    answers = {
        2: "xapp-1-A012345678-0123456789-abcdef",
        4: "xoxb-123456789012-abcdefABCDEF",
        6: "12345678901234567",
        7: "98765432109876543",
    }

    def fake_prompts(step, context=None):
        return answers.get(step.n, "")

    creds = sw.run_slack_walkthrough(fake_prompts, context="demo")
    assert creds.app_token == answers[2]
    assert creds.bot_token == answers[4]
    assert creds.channel_id == "12345678901234567"
    assert creds.second_channel_id == "98765432109876543"


def test_run_skips_blank_optional_second_channel():
    answers = {2: "xapp-x", 4: "xoxb-x", 6: "12345678901234567"}

    def fake_prompts(step, context=None):
        return answers.get(step.n, "")

    creds = sw.run_slack_walkthrough(fake_prompts, context="demo")
    assert creds.second_channel_id == ""


def test_run_passes_context_to_prompts():
    seen = {}

    def fake_prompts(step, context=None):
        seen["context"] = context
        return ""

    sw.run_slack_walkthrough(fake_prompts, context="ctx-9")
    assert seen["context"] == "ctx-9"
