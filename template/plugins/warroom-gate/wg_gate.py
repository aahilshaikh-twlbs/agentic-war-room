"""transform_llm_output callback for the war-room confidence gate.
Stdlib only, Python >=3.9.

CRITICAL: Hermes is fail-OPEN on hook error (it leaves text unchanged if the
hook raises - conversation_loop.py:4607). So this callback catches everything
and returns an abstention rather than raising. It returns None to leave text
unchanged (chatter / disabled / nothing to do), or a string to replace it.
"""
import os
import uuid
from pathlib import Path

import wg_audit
import wg_classify
import wg_envelope
import wg_gateconfig
import wg_policy
import wg_render
import wg_verify


# Severity rank for at/above comparisons. Higher number = more severe. Unknown
# tokens rank as default (lowest); `require_verifier_at` "" disables the path,
# and an unknown floor token ranks 99 so nothing is ever at/above it (safe).
_SEV_RANK = {"default": 0, "alert3": 1, "alert2": 2, "alert1": 3}


def _at_or_above(sev, floor_sev):
    # type: (str, str) -> bool
    if not floor_sev:
        return False
    return _SEV_RANK.get(sev, 0) >= _SEV_RANK.get(floor_sev, 99)


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
        # Hybrid inference (raise-only): in hybrid mode an untagged/default claim
        # with severity cue words is bumped to a stricter floor. Never lowers an
        # explicit tag; never produces alert1.
        if cfg["severity_inference"] == "hybrid":
            sev = wg_classify.infer_severity(
                body if env is not None else response_text, sev)
        decision = wg_policy.decide(
            True, env, threshold, severity_thresholds=cfg["severity_thresholds"],
            severity=sev)
        conf_pct = int(round(env.conf * 100)) if env is not None else None
        floor_pct = int(round(
            wg_policy.resolve_floor(sev, threshold, cfg["severity_thresholds"]) * 100))

        if decision.action != wg_policy.PASS:
            wg_audit.log(root, decision, conf, "claim", response_text,
                         verdict="claim", extra={"sev": sev, "verify": "none"})
            return wg_render.abstention(decision, conf_pct, floor_pct)

        # PASS so far. If this severity requires an independent verifier, obtain
        # a signed verdict before posting; any non-signed outcome abstains
        # (fail-closed). This whole call sits inside the top-level try/except.
        verify_state = "none"
        if _at_or_above(sev, cfg["require_verifier_at"]):
            res = wg_verify.request_and_wait(
                label=cfg["label"],
                verifier_label=cfg["verifier_label"],
                severity=sev,
                conf=env.conf,
                grounded=env.grounded,
                claim=body if env is not None else response_text,
                timeout_s=cfg["verifier_timeout_s"],
                request_id=uuid.uuid4().hex)
            outcome = res.get("outcome")
            if outcome == "signed":
                verify_state = "signed"
            else:
                verify_state = outcome or "unreachable"
                reason = {
                    "rejected": "verifier-rejected",
                    "timeout": "verifier-timeout",
                    "unreachable": "verifier-unreachable",
                }.get(verify_state, "verifier-unreachable")
                abstain = wg_policy.Decision(
                    wg_policy.ABSTAIN, reason, res.get("gap", ""))
                wg_audit.log(root, abstain, conf, "claim", response_text,
                             verdict="claim",
                             extra={"sev": sev, "verify": verify_state})
                return wg_render.abstention(abstain, conf_pct, floor_pct)

        wg_audit.log(root, decision, conf, "claim", response_text,
                     verdict="claim", extra={"sev": sev, "verify": verify_state})
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
