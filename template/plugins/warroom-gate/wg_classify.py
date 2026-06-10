"""Claim vs chatter heuristic. Stdlib only, Python >=3.9.

Conservative: when unsure, treat as a claim (so it gets gated). Chatter =
greetings/acks, very short non-declarative text, or a pure question.
This heuristic is the main accuracy risk (see spec); tune with real traffic.
"""
_CHATTER = {
    "ok", "okay", "kk", "got it", "thanks", "thank you", "ty", "on it", "sure",
    "yep", "yes", "no", "nope", "hi", "hey", "hello", "ack", "acknowledged",
    "done", "+1", "👍", "✅",
}


def is_claim(text):
    # type: (str) -> bool
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower().strip(" .!👍✅")
    # Strip-to-empty (bare 👍/✅/punctuation/"...") is chatter — the strip() above
    # removes exactly the chars _CHATTER tokens are built from, so an emoji-only
    # message normalizes to "" and would otherwise fall through to claim.
    if not low or low in _CHATTER:
        return False
    # Pure question (asking, not asserting): single line, no declarative sentence.
    if t.endswith("?") and "\n" not in t and len(t) < 200 and "." not in t.rstrip("?"):
        return False
    # NOTE: no length-based exemption. Terse declaratives ("it's down",
    # "payments are failing", "db is corrupted") are claims and MUST be gated.
    # See spec — any length short-circuit is a bug, not a convenience.
    return True


def matched_chatter(text):
    # type: (str) -> object
    """Return the exact _CHATTER token `text` normalizes to, else None.

    Read-only audit helper for gate.log's `matched=` field. Mirrors the EXACT
    normalization is_claim() uses (lower(), strip(" .!👍✅"), _CHATTER membership)
    so a logged token is always a real, public _CHATTER entry. It never changes
    classification -- is_claim() is the sole authority on claim vs chatter.
    """
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower().strip(" .!👍✅")
    if low in _CHATTER:
        return low
    return None

# Conservative severity cue words. The hybrid classifier may RAISE an
# untagged/`default` claim to `alert2` (more rigor), NEVER lower an explicit tag,
# and NEVER fabricate `alert1` (top tier must be an explicit human/agent tag).
# This preserves the gate's fail-closed bias: inference can only demand more.
_SEV_CUES = (
    "prod", "production", "outage", "data loss", "corrupt", "breach",
    "down", "failing", "customer impact", "incident",
)


def infer_severity(text, current):
    # type: (str, str) -> str
    """Return a possibly-RAISED severity. Only an untagged/`default` claim with a
    cue word is bumped (to `alert2`); any explicit tag is returned unchanged."""
    if current != "default":
        return current
    low = (text or "").lower()
    if any(cue in low for cue in _SEV_CUES):
        return "alert2"
    return current
