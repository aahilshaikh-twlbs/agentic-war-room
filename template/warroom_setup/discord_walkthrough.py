"""Discord bot setup walkthrough. Stdlib only, Python >=3.9.

A walkthrough is a list of Step records (display text + an optional prompt with
a validator). The driver, run_discord_walkthrough, is UI-agnostic: it takes a
`prompts` callable so the same steps work in a CLI wizard, a test, or a future
installer. Token/channel-id validation lives in validators.py (re-exported here
as _validate_token / _validate_channel_id) so there is one source of truth.
"""
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import validators

# Re-export the shared validators under the walkthrough's local names.
_validate_token = validators.valid_bot_token
_validate_channel_id = validators.valid_channel_id

# OAuth2 permission integer for a war-room bot (View Channels + Send Messages +
# Read Message History + Embed Links + Attach Files + Use Slash Commands).
DISCORD_PERMISSION_INTEGER = 277025770560


@dataclass
class Step:
    n: int
    title: str
    body_lines: List[str]
    prompt_label: Optional[str] = None
    validator: Optional[Callable[[str], bool]] = None
    optional: bool = False


@dataclass
class DiscordCreds:
    bot_token: str = ""
    channel_id: str = ""
    second_channel_id: str = ""


WALKTHROUGH_STEPS = [
    Step(
        n=1,
        title="Create a Discord application",
        body_lines=[
            "Open the Discord Developer Portal: https://discord.com/developers/applications",
            "Click 'New Application', give it a name, and accept the terms.",
            "Open the 'Bot' tab and click 'Add Bot' if one is not already present.",
        ],
    ),
    Step(
        n=2,
        title="Copy the bot token",
        body_lines=[
            "On the 'Bot' tab, click 'Reset Token' and copy the token.",
            "Treat this like a password -- it is written to .env, never to config.yaml.",
        ],
        prompt_label="Discord bot token",
        validator=_validate_token,
    ),
    Step(
        n=3,
        title="Enable the MESSAGE CONTENT intent",
        body_lines=[
            "Still on the 'Bot' tab, scroll to 'Privileged Gateway Intents'.",
            "Toggle ON 'MESSAGE CONTENT INTENT' (required to read channel messages).",
            "Save changes.",
        ],
    ),
    Step(
        n=4,
        title="Invite the bot with the right permissions",
        body_lines=[
            "Open 'OAuth2' -> 'URL Generator'.",
            "Scopes: check 'bot' and 'applications.commands'.",
            "Bot permissions: use the permission integer 277025770560.",
            "Open the generated URL and add the bot to your server.",
        ],
    ),
    Step(
        n=5,
        title="Copy the channel ID",
        body_lines=[
            "In Discord, enable Developer Mode: User Settings -> Advanced -> Developer Mode.",
            "Right-click the war-room channel and choose 'Copy Channel ID'.",
        ],
        prompt_label="Channel ID",
        validator=_validate_channel_id,
    ),
    Step(
        n=6,
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
        n=7,
        title="Finish",
        body_lines=[
            "Done. The bot token goes in .env; channel IDs go in config.yaml.",
            "Restart the gateway to pick up the new configuration.",
        ],
    ),
]  # type: List[Step]


def run_discord_walkthrough(prompts, *, context):
    # type: (Callable, str) -> DiscordCreds
    """Drive the Discord steps. `prompts` is called once per step as
    prompts(step, context=context) and returns the operator's answer for steps
    that have a prompt_label (the return value is ignored for info-only steps;
    the caller is expected to display step.body_lines). Validation/retry is the
    `prompts` callable's responsibility (each step carries its validator).
    Returns the collected DiscordCreds."""
    creds = DiscordCreds()
    for step in WALKTHROUGH_STEPS:
        answer = prompts(step, context=context)
        if not step.prompt_label:
            continue
        answer = (answer or "").strip()
        if step.optional and not answer:
            continue
        if step.validator is _validate_token:
            creds.bot_token = answer
        elif step.validator is _validate_channel_id:
            if step.optional:
                creds.second_channel_id = answer
            else:
                creds.channel_id = answer
    return creds
