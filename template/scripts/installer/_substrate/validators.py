"""Shared input validators for setup, walkthroughs, and installers.

Stdlib only, Python >=3.9. Each validator is total: it accepts any input
(including None) and returns a bool. These are the single source of truth so
setup.py, the platform walkthroughs, and the future installer all agree on what
a valid slug / handle / channel id / token / board name looks like.
"""
import re

# Profile/agent slug: lowercase, starts with a letter, 1-64 chars, dashes ok.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

# Operator handle: like a slug but also allows underscores. Deliberately a
# SUPERSET of valid_slug so the T23 migration (slug -> handle for the handle
# field) never rejects a previously-accepted value.
_HANDLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

# Discord/Slack snowflake channel id: 17-20 digits.
_CHANNEL_ID_RE = re.compile(r"^\d{17,20}$")

# Bot token shapes:
#   Discord: three base64url segments joined by dots.
#   Slack:   xoxb-/xoxp-/... bot/user tokens and xapp- app-level tokens.
_DISCORD_TOKEN_RE = re.compile(
    r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,}$"
)
_SLACK_TOKEN_RE = re.compile(r"^x(?:ox[abprs]|app)-[A-Za-z0-9-]{8,}$")

# Mailbox board name: starts alnum, 1-64 chars, allows . / : _ - separators.
_BOARD_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,63}$")


def valid_slug(s):
    # type: (object) -> bool
    return bool(_SLUG_RE.match(s or "")) if isinstance(s, str) else False


def valid_handle(s):
    # type: (object) -> bool
    return bool(_HANDLE_RE.match(s or "")) if isinstance(s, str) else False


def valid_channel_id(s):
    # type: (object) -> bool
    return bool(_CHANNEL_ID_RE.match(s or "")) if isinstance(s, str) else False


def valid_bot_token(s):
    # type: (object) -> bool
    if not isinstance(s, str):
        return False
    s = s.strip()
    return bool(_DISCORD_TOKEN_RE.match(s) or _SLACK_TOKEN_RE.match(s))


def valid_board_name(s):
    # type: (object) -> bool
    return bool(_BOARD_NAME_RE.match(s or "")) if isinstance(s, str) else False
