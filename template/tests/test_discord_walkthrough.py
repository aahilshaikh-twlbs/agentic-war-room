"""Discord setup walkthrough (Task T8): step content + validator wiring + run."""
from warroom_setup import discord_walkthrough as dw
from warroom_setup import validators


def test_seven_steps_numbered_in_order():
    assert len(dw.WALKTHROUGH_STEPS) == 7
    assert [s.n for s in dw.WALKTHROUGH_STEPS] == [1, 2, 3, 4, 5, 6, 7]


def test_permission_integer_present():
    assert dw.DISCORD_PERMISSION_INTEGER == 277025770560
    blob = "\n".join("\n".join(s.body_lines) for s in dw.WALKTHROUGH_STEPS)
    assert "277025770560" in blob


def test_message_content_intent_step_exists():
    blob = "\n".join("\n".join(s.body_lines) for s in dw.WALKTHROUGH_STEPS)
    assert "MESSAGE CONTENT" in blob


def test_validators_are_reexported_from_validators_module():
    assert dw._validate_token is validators.valid_bot_token
    assert dw._validate_channel_id is validators.valid_channel_id


def test_validator_wiring():
    token_steps = [s for s in dw.WALKTHROUGH_STEPS if s.validator is dw._validate_token]
    chan_steps = [s for s in dw.WALKTHROUGH_STEPS if s.validator is dw._validate_channel_id]
    assert len(token_steps) == 1
    assert len(chan_steps) == 2                       # primary + optional second
    assert any(s.optional for s in chan_steps)
    assert any(not s.optional for s in chan_steps)


def test_run_collects_creds():
    answers = {
        2: "FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL",
        5: "12345678901234567",
        6: "98765432109876543",
    }

    def fake_prompts(step, context=None):
        return answers.get(step.n, "")

    creds = dw.run_discord_walkthrough(fake_prompts, context="demo")
    assert creds.bot_token == answers[2]
    assert creds.channel_id == "12345678901234567"
    assert creds.second_channel_id == "98765432109876543"


def test_run_skips_blank_optional_second_channel():
    answers = {2: "tok", 5: "12345678901234567"}

    def fake_prompts(step, context=None):
        return answers.get(step.n, "")

    creds = dw.run_discord_walkthrough(fake_prompts, context="demo")
    assert creds.second_channel_id == ""


def test_run_passes_context_to_prompts():
    seen = {}

    def fake_prompts(step, context=None):
        seen["context"] = context
        return ""

    dw.run_discord_walkthrough(fake_prompts, context="my-context")
    assert seen["context"] == "my-context"
