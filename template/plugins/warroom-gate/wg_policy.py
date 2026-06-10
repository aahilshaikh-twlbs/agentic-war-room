"""Gate decision. Stdlib only, Python >=3.9. Pure."""
from dataclasses import dataclass
from typing import Dict, Optional

from wg_envelope import Envelope

PASS = "pass"
ABSTAIN = "abstain"


@dataclass
class Decision:
    action: str          # PASS | ABSTAIN
    # reason vocab:
    #   chatter | ok | no-envelope | ungrounded | below-threshold |
    #   below-severity-floor | verifier-rejected | verifier-timeout |
    #   verifier-unreachable | empty-body | internal-error
    reason: str
    missing: str = ""


def resolve_floor(sev, threshold, severity_thresholds=None):
    # type: (str, float, Optional[Dict[str, int]]) -> float
    """Per-severity floor as a [0,1] fraction. With no table, returns the scalar
    threshold (back-compat). With a table, looks up `sev`, falling back to
    `default`, falling back to the scalar threshold * 100."""
    if not severity_thresholds:
        return threshold
    base_pct = int(round(threshold * 100))
    pct = severity_thresholds.get(
        sev, severity_thresholds.get("default", base_pct))
    return pct / 100.0


def decide(is_claim, env, threshold, severity_thresholds=None):
    # type: (bool, Optional[Envelope], float, Optional[Dict[str, int]]) -> Decision
    if not is_claim:
        return Decision(PASS, "chatter")
    if env is None:
        return Decision(ABSTAIN, "no-envelope")
    if not env.grounded or env.grounded == ("none",):
        return Decision(ABSTAIN, "ungrounded", env.missing)
    # Below the baseline (default) floor -> generic below-threshold. At/above the
    # baseline but below the claim's stricter per-severity floor ->
    # below-severity-floor (distinct audit + message).
    if env.conf < threshold:
        return Decision(ABSTAIN, "below-threshold", env.missing)
    floor = resolve_floor(env.sev, threshold, severity_thresholds)
    if env.conf < floor:
        return Decision(ABSTAIN, "below-severity-floor", env.missing)
    return Decision(PASS, "ok")
