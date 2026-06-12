"""Confidence-envelope parsing. Stdlib only, Python >=3.9.

Canonical form (agent-controlled, last line only):
    ⟦conf=0.82 grounded=tool,file missing=none⟧
Anti-spoof: only an envelope occupying the entire final non-empty line is
honored; lookalikes elsewhere (e.g. quoted user text) are ignored.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

GROUNDED_VOCAB = ("tool", "file", "source", "citation", "memory", "none")

# Closed lexical severity set the envelope grammar accepts. The THRESHOLD lookup
# is config-driven (wg_gateconfig.severity_thresholds keys), but the agent-typed
# token must be one of these to ride the anti-spoofed envelope slot; an out-of-
# vocab token makes the whole envelope unparseable (-> claim abstains
# no-envelope), so the gate never guesses a severity from a malformed footer.
# `default` is reserved as the baseline floor.
SEV_VOCAB = ("alert1", "alert2", "alert3", "default")

# Sentinel brackets as \uXXXX escapes so the matching logic never depends on how
# the source file's non-ASCII bytes are decoded. U+27E6/U+27E7 = the bracket pair.
_L = "\u27e6"
_R = "\u27e7"

# Bounded quantifiers only -> linear, ReDoS-safe. Strict closing (a single _R,
# no optional open bracket) keeps the grammar tight for anti-spoof.
_ENV_RE = re.compile(
    "^" + _L
    + r"conf=(?P<conf>0(?:\.\d{1,3})?|1(?:\.0{1,3})?)"
    + r" grounded=(?P<grounded>[a-z,]{1,64})"
    # The missing field is free text that may contain spaces, but it must NOT
    # absorb the optional trailing ` sev=` token. Each step consumes one char:
    # a space that does NOT begin a ` sev=` run, or any non-space/non-bracket
    # char. Bounded {0,200} -> still linear / ReDoS-safe. Without this guard the
    # greedy [^⟦⟧] class would swallow ` sev=alert1` into missing and the
    # optional group would never fire (and an out-of-vocab sev=alert9 would
    # parse instead of failing closed).
    + r" missing=(?P<missing>(?: (?!sev=)|[^ " + _L + _R + r"\n]){0,200})"
    + r"(?: sev=(?P<sev>alert1|alert2|alert3|default))?"
    + _R + "$"
)
_STRAY_RE = re.compile(_L + r"conf=[^" + _R + r"\n]{0,300}" + _R)


@dataclass
class Envelope:
    conf: float
    grounded: Tuple[str, ...]
    missing: str
    sev: str = "default"


def parse_last_line(text):
    # type: (str) -> Tuple[Optional[Envelope], str]
    if not isinstance(text, str) or not text:
        return None, text
    lines = text.rstrip("\n").split("\n")
    last = lines[-1].strip()
    m = _ENV_RE.match(last)
    if not m:
        return None, text
    grounded = tuple(g for g in m.group("grounded").split(",") if g in GROUNDED_VOCAB)
    if not grounded:
        return None, text
    env = Envelope(
        conf=float(m.group("conf")),
        grounded=grounded,
        missing=m.group("missing").strip(),
        sev=(m.group("sev") or "default"),
    )
    body = "\n".join(lines[:-1]).rstrip("\n")
    return env, body


def strip_stray_envelopes(text):
    # type: (str) -> str
    return _STRAY_RE.sub("", text)
