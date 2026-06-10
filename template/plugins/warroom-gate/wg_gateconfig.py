"""Read war_room.* from <profile>/config.yaml. Stdlib only, Python >=3.9.

Line-based scan of the `war_room:` block (no PyYAML). Conservative defaults;
`enforce` defaults False so an un-set-up profile does not gate. Understands ONE
nested mapping level (`severity_thresholds:`) for the DEFCON / severity model;
every other key stays flat.
"""
import re
from pathlib import Path
from typing import Dict

_DEFAULTS = {
    "enforce": False,
    "min_confidence": 75,
    "show_badge": True,
    "severity_thresholds": {},     # filled with {"default": min_confidence} below
    "severity_inference": "explicit",
    "require_verifier_at": "",
    "verifier_label": "",
    "verifier_timeout_s": 30,
    "escalate_at": "",
}

# Clamp the bounded wait so a misconfig can't hang the gateway turn (spec
# "Critical": monotonic deadline + reader clamp).
_TIMEOUT_MIN = 1
_TIMEOUT_MAX = 120


def _fresh_defaults():
    # type: () -> Dict
    out = dict(_DEFAULTS)
    out["severity_thresholds"] = {}
    return out


def _scan(text):
    # type: (str) -> Dict
    out = _fresh_defaults()
    in_wr = False
    in_sev = False           # inside the severity_thresholds: nested mapping
    sev = {}                 # type: Dict[str, int]
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("war_room:"):
            in_wr = True
            continue
        if not in_wr:
            continue
        # A non-indented, non-comment, non-empty line ends the block.
        if line[:1] not in (" ", "\t", "#") and s:
            break
        # Inside the nested mapping: a child line is indented MORE than the
        # `severity_thresholds:` header (>=4 leading spaces here). Any line
        # indented at the block's own key level (2 spaces) ends the nested map.
        if in_sev:
            indent = len(line) - len(line.lstrip(" "))
            cm = re.match(r"([a-z0-9_]+):\s*(\S+)", s)
            if indent >= 4 and cm:
                try:
                    sev[cm.group(1)] = max(0, min(100, int(cm.group(2))))
                except ValueError:
                    pass
                continue
            # blank line inside the mapping is tolerated, stays nested
            if not s:
                continue
            in_sev = False   # fall through to flat-key handling for this line
        if s.startswith("severity_thresholds:"):
            in_sev = True
            continue
        m = re.match(
            r"(enforce|min_confidence|show_confidence_badge|severity_inference|"
            r"require_verifier_at|verifier_label|verifier_timeout_s|escalate_at"
            r"):\s*(\S+)", s)
        if m:
            k, v = m.group(1), m.group(2)
            if k == "enforce":
                out["enforce"] = v.lower() == "true"
            elif k == "min_confidence":
                try:
                    out["min_confidence"] = max(0, min(100, int(v)))
                except ValueError:
                    pass
            elif k == "show_confidence_badge":
                out["show_badge"] = v.lower() == "true"
            elif k == "severity_inference":
                out["severity_inference"] = v
            elif k == "require_verifier_at":
                out["require_verifier_at"] = v
            elif k == "verifier_label":
                out["verifier_label"] = v
            elif k == "verifier_timeout_s":
                try:
                    out["verifier_timeout_s"] = max(
                        _TIMEOUT_MIN, min(_TIMEOUT_MAX, int(v)))
                except ValueError:
                    pass
            elif k == "escalate_at":
                out["escalate_at"] = v
    # The default floor is min_confidence unless the table restated it.
    if "default" not in sev:
        sev["default"] = out["min_confidence"]
    out["severity_thresholds"] = sev
    return out


def read(profile_root):
    # type: (Path) -> Dict
    p = Path(profile_root) / "config.yaml"
    if not p.is_file():
        out = _fresh_defaults()
        out["severity_thresholds"] = {"default": out["min_confidence"]}
        return out
    try:
        return _scan(p.read_text(encoding="utf-8"))
    except OSError:
        out = _fresh_defaults()
        out["severity_thresholds"] = {"default": out["min_confidence"]}
        return out
