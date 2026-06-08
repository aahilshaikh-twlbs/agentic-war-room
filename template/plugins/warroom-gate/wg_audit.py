"""Append-only gate-decision log. Stdlib only, Python >=3.9.

Records the decision, never the message text or any secret. Best-effort:
logging failures never propagate (the gate must not fail because logging did).
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from wg_policy import Decision


def log(profile_root, decision, conf, kind, text):
    # type: (Path, Decision, Optional[float], str, str) -> None
    try:
        digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:8]
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conf_s = "-" if conf is None else ("%.2f" % conf)
        line = "%s action=%s reason=%s conf=%s kind=%s sha=%s\n" % (
            ts, decision.action, decision.reason, conf_s, kind, digest)
        d = Path(profile_root) / "local" / "war_room"
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(d), 0o700)
        except OSError:
            pass
        f = d / "gate.log"
        with open(str(f), "a", encoding="utf-8") as fh:
            fh.write(line)
        try:
            os.chmod(str(f), 0o600)
        except OSError:
            pass
    except Exception:
        return  # logging is best-effort; never raise
