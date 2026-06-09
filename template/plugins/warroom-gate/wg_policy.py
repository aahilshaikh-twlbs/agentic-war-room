"""Gate decision. Stdlib only, Python >=3.9. Pure."""
from dataclasses import dataclass
from typing import Optional

from wg_envelope import Envelope

PASS = "pass"
ABSTAIN = "abstain"


@dataclass
class Decision:
    action: str          # PASS | ABSTAIN
    reason: str          # chatter | ok | no-envelope | ungrounded | below-threshold | empty-body | internal-error
    missing: str = ""


def decide(is_claim, env, threshold):
    # type: (bool, Optional[Envelope], float) -> Decision
    if not is_claim:
        return Decision(PASS, "chatter")
    if env is None:
        return Decision(ABSTAIN, "no-envelope")
    if not env.grounded or env.grounded == ("none",):
        return Decision(ABSTAIN, "ungrounded", env.missing)
    if env.conf < threshold:
        return Decision(ABSTAIN, "below-threshold", env.missing)
    return Decision(PASS, "ok")
