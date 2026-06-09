"""Abstention + badge rendering. Stdlib only, Python >=3.9. Pure."""
from typing import Optional

from wg_policy import Decision


def abstention(decision, conf_pct=None, threshold_pct=None):
    # type: (Decision, Optional[int], Optional[int]) -> str
    miss = decision.missing or "more grounded evidence"
    if decision.reason == "below-threshold" and conf_pct is not None and threshold_pct is not None:
        return ("\U0001f6d1 Holding back - not confident enough to post that "
                "(%d%% < %d%% bar).\n   To clear it I'd need: %s." % (conf_pct, threshold_pct, miss))
    if decision.reason == "ungrounded":
        return ("\U0001f6d1 Holding back - that claim isn't grounded in evidence I can cite.\n"
                "   To clear it I'd need: %s." % miss)
    if decision.reason == "no-envelope":
        return ("\U0001f6d1 Holding back - no confidence envelope on a claim; "
                "not posting unverified info to the war room.")
    if decision.reason == "empty-body":
        return ("\U0001f6d1 Holding back - a confidence envelope with no content "
                "to post; nothing to say to the war room.")
    return ("\U0001f6d1 Holding back - gate error; not posting unverified info to the war room.")


def with_badge(body, conf, show):
    # type: (str, float, bool) -> str
    if not show:
        return body
    pct = int(round(conf * 100))
    return body.rstrip("\n") + "\n\n- \u2713 %d%%" % pct
