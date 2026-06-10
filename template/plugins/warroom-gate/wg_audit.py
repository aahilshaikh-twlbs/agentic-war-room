"""Append-only gate-decision log. Stdlib only, Python >=3.9.

Records the decision plus a per-message classifier verdict and a tiny set of
CATEGORICAL features (length bucket, ends-with-?, multiline, matched chatter
token) and a full sha256 of the text. NEVER the message body and NEVER a secret
(the sha256 is hash-only; the features are non-reconstructing). Best-effort:
logging failures never propagate (the gate must not fail because logging did).

Field order is fixed and additive: timestamp, verdict?, action, reason, conf,
kind, len, ends_q, multiline, matched, sha256. `sha256=` is emitted LAST so new
optional key=value fields slot in immediately before it.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import wg_classify
from wg_policy import Decision


def _len_bucket(text):
    # type: (str) -> str
    n = len(text or "")
    if n < 16:
        return "xs"
    if n < 64:
        return "s"
    if n < 256:
        return "m"
    return "l"


def log(profile_root, decision, conf, kind, text, verdict=None):
    # type: (Path, Decision, Optional[float], str, str, Optional[str]) -> None
    try:
        t = text or ""
        digest = hashlib.sha256(t.encode("utf-8")).hexdigest()
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conf_s = "-" if conf is None else ("%.2f" % conf)
        matched = wg_classify.matched_chatter(t) or "none"
        ends_q = "1" if t.rstrip().endswith("?") else "0"
        multiline = "1" if "\n" in t else "0"
        verdict_tok = "" if verdict is None else ("verdict=%s " % verdict)
        line = (
            "%s %saction=%s reason=%s conf=%s kind=%s "
            "len=%s ends_q=%s multiline=%s matched=%s sha256=%s\n"
        ) % (
            ts, verdict_tok, decision.action, decision.reason, conf_s, kind,
            _len_bucket(t), ends_q, multiline, matched, digest,
        )
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
