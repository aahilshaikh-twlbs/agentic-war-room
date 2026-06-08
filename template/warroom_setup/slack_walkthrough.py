"""Slack (Socket Mode) setup walkthrough. Stdlib only, Python >=3.9.

Parallel to discord_walkthrough: same Step dataclass (imported, not redefined),
same UI-agnostic driver shape. Socket Mode needs TWO tokens -- an app-level
token (xapp-) for the socket connection and a bot user token (xoxb-) -- so the
driver maps answers by step number rather than by validator identity.
"""
from typing import Callable

from . import validators
from .discord_walkthrough import Step

_validate_token = validators.valid_bot_token
_validate_channel_id = validators.valid_channel_id


class SlackCreds:
    def __init__(self, app_token="", bot_token="", channel_id="", second_channel_id=""):
        self.app_token = app_token
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.second_channel_id = second_channel_id

    def __eq__(self, other):
        return isinstance(other, SlackCreds) and self.__dict__ == other.__dict__

    def __repr__(self):
        return "SlackCreds(%r, %r, %r, %r)" % (
            self.app_token, self.bot_token, self.channel_id, self.second_channel_id,
        )


# Step-number -> creds-field contract used by run_slack_walkthrough.
_APP_TOKEN_STEP = 2
_BOT_TOKEN_STEP = 4
_CHANNEL_STEP = 6
_SECOND_CHANNEL_STEP = 7


SLACK_WALKTHROUGH_STEPS = [
    Step(
        n=1,
        title="Create a Slack app",
        body_lines=[
            "Open https://api.slack.com/apps and click 'Create New App'.",
            "Choose 'From an app manifest' and paste template/slack-manifest.json,",
            "or start 'From scratch' and pick your workspace.",
        ],
    ),
    Step(
        n=2,
        title="Enable Socket Mode and create an app-level token",
        body_lines=[
            "Open 'Socket Mode' and toggle it ON.",
            "Generate an app-level token with the 'connections:write' scope.",
            "Copy the token -- it starts with 'xapp-'. Stored in .env.",
        ],
        prompt_label="Slack app-level token (xapp-)",
        validator=_validate_token,
    ),
    Step(
        n=3,
        title="Add bot token scopes",
        body_lines=[
            "Open 'OAuth & Permissions' -> 'Scopes' -> 'Bot Token Scopes'.",
            "Add: chat:write, channels:history, channels:read, app_mentions:read.",
        ],
    ),
    Step(
        n=4,
        title="Install to workspace and copy the bot token",
        body_lines=[
            "Click 'Install to Workspace' and authorize.",
            "Copy the 'Bot User OAuth Token' -- it starts with 'xoxb-'. Stored in .env.",
        ],
        prompt_label="Slack bot token (xoxb-)",
        validator=_validate_token,
    ),
    Step(
        n=5,
        title="Subscribe to events",
        body_lines=[
            "Open 'Event Subscriptions' and enable events.",
            "Under 'Subscribe to bot events' add: app_mention, message.channels.",
            "Reinstall the app if Slack prompts you to apply new scopes.",
        ],
    ),
    Step(
        n=6,
        title="Copy the channel ID",
        body_lines=[
            "Right-click the war-room channel -> 'View channel details'.",
            "The channel ID is at the bottom of that dialog (or in the channel URL).",
            "Invite the bot to the channel with '/invite @yourbot'.",
        ],
        prompt_label="Channel ID",
        validator=_validate_channel_id,
    ),
    Step(
        n=7,
        title="Optional: a second channel",
        body_lines=[
            "If you want a second bound channel, copy its ID the same way.",
            "Leave blank to skip.",
        ],
        prompt_label="Second channel ID (optional)",
        validator=_validate_channel_id,
        optional=True,
    ),
    Step(
        n=8,
        title="Finish",
        body_lines=[
            "Done. Both tokens go in .env; channel IDs go in config.yaml.",
            "Restart the gateway to pick up the new configuration.",
        ],
    ),
]


def run_slack_walkthrough(prompts, *, context):
    # type: (Callable, str) -> SlackCreds
    """Drive the Slack steps. `prompts` is called once per step as
    prompts(step, context=context) and returns the operator's answer for steps
    with a prompt_label. Validation/retry is the callable's responsibility.
    Returns the collected SlackCreds."""
    creds = SlackCreds()
    for step in SLACK_WALKTHROUGH_STEPS:
        answer = prompts(step, context=context)
        if not step.prompt_label:
            continue
        answer = (answer or "").strip()
        if step.optional and not answer:
            continue
        if step.n == _APP_TOKEN_STEP:
            creds.app_token = answer
        elif step.n == _BOT_TOKEN_STEP:
            creds.bot_token = answer
        elif step.n == _CHANNEL_STEP:
            creds.channel_id = answer
        elif step.n == _SECOND_CHANNEL_STEP:
            creds.second_channel_id = answer
    return creds
