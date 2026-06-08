"""Declarative wizard model. Stdlib only, Python >=3.9.

Mirrors ccpkg selection.py/selectables.py. Toggles are picked in the raw-mode
TUI; TEXT/SECRET fields are collected via line prompts (prompts.py) because the
ccpkg toggle wizard has no free-text path.
"""
from dataclasses import dataclass, field
from typing import List

STAGE_ORDER = ["Persona", "Channels", "Model", "WarRoom"]


@dataclass
class Entry:
    id: str
    desc: str
    default: bool
    kind: str          # "toggle"


@dataclass
class Stage:
    name: str
    entries: List[Entry] = field(default_factory=list)


@dataclass
class Toggle:
    id: str
    group: str         # one of STAGE_ORDER
    desc: str
    default: bool = True


@dataclass
class TextField:
    id: str
    prompt: str
    secret: bool = False
    required: bool = False
    enable_if: str = ""   # id of a Toggle that must be selected for this field to be asked; "" = always


# Toggle picker entries (arrow/space/Enter/Esc TUI).
TOGGLES = [
    Toggle(id="persona.seed_examples", group="Persona",
           desc="seed persona/*.md with example content (else blank skeleton)", default=False),
    Toggle(id="channels.discord", group="Channels", desc="enable Discord channel", default=True),
    Toggle(id="channels.slack", group="Channels", desc="enable Slack channel", default=False),
    Toggle(id="model.opus", group="Model", desc="Claude Opus", default=True),
    Toggle(id="model.sonnet", group="Model", desc="Claude Sonnet", default=False),
    Toggle(id="warroom.enroll", group="WarRoom",
           desc="enroll on an AWR coordination board (stub until L1)", default=True),
]

# Identity is always asked; channel secrets are asked only if the channel is enabled.
TEXT_FIELDS = [
    TextField(id="agent_name", prompt="Agent name (bare, lowercase; sorts above specialists)", required=True),
    TextField(id="display_name", prompt="Display name (human-readable)", required=True),
    TextField(id="handle", prompt="Profile handle / slug (defaults to agent_name)", required=False),
    TextField(id="ANTHROPIC_API_KEY", prompt="Anthropic API key", secret=True, required=True),
    TextField(id="DISCORD_BOT_TOKEN", prompt="Discord bot token", secret=True,
              required=False, enable_if="channels.discord"),
    TextField(id="DISCORD_ALLOWED_USERS", prompt="Discord allowed user IDs (comma-separated)",
              required=False, enable_if="channels.discord"),
    TextField(id="SLACK_BOT_TOKEN", prompt="Slack bot token (xoxb-...)", secret=True,
              required=False, enable_if="channels.slack"),
    TextField(id="SLACK_APP_TOKEN", prompt="Slack app token (xapp-...)", secret=True,
              required=False, enable_if="channels.slack"),
    TextField(id="warroom.board", prompt="War-room board name", required=False, enable_if="warroom.enroll"),
    TextField(id="warroom.min_confidence",
              prompt="War-room min confidence % to post a claim (0-100)",
              required=False, enable_if="warroom.enroll"),
]

# Secrets that must NEVER be written to the answers JSON (only to .env).
SECRET_IDS = frozenset(f.id for f in TEXT_FIELDS if f.secret)

# Which TextField ids map to .env keys (everything uppercase here is an env var).
ENV_FIELD_IDS = frozenset({
    "ANTHROPIC_API_KEY", "DISCORD_BOT_TOKEN", "DISCORD_ALLOWED_USERS",
    "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN",
})


def _order_key(group):
    if group in STAGE_ORDER:
        return (0, STAGE_ORDER.index(group), "")
    return (1, 0, group)


def build_stages(toggles):
    # type: (List[Toggle]) -> List[Stage]
    buckets = {}
    for t in toggles:
        buckets.setdefault(t.group, []).append(
            Entry(id=t.id, desc=t.desc, default=t.default, kind="toggle"))
    stages = []
    for group in sorted(buckets, key=_order_key):
        if buckets[group]:
            stages.append(Stage(name=group, entries=buckets[group]))
    return stages


def default_ids(toggles):
    # type: (List[Toggle]) -> set
    return {t.id for t in toggles if t.default}
