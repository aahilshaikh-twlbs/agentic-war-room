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
from pathlib import Path
from typing import Optional

from . import setup, validators

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


def _report(info, profile_root, board, label, out, dry_run=False):
    # type: (dict, Path, str, str, object, bool) -> None
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
    if dry_run:
        out.write("[dry-run] no files written.\n")


def assimilate(profile_root, *, board="default", label=None, dry_run=False,
               reconfigure=False, no_walkthrough=False, enforce=False,
               yes=False, env=None, out=None, prompts=None):
    # type: (...) -> int
    """Orchestrate assimilation of a foreign Hermes profile. Returns an exit code
    per the EXIT_* contract.

    T6 milestone: classification short-circuits (exit 3/2/4 + awr-template
    redirect) + identity resolution + pre-flight report. The walkthrough / patch
    / enroll steps land in T7-T9; until then a non-dry-run live call reports and
    returns 0 without writing (the "report-only" handler the build order
    specifies for this task).
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
    if info["orphan_sentinel"]:
        out.write("assimilate: config.yaml carries a war-room sentinel block but "
                  "this profile was never enrolled (no local/warroom-enroll.json); "
                  "manual review required\n")
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

    # 3. Pre-flight report.
    _report(info, profile_root, board, resolved_label, out, dry_run=dry_run)
    if dry_run:
        return EXIT_OK

    # 4-5: walkthroughs + patches + enroll land in T7-T9.
    return EXIT_OK
