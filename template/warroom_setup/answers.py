"""Persisted setup answers at local/.warroom-setup.json. Stdlib only, Python >=3.9.

Extends ccpkg's selected/deselected with a `values` map for free-text fields.
SECRET_IDS are stripped before writing - tokens live only in .env.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .selectables import SECRET_IDS

FILENAME = ".warroom-setup.json"


@dataclass
class Answers:
    selected: List[str] = field(default_factory=list)
    deselected: List[str] = field(default_factory=list)
    values: Dict[str, str] = field(default_factory=dict)


def load(path):
    # type: (Path) -> Optional[Answers]
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if "selected" not in data and "deselected" not in data and "values" not in data:
        return None
    return Answers(
        selected=list(data.get("selected", [])),
        deselected=list(data.get("deselected", [])),
        values=dict(data.get("values", {})),
    )


def save(path, ans):
    # type: (Path, Answers) -> None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_values = {k: v for k, v in ans.values.items() if k not in SECRET_IDS}
    payload = {"selected": sorted(ans.selected),
               "deselected": sorted(ans.deselected),
               "values": safe_values}
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, str(path))
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass
