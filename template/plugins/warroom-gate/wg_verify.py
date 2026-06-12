"""Independent-verifier client for the war-room confidence gate. Stdlib only,
Python >=3.9.

When a claim's severity is at/above `require_verifier_at`, the gate (wg_gate)
calls request_and_wait(): post a verification request to the verifier's mailbox
label, then block (bounded by a monotonic deadline) for a signed verdict. Every
failure path resolves to a non-"signed" outcome so the caller abstains
(fail-closed). The ONLY side effect is the mailbox CLI subprocess; this module
never imports mailbox.client and never touches .env / auth.json / local/.

DV2: the gate plugin runs in the Hermes gateway with only its own dir on
sys.path, so warroom_setup.enroll is not importable here. discover_cli mirrors
enroll.discover_mailbox_cli's precedence (env MAILBOX_HOME -> standard install
-> PATH) using stdlib only.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional


def discover_cli(env=None):
    # type: (Optional[dict]) -> Optional[str]
    """Locate an executable `mailbox` CLI (str path) or None. Mirrors
    enroll.discover_mailbox_cli precedence minus the dev-checkout fallback."""
    e = env if env is not None else os.environ
    candidates = []
    mh = (e.get("MAILBOX_HOME") or "").strip()
    if mh:
        candidates.append(Path(mh) / "mailbox")
    home = Path(e.get("HOME") or os.path.expanduser("~"))
    candidates.append(home / ".claude" / "mailbox" / "mailbox")
    for c in candidates:
        try:
            if c.is_file() and os.access(str(c), os.X_OK):
                return str(c)
        except OSError:
            pass
    which = shutil.which("mailbox", path=e.get("PATH"))
    return which if which else None


def build_request(label, severity, conf, grounded, claim, request_id):
    # type: (str, str, float, tuple, str, str) -> str
    """The verify_request JSON body. Carries the full claim text (D6: the
    verifier cannot judge what it cannot read; single-host mailbox). The audit
    log still records only the sha (caller's responsibility)."""
    claim_sha = hashlib.sha256((claim or "").encode("utf-8")).hexdigest()[:8]
    return json.dumps({
        "kind": "verify_request",
        "request_id": request_id,
        "from": label,
        "severity": severity,
        "conf": conf,
        "grounded": list(grounded),
        "claim_sha": claim_sha,
        "claim": claim,
    })


def _run(cli, argv, env, timeout):
    # type: (str, list, dict, int) -> Optional[subprocess.CompletedProcess]
    """Run the mailbox CLI; return the completed process or None on any OS-level
    failure (treated as unreachable by the caller)."""
    try:
        return subprocess.run(
            [cli] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def request_and_wait(label, verifier_label, severity, conf, grounded, claim,
                     timeout_s, request_id, poll_interval_s=0.5, env=None):
    # type: (str, str, str, float, tuple, str, int, str, float, Optional[dict]) -> dict
    """Post a verify request and block (bounded) for a signed verdict.

    Returns {"outcome": one of signed|rejected|timeout|unreachable,
             "gap": <str, on rejected>, "by": <verifier label>}.
    The caller (wg_gate) maps every non-"signed" outcome to an abstention."""
    # D8 self-verification + blank-label guards: cannot verify -> cannot post.
    vl = (verifier_label or "").strip()
    if not vl or vl == label:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    cli = discover_cli(env)
    if cli is None:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    e = dict(env if env is not None else os.environ)
    body = build_request(label, severity, conf, grounded, claim, request_id)

    # Post the directed request. DV3: scope=local is correct for a same-board
    # designated verifier; --to <label> is the directed filter the recipient's
    # poll_inbox matches.
    sent = _run(cli, ["send", body, "--to", vl, "--kind", "verify_request"],
                e, timeout=15)
    if sent is None or sent.returncode != 0:
        return {"outcome": "unreachable", "gap": "", "by": vl}

    # Bounded poll on a MONOTONIC deadline (never time-of-day; never unbounded).
    deadline = time.monotonic() + max(0, timeout_s)
    while time.monotonic() < deadline:
        got = _run(cli, ["inbox", "--json", "--local"], e, timeout=15)
        if got is not None and got.returncode == 0:
            verdict = _scan_inbox(got.stdout, verifier_label=vl,
                                  request_id=request_id)
            if verdict is not None:
                return verdict
        if poll_interval_s > 0:
            time.sleep(poll_interval_s)
        else:
            # poll_interval 0 (tests): re-check the clock and bail if past
            # deadline so the fake monotonic sequence terminates the loop.
            if time.monotonic() >= deadline:
                break
    return {"outcome": "timeout", "gap": "", "by": vl}


def _scan_inbox(stdout, verifier_label, request_id):
    # type: (bytes, str, str) -> Optional[dict]
    """Find a matching verdict in a JSON inbox dump, or None. A verdict is
    accepted only when (a) the message sender (transport-authenticated
    from_label) is the configured verifier, AND (b) the embedded request_id
    echoes ours. Malformed JSON / mismatches are ignored (not fatal)."""
    try:
        rows = json.loads(stdout.decode("utf-8") if isinstance(stdout, bytes) else stdout)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(rows, list):
        return None
    for m in rows:
        if not isinstance(m, dict):
            continue
        # Transport authentication: trust the sender label, not the body's `by`.
        if m.get("from_label") != verifier_label:
            continue
        try:
            payload = json.loads(m.get("body", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("kind") != "verify_verdict":
            continue
        if payload.get("request_id") != request_id:
            continue
        v = payload.get("verdict")
        if v == "signed":
            # DV6: the verifier's own `envelope` is informational in v1 — the gate
            # posts the ORIGINATOR's badge, so a signed verb from the authenticated
            # verifier with a matching request_id is sufficient; we do not parse or
            # require payload["envelope"]. The trust boundary is the transport
            # sender + the explicit `signed` verb, not the envelope's presence.
            return {"outcome": "signed", "gap": "", "by": verifier_label}
        if v == "rejected":
            return {"outcome": "rejected",
                    "gap": str(payload.get("gap") or "verifier could not confirm"),
                    "by": verifier_label}
        # unknown verdict value: ignore this message, keep polling
    return None
