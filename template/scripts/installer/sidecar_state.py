"""Resume sidecar at ``~/.awr/install-state.json`` (A3/F12).

A partial install records a NON-SECRET snapshot so it can be resumed. The
sidecar lives in its own ``~/.awr`` namespace (out of Hermes' ``~/.hermes``),
the directory is 0700 and the file 0600, writes are atomic, and the record
expires after 24h. Secrets are NEVER persisted: tokens/keys are stripped on the
way in, and on resume any channel that ran a walkthrough must re-prompt for its
secret (K6).

Schema: ``{started_at, last_updated, profile_name, stage, completed_stages,
answers_non_secret}``.

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Dict, List, Optional

TTL_SECONDS = 24 * 3600
TOTAL_STAGES = 5

# Substrings that mark a key as secret-bearing; such keys are never written.
_SECRET_MARKERS = ("token", "key", "secret", "password", "passwd", "cred")


def default_path() -> Path:
    return Path("~/.awr/install-state.json").expanduser()


def _strip_secrets(payload: Dict) -> Dict:
    """Drop any key whose name looks secret-bearing (defense in depth)."""
    clean = {}
    for k, v in (payload or {}).items():
        low = str(k).lower()
        if any(marker in low for marker in _SECRET_MARKERS):
            continue
        clean[k] = v
    return clean


class Sidecar:
    """Read/write the resume sidecar. ``clock`` is injectable for TTL tests."""

    def __init__(self, path: Optional[Path] = None, *, clock=time.time):
        self.path = Path(path) if path is not None else default_path()
        self._clock = clock

    # -- write ------------------------------------------------------------- #
    def save(self, answers_non_secret: Dict, *, stage: Optional[str] = None,
             completed_stages: Optional[List[int]] = None) -> Dict:
        existing = self._read_raw()
        started = existing.get("started_at") if existing else None
        record = {
            "started_at": started if started is not None else self._clock(),
            "last_updated": self._clock(),
            "profile_name": (answers_non_secret or {}).get("profile_name"),
            "stage": stage if stage is not None else (existing.get("stage") if existing else None),
            "completed_stages": list(
                completed_stages
                if completed_stages is not None
                else ((existing.get("completed_stages") if existing else None) or [])
            ),
            "answers_non_secret": _strip_secrets(answers_non_secret),
        }
        self._atomic_write(record)
        return record

    def record_stage(self, stage: str, completed_stages: List[int]) -> None:
        rec = self._read_raw() or {}
        rec.setdefault("started_at", self._clock())
        rec["stage"] = stage
        rec["completed_stages"] = list(completed_stages)
        rec["last_updated"] = self._clock()
        self._atomic_write(rec)

    def cleanup(self) -> None:
        """Remove the sidecar (call on successful install)."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    # -- read -------------------------------------------------------------- #
    def _read_raw(self) -> Optional[Dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def is_expired(self) -> bool:
        raw = self._read_raw()
        if raw is None:
            return False
        return (self._clock() - raw.get("started_at", 0)) > TTL_SECONDS

    def load(self) -> Optional[Dict]:
        """Return the record, or None if missing or stale (>24h, §6)."""
        raw = self._read_raw()
        if raw is None:
            return None
        if (self._clock() - raw.get("started_at", 0)) > TTL_SECONDS:
            return None
        return raw

    # -- internals --------------------------------------------------------- #
    def _atomic_write(self, record: Dict) -> None:
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)  # K22
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(str(tmp), str(self.path))
        os.chmod(self.path, 0o600)


# --------------------------------------------------------------------------- #
# Resume policy helpers (§6 / K6)
# --------------------------------------------------------------------------- #
def pending_stages(state: Dict, total: int = TOTAL_STAGES) -> List[int]:
    """Stages not yet completed, given a loaded sidecar record."""
    done = set(state.get("completed_stages", []) or [])
    return [n for n in range(1, total + 1) if n not in done]


def channels_needing_reprompt(state: Dict) -> List[str]:
    """Channels whose walkthrough secrets must be re-entered on resume (K6).

    Secrets are never persisted, so every channel that was selected needs its
    token re-prompted before the install can continue.
    """
    answers = state.get("answers_non_secret", {}) or {}
    return list(answers.get("channels", []) or [])
