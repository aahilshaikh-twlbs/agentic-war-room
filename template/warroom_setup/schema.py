"""Canonical key sets, defaults, and sanitization patterns. Stdlib only.

This is the single source of truth for the war_room config block, the mailbox
routing block, the percentage clamp, and the sanitization regex used by the CI
guard (see template/SANITIZATION.md). setup.py, the walkthroughs, and the future
installer all read from here so they cannot drift.
"""
import re

# Ordered key set for the sentinel-managed war_room config block. The DEFCON /
# severity keys (severity_thresholds .. escalate_at) are all optional. They render
# only when the feature is configured: severity_thresholds={} is omitted, the ""
# scalars are omitted, and the default-valued DEFCON scalars
# (severity_inference="explicit", verifier_timeout_s=30) are omitted too UNLESS a
# DEFCON surface is set (see the renderer's _defcon_on guard in setup.py). So a
# non-DEFCON profile keeps the EXACT pre-DEFCON block bytes.
WAR_ROOM_KEYS = (
    "enabled", "board", "parent", "label", "role", "min_confidence",
    "gate_action", "enforce", "show_confidence_badge",
    "severity_thresholds", "severity_inference", "require_verifier_at",
    "verifier_label", "verifier_timeout_s", "escalate_at",
)

# Sanctioned war_room.role values. `verifier` (DEFCON / severity spec) names an
# agent that services verification requests; `contributor` is the default. Other
# values are tolerated (free scalar) but these are documented.
ROLE_VOCAB = ("contributor", "verifier")

# Ordered key set for the top-level mailbox routing block (locked decision #1:
# routing lives in config.yaml, not .env).
MAILBOX_KEYS = ("board", "label", "mailbox_home", "socket_path")

# Safe defaults for every WAR_ROOM_KEY. label defaults empty -> resolved to the
# operator handle at setup time (locked decision #4).
DEFAULTS = {
    "enabled": True,
    "board": "default",
    "parent": "",
    "label": "",
    "role": "contributor",
    "min_confidence": 75,
    "gate_action": "abstain",
    "enforce": False,
    "show_confidence_badge": True,
    # --- DEFCON / severity (all optional; OFF/empty by default) ---
    "severity_thresholds": {},     # {} => default-only floor from min_confidence
    "severity_inference": "explicit",
    "require_verifier_at": "",     # "" => never require a verifier
    "verifier_label": "",
    "verifier_timeout_s": 30,
    "escalate_at": "",             # "" => never auto-escalate (orchestrator-driven)
}

# Safe defaults for the mailbox block. Empty strings mean "use the mailbox
# runtime's own default location".
MAILBOX_DEFAULTS = {
    "board": "default",
    "label": "",
    "mailbox_home": "",
    "socket_path": "",
}


def clamp_pct(v, default=75):
    # type: (object, int) -> int
    """Coerce v to an int percentage in [0, 100]. Accepts str/int/float; falls
    back to default on None, blank, bool, or unparseable input."""
    if v is None or isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return max(0, min(100, int(v)))
    s = str(v).strip()
    if not s:
        return default
    try:
        return max(0, min(100, int(s)))
    except ValueError:
        return default


# Sanitization value patterns (shape-based; no literal employer/operator
# strings, which are matched separately by the configurable blocklist in
# template/SANITIZATION.md). These catch org artifacts that leak by SHAPE.
BLOCKED_VALUE_PATTERNS = (
    r"U0[A-Z0-9]{8,}",                  # Slack user id
    r"T0[A-Z0-9]{8,}",                  # Slack team id
    # agent-fingerprint: <slug>-<uuid>
    r"[a-z][a-z0-9-]*-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    r"[A-Za-z0-9-]+\.(?:internal|corp|local|lan)\b",   # non-public hostnames
    r"/Users/[^/\s]+/Documents/",       # vault-style absolute home paths
    r"\b\d{17,20}\b",                   # Discord/Slack snowflake ids
)

BLOCKED_VALUES_REGEX = re.compile(
    "|".join("(?:%s)" % p for p in BLOCKED_VALUE_PATTERNS)
)
