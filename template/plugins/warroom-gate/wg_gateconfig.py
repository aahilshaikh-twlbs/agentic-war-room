"""Read war_room.* from <profile>/config.yaml. Stdlib only, Python >=3.9.

Line-based scan of the `war_room:` block (no PyYAML). Conservative defaults;
`enforce` defaults False so an un-set-up profile does not gate.
"""
import re
from pathlib import Path
from typing import Dict

_DEFAULTS = {"enforce": False, "min_confidence": 75, "show_badge": True}


def _scan(text):
    # type: (str) -> Dict
    out = dict(_DEFAULTS)
    in_wr = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("war_room:"):
            in_wr = True
            continue
        if in_wr:
            # A non-indented, non-comment, non-empty line ends the block.
            if line[:1] not in (" ", "\t", "#") and s:
                break
            m = re.match(r"(enforce|min_confidence|show_confidence_badge):\s*(\S+)", s)
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
    return out


def read(profile_root):
    # type: (Path) -> Dict
    p = Path(profile_root) / "config.yaml"
    if not p.is_file():
        return dict(_DEFAULTS)
    try:
        return _scan(p.read_text(encoding="utf-8"))
    except OSError:
        return dict(_DEFAULTS)
