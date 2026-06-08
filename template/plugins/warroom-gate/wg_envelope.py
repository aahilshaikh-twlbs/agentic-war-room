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
    + r" missing=(?P<missing>[^" + _L + _R + r"\n]{0,200})"
    + _R + "$"
)
_STRAY_RE = re.compile(_L + r"conf=[^" + _R + r"\n]{0,300}" + _R)


@dataclass
class Envelope:
    conf: float
    grounded: Tuple[str, ...]
    missing: str


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
    env = Envelope(conf=float(m.group("conf")), grounded=grounded, missing=m.group("missing").strip())
    body = "\n".join(lines[:-1]).rstrip("\n")
    return env, body


def strip_stray_envelopes(text):
    # type: (str) -> str
    return _STRAY_RE.sub("", text)
