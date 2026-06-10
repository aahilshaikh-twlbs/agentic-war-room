"""transform_llm_output callback for the war-room confidence gate.
Stdlib only, Python >=3.9.

CRITICAL: Hermes is fail-OPEN on hook error (it leaves text unchanged if the
hook raises - conversation_loop.py:4607). So this callback catches everything
and returns an abstention rather than raising. It returns None to leave text
unchanged (chatter / disabled / nothing to do), or a string to replace it.
"""
import os
from pathlib import Path

import wg_audit
import wg_classify
import wg_envelope
import wg_gateconfig
import wg_policy
import wg_render


def _profile_root():
    # type: () -> Path
    hh = os.environ.get("HERMES_HOME")
    if hh:
        return Path(hh)
    # Fallback: plugin dir is <profile>/plugins/warroom-gate/ -> parents[2] = profile.
    return Path(__file__).resolve().parents[2]


def gate(response_text="", session_id="", model="", platform="", **_):
    # type: (str, str, str, str, object) -> object
    try:
        if not isinstance(response_text, str) or not response_text.strip():
            return None
        root = _profile_root()
        cfg = wg_gateconfig.read(root)
        if not cfg["enforce"]:
            return None

        env, body = wg_envelope.parse_last_line(response_text)
        claim = wg_classify.is_claim(body if env is not None else response_text)

        conf = env.conf if env is not None else None
        if not claim:
            # Log the chatter decision (verdict=chatter) so under-gating is no
            # longer invisible. decide(False, ...) returns Decision(PASS,
            # "chatter") without reading env or threshold (wg_policy.py:20-21);
            # constructed directly to avoid a meaningless threshold argument.
            wg_audit.log(root, wg_policy.Decision(wg_policy.PASS, "chatter"),
                         conf, "chatter", response_text, verdict="chatter")
            cleaned = wg_envelope.strip_stray_envelopes(response_text).rstrip()
            return cleaned if cleaned != response_text.rstrip() else None

        threshold = cfg["min_confidence"] / 100.0
        sev = env.sev if env is not None else "default"
        decision = wg_policy.decide(
            True, env, threshold, severity_thresholds=cfg["severity_thresholds"])
        conf_pct = int(round(env.conf * 100)) if env is not None else None
        floor_pct = int(round(
            wg_policy.resolve_floor(sev, threshold, cfg["severity_thresholds"]) * 100))

        if decision.action != wg_policy.PASS:
            wg_audit.log(root, decision, conf, "claim", response_text,
                         verdict="claim", extra={"sev": sev, "verify": "none"})
            return wg_render.abstention(decision, conf_pct, floor_pct)

        # PASS so far. The verifier handshake (Task 6) composes here; in Phase 1
        # there is no verifier, so `verify` is "none".
        wg_audit.log(root, decision, conf, "claim", response_text,
                     verdict="claim", extra={"sev": sev, "verify": "none"})
        out = wg_render.with_badge(body, env.conf, cfg["show_badge"]) if env is not None else body
        return out if out != response_text else None
    except Exception:
        # FAIL CLOSED: never propagate (Hermes would pass the ungated text).
        try:
            return wg_render.abstention(
                wg_policy.Decision(wg_policy.ABSTAIN, "internal-error"), None, None)
        except Exception:
            return "\U0001f6d1 Holding back - gate error; not posting unverified info."


def register(ctx):
    ctx.register_hook("transform_llm_output", gate)
