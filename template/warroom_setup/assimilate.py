"""Feature A — assimilate an existing (foreign) Hermes profile into the war room.

Adds war-room coordination capability to a Hermes profile that was NOT built
from this template, without clobbering its existing channel wiring, persona,
hooks, plugins, or skill bundles. The orchestration is composition over
shared-core (setup.patch_*, enroll.bootstrap, the channel walkthroughs); the
strictly-new code here is classification + a preserve-don't-clobber driver.

Stdlib only, Python >=3.9. Imports use the `from . import X` form deliberately
(the package forbids dotted-submodule imports of setup/cli to avoid cycles; see
test_security.test_no_module_imports_cli_or_setup_except_entrypoints).

T5 surface: classification helpers only (_classify / _detect_channels /
_already_assimilated). CLI + orchestrator land in later tasks.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import discord_walkthrough, enroll, runtime_state, setup
from . import slack_walkthrough, validators


def _utc_now_iso():
    # type: () -> str
    """ISO-8601 UTC timestamp for the assimilate audit trail."""
    return datetime.now(timezone.utc).isoformat()

# Exit-code contract (mirrors enroll's; consumed by the CLI dispatch in T6+).
EXIT_OK = 0            # assimilated (or dry-run reported cleanly)
EXIT_CLI_MISSING = 1   # mailbox CLI not found (config written; runtime inactive)
EXIT_ALREADY = 2       # already assimilated, --reconfigure not passed
EXIT_BAD_PROFILE = 3   # path invalid / not a Hermes profile
EXIT_ABORTED = 4       # walkthrough/identity validation failed, owner aborted,
#                        or an orphan war-room sentinel blocks a safe rewrite


def _config_text(profile_root):
    # type: (Path) -> str
    cfg = Path(profile_root) / "config.yaml"
    return cfg.read_text(encoding="utf-8") if cfg.exists() else ""


def _has_war_room_sentinel(profile_root):
    # type: (Path) -> bool
    """True iff config.yaml carries our exact war-room begin sentinel LINE. The
    sentinel string is distinctive enough that a substring check is safe."""
    return setup._WR_BEGIN in _config_text(profile_root)


def _has_enroll_state(profile_root):
    # type: (Path) -> bool
    return (Path(profile_root) / "local" / "warroom-enroll.json").exists()


def _already_assimilated(profile_root):
    # type: (Path) -> bool
    """A profile is assimilated only when BOTH the managed war-room sentinel
    block AND the enroll runtime-state file are present. Sentinel-without-state
    is an ORPHAN (see _classify), not an assimilated profile."""
    return _has_war_room_sentinel(profile_root) and _has_enroll_state(profile_root)


def _detect_channels(profile_root):
    # type: (Path) -> dict
    """Read <profile>/.env (if present) and report which channel bot tokens are
    already wired, so the orchestrator can skip those walkthroughs. A key present
    but empty does NOT count as configured."""
    profile_root = Path(profile_root)
    env_path = profile_root / ".env"
    channels = {"discord": False, "slack": False}
    if not env_path.exists():
        return channels
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        key, val = key.strip(), val.strip()
        if not val:
            continue
        if key == "DISCORD_BOT_TOKEN":
            channels["discord"] = True
        elif key == "SLACK_BOT_TOKEN":
            channels["slack"] = True
    return channels


def _classify(profile_root):
    # type: (Path) -> dict
    """Classify a candidate assimilate target. Returns a plain dict (the surface
    is intentionally tiny -- we do not reuse the installer's ProfileInspection
    dataclass, which lives in a different sys.path root and would couple
    warroom_setup to scripts/installer).

    Keys:
      exists               -- profile_root is a directory on disk
      is_hermes            -- has config.yaml
      is_awr_template      -- carries the warroom_setup/ package
      already_assimilated  -- war-room sentinel block AND enroll state present
      orphan_sentinel      -- sentinel present but enroll state ABSENT. Synthesis
                              fix (§3 vs §7): this is suspicious -- the
                              orchestrator refuses with exit 4 instead of
                              silently rewriting a block it may not own.
      channels             -- {"discord": bool, "slack": bool} from .env
      has_persona_decisions-- local/persona/decisions.md exists
    """
    profile_root = Path(profile_root)
    sentinel = _has_war_room_sentinel(profile_root)
    enrolled = _has_enroll_state(profile_root)
    return {
        "exists": profile_root.is_dir(),
        "is_hermes": (profile_root / "config.yaml").exists(),
        "is_awr_template": (profile_root / "warroom_setup" / "__init__.py").exists(),
        "already_assimilated": sentinel and enrolled,
        "orphan_sentinel": sentinel and not enrolled,
        "channels": _detect_channels(profile_root),
        "has_persona_decisions": (
            profile_root / "local" / "persona" / "decisions.md"
        ).exists(),
    }


def _existing_mailbox_board(profile_root):
    # type: (Path) -> Optional[str]
    """Return the MAILBOX_BOARD value already set in <profile>/.env, or None.
    Used to surface (and gate) a board overwrite (risk-2 mitigation)."""
    env_path = Path(profile_root) / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        if key.strip() == "MAILBOX_BOARD":
            return val.strip() or None
    return None


def _resolve_label(profile_root, label):
    # type: (Path, Optional[str]) -> Optional[str]
    """Resolve the board label: explicit `label`, else the `handle` from
    local/agent.json, else the profile directory name. Returns None if the
    resolved value fails handle validation (the caller maps that to exit 4)."""
    profile_root = Path(profile_root)
    candidate = (label or "").strip()
    if not candidate:
        agent_json = profile_root / "local" / "agent.json"
        if agent_json.exists():
            try:
                data = json.loads(agent_json.read_text(encoding="utf-8"))
                candidate = (data.get("handle") or "").strip()
            except (ValueError, OSError):
                candidate = ""
        if not candidate:
            candidate = profile_root.name
    return candidate if validators.valid_handle(candidate) else None


def _report(info, profile_root, board, label, out, dry_run=False,
            overwrite_board=None):
    # type: (dict, Path, str, str, object, bool, Optional[str]) -> None
    """Pre-flight summary of what assimilate will create/modify (§8 step 3)."""
    text = _config_text(profile_root)
    wr_present = setup._WR_BEGIN in text
    mb_present = setup._MB_BEGIN in text

    def pick(flag, yes_msg, no_msg):
        return yes_msg if flag else no_msg

    out.write("Assimilating %s (board=%s, label=%s):\n" % (profile_root, board, label))
    out.write("  hermes-managed:  %s\n" % ("yes" if info["is_hermes"] else "no"))
    out.write("  awr-template:    %s\n" % ("yes" if info["is_awr_template"] else "no"))
    out.write("  discord creds:   %s\n" % pick(
        info["channels"]["discord"], "present (skipping walkthrough)",
        "absent (will walk through)"))
    out.write("  slack creds:     %s\n" % pick(
        info["channels"]["slack"], "present (skipping walkthrough)",
        "absent (will walk through)"))
    out.write("  persona file:    %s\n" % pick(
        info["has_persona_decisions"], "present (will append sentinel-bounded rule)",
        "absent (will create + append rule)"))
    out.write("  war_room block:  %s\n" % pick(
        wr_present, "present (will update)", "absent (will create)"))
    out.write("  mailbox block:   %s\n" % pick(
        mb_present, "present (will update)", "absent (will create)"))
    if overwrite_board:
        out.write("  [overwrite: MAILBOX_BOARD=%s -> %s]\n" % (overwrite_board, board))
    if dry_run:
        out.write("[dry-run] no files written.\n")


def _default_prompts(in_stream, out, max_retries=3):
    """Build a UI-agnostic walkthrough `prompts` callable that reads answers from
    `in_stream` and echoes step text to `out`. Mirrors the installer's step
    driver (display body -> prompt -> validate/retry -> skip-optional-on-blank).
    Used only for the real interactive CLI; tests inject their own `prompts`."""
    def prompts(step, context=None):
        out.write("\n[%s] %s\n" % (step.n, step.title))
        for line in step.body_lines:
            out.write("  %s\n" % line)
        if not step.prompt_label:
            return ""
        attempts = 0
        while True:
            attempts += 1
            out.write("%s: " % step.prompt_label)
            try:
                out.flush()
            except Exception:  # pragma: no cover - guard real fds
                pass
            val = (in_stream.readline() or "").strip()
            if step.optional and val == "":
                return ""
            if step.validator is None or step.validator(val):
                return val
            if attempts >= max_retries:
                out.write("  still invalid after %d tries; skipping (set it "
                          "manually in .env later).\n" % max_retries)
                return ""
            out.write("  invalid; try again (%d/%d).\n" % (attempts, max_retries))
    return prompts


def _run_walkthroughs(info, no_walkthrough, yes, prompts, in_stream, out):
    # type: (dict, bool, bool, object, object, object) -> tuple
    """Conditionally run the Discord/Slack walkthroughs for channels whose creds
    are NOT already wired. Returns `(creds_env, walked)` where creds_env is the
    dict of .env values to merge and walked is the list of channel names a
    walkthrough was run for. Returns `(None, None)` to signal a headless usage
    error (caller maps to exit 4). Channels that already have creds
    (info["channels"]) are skipped to preserve existing wiring.
    """
    needs_discord = not info["channels"]["discord"]
    needs_slack = not info["channels"]["slack"]
    creds_env = {}  # type: dict
    walked = []  # type: list
    if no_walkthrough or not (needs_discord or needs_slack):
        return creds_env, walked

    driver = prompts
    if driver is None:
        if yes:
            out.write("assimilate: --yes needs --no-walkthrough (or pre-set "
                      "channel creds); cannot run an interactive walkthrough "
                      "headlessly\n")
            return None, None  # usage error -> exit 4
        driver = _default_prompts(
            in_stream if in_stream is not None else sys.stdin, out)

    if needs_discord:
        dc = discord_walkthrough.run_discord_walkthrough(driver, context="assimilate")
        if dc.bot_token:
            creds_env["DISCORD_BOT_TOKEN"] = dc.bot_token
        if dc.channel_id:
            creds_env["DISCORD_HOME_CHANNEL"] = dc.channel_id
        walked.append("discord")
    if needs_slack:
        sc = slack_walkthrough.run_slack_walkthrough(driver, context="assimilate")
        if sc.app_token:
            creds_env["SLACK_APP_TOKEN"] = sc.app_token
        if sc.bot_token:
            creds_env["SLACK_BOT_TOKEN"] = sc.bot_token
        if sc.channel_id:
            creds_env["SLACK_HOME_CHANNEL"] = sc.channel_id
        walked.append("slack")
    return creds_env, walked


def assimilate(profile_root, *, board="default", label=None, dry_run=False,
               reconfigure=False, no_walkthrough=False, enforce=False,
               yes=False, env=None, out=None, prompts=None, in_stream=None):
    # type: (...) -> int
    """Orchestrate assimilation of a foreign Hermes profile. Returns an exit code
    per the EXIT_* contract.

    Flow: classify (exit 3/2/4 + awr-template redirect) -> resolve label ->
    pre-flight report -> proceed-confirm (unless --yes/--dry-run) -> patch
    war_room (5a) + persona (5b). The walkthrough .env merge (5c/5d) and
    enroll.bootstrap + audit trail (T9) extend the patch section in later tasks.
    """
    out = out if out is not None else sys.stdout
    profile_root = Path(profile_root)
    info = _classify(profile_root)

    # 1. Classification short-circuits (§7).
    if not info["exists"] or not info["is_hermes"]:
        missing = "directory" if not info["exists"] else "config.yaml"
        out.write("assimilate: %s is not a Hermes profile (missing %s)\n"
                  % (profile_root, missing))
        return EXIT_BAD_PROFILE
    if info["is_awr_template"]:
        # A war-room template profile ships its own sentinel block and owns the
        # `warroom setup` / `warroom enroll` flow -- assimilate is for FOREIGN
        # profiles. Redirect (exit 0) rather than double-patch. Checked before
        # orphan_sentinel so the template's shipped (un-enrolled) sentinel is not
        # mistaken for a foreign orphan.
        out.write("assimilate: this is a war-room template profile; use "
                  "`warroom setup` / `warroom enroll --reconfigure` instead\n")
        return EXIT_OK
    if info["orphan_sentinel"] and not reconfigure:
        out.write("assimilate: config.yaml carries a war-room sentinel block but "
                  "this profile was never enrolled (no local/warroom-enroll.json); "
                  "manual review required (pass --reconfigure to force a rewrite)\n")
        return EXIT_ABORTED
    if info["already_assimilated"] and not reconfigure:
        out.write("assimilate: already assimilated (use --reconfigure to force "
                  "re-write)\n")
        return EXIT_ALREADY

    # 2. Resolve identity / board label.
    resolved_label = _resolve_label(profile_root, label)
    if resolved_label is None:
        out.write("assimilate: could not resolve a valid board label "
                  "(invalid handle); pass --label\n")
        return EXIT_ABORTED
    if not validators.valid_board_name(board):
        out.write("assimilate: invalid board name %r\n" % (board,))
        return EXIT_ABORTED

    # 2b. Detect a MAILBOX_BOARD overwrite (risk-2): an operator who tested
    #     mailbox standalone may already have a different board in .env.
    old_board = _existing_mailbox_board(profile_root)
    board_overwrite = bool(old_board) and old_board != board

    # 3. Pre-flight report.
    _report(info, profile_root, board, resolved_label, out, dry_run=dry_run,
            overwrite_board=old_board if board_overwrite else None)
    if dry_run:
        return EXIT_OK

    # 3b. A board overwrite needs an EXPLICIT ack. Interactively that is the
    #     proceed-confirm below; headlessly (--yes) it must be --reconfigure, so
    #     we never silently clobber an operator's existing board.
    if board_overwrite and yes and not reconfigure:
        out.write("assimilate: refusing to overwrite existing MAILBOX_BOARD=%s "
                  "with %s; pass --reconfigure to confirm\n" % (old_board, board))
        return EXIT_ABORTED

    # 4. Proceed-confirm (interactive unless --yes).
    if not yes:
        stream = in_stream if in_stream is not None else sys.stdin
        out.write("Proceed? [y/N] ")
        try:
            out.flush()
        except Exception:  # pragma: no cover - StringIO has flush; guard real fds
            pass
        resp = (stream.readline() or "").strip().lower()
        if resp not in ("y", "yes"):
            out.write("assimilate: aborted by operator (no changes written)\n")
            return EXIT_ABORTED

    # 4b. Walkthroughs (conditional) -- collect creds for channels not yet wired.
    creds_env, walked = _run_walkthroughs(
        info, no_walkthrough, yes, prompts, in_stream, out)
    if creds_env is None:
        return EXIT_ABORTED  # headless usage error
    has_channel = (info["channels"]["discord"] or info["channels"]["slack"]
                   or bool(creds_env))
    if not has_channel:
        out.write("warning: channels: none configured; war-room will be "
                  "CLI-only\n")

    # 5. Patches (atomic, preserve-don't-clobber).
    #    5d (synthesis fix): persist walkthrough creds to .env BEFORE
    #       enroll.bootstrap, so a later bootstrap failure never strands a
    #       freshly-collected Discord/Slack token. write_env merges (existing
    #       keys, e.g. an operator's other tokens, survive).
    if creds_env:
        setup.write_env(profile_root, creds_env, filename=".env")
    #    5a. war_room block. enforce defaults OFF -- gentler on an existing
    #        operator's outputs at first contact; --enforce opts in.
    setup.patch_war_room_block(profile_root, board, label=resolved_label,
                               enforce=enforce)
    #    5b. persona rule: idempotent append inside the runtime sentinel region;
    #        never clobbers the operator's own decisions.md content.
    setup.patch_persona_decisions(profile_root, setup._WARROOM_PERSONA_RULE,
                                  sentinel_id="warroom-runtime")
    #    5c. enroll.bootstrap: writes the mailbox: block, merges MAILBOX_BOARD/
    #        LABEL into .env, and persists local/warroom-enroll.json. We DO NOT
    #        mutate its contract (owned by shared-core / Feature C); a missing
    #        mailbox CLI yields status="cli-not-found" without raising.
    state = enroll.bootstrap(profile_root, board, resolved_label, env=env)
    #    5e. Audit trail -- kept SEPARATE from the enroll runtime state so
    #        `warroom enroll --status` reads only enroll state, not history.
    runtime_state.save_state(
        profile_root / "local" / "warroom-assimilate.json",
        {
            "timestamp": _utc_now_iso(),
            "board": board,
            "label": resolved_label,
            "channels_walked_through": walked,
            "enroll_status": state.status,
            "enforce": bool(enforce),
        },
    )

    # 6. Post-flight summary.
    out.write("\nAssimilated %s (board=%s, label=%s). Next:\n"
              % (profile_root, board, resolved_label))
    out.write("  - Restart this Claude session so MAILBOX_BOARD/LABEL load "
              "into env.\n")
    out.write("  - Run `mailbox ps` to see your peer; if it shows empty, the "
              "daemon may\n")
    out.write("    need a manual `mailbox` invocation to spawn.\n")
    out.write("  - Re-run with --reconfigure to change the board or label.\n")
    if state.status != "ok":
        # Risk-3 mitigation (synthesis): post-flight TEXT only -- we do not touch
        # enroll.bootstrap's contract. Config blocks are written; runtime inactive.
        out.write("\nwar-room: mailbox CLI not found -- the war_room + mailbox "
                  "config blocks are written but the runtime is inactive. Install "
                  "the mailbox runtime (template/README.md) and re-run "
                  "`warroom enroll`.\n")
        return EXIT_CLI_MISSING
    return EXIT_OK
