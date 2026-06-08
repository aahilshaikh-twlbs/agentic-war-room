"""Agent identity model + local/agent.json IO. Stdlib only, Python >=3.9."""
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

_FIELDS = ("agent_name", "handle", "display_name", "model",
           "specialist_prefix", "agent_fingerprint")


@dataclass
class AgentIdentity:
    agent_name: str          # bare Claude head name (sorts above any specialists)
    handle: str              # Hermes profile slug (the installed profile dir name)
    display_name: str
    model: str               # e.g. "opus"
    specialist_prefix: str   # specialists are <prefix>-<role>
    agent_fingerprint: str   # stable per-agent id, generated once at setup

    def as_substitutions(self):
        # type: () -> Dict[str, str]
        return {"{{%s}}" % f: str(getattr(self, f)) for f in _FIELDS}


def load(path):
    # type: (Path) -> Optional[AgentIdentity]
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return AgentIdentity(**{f: str(data.get(f, "")) for f in _FIELDS})


def save(path, ident):
    # type: (Path, AgentIdentity) -> None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(ident), fh, indent=2)
        fh.write("\n")
    os.replace(tmp, str(path))
    try:
        os.chmod(str(path), 0o600)   # identity may carry no secret, but keep local/ uniformly private
    except OSError:
        pass
