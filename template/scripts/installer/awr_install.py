"""AWR interactive installer -- TUI entry point.

Collapses the four-step manual path (hermes profile install -> warroom setup ->
hermes plugins enable -> first-chat enroll) into one continuous flow. This
module owns the CLI surface (:func:`build_parser`) and the top-level dispatch
(:func:`main`). The interactive wizard (T5), in-process execute phase (T6),
headless mode (T9) and uninstall (T11) hang off this skeleton.

Stdlib only, Python >=3.9. Run as ``python3 -m awr_install`` with the installer
directory on ``PYTHONPATH`` (the launcher does this).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import in_process_orchestrator as orch
import masked_prompt
import profile_detect
import rollback as rollback_mod
import sidecar_state
from _substrate import validators
from _substrate.discord_walkthrough import (
    DiscordCreds,
    Step,
    WALKTHROUGH_STEPS,
    run_discord_walkthrough,
)
from _substrate.slack_walkthrough import (
    SLACK_WALKTHROUGH_STEPS,
    SlackCreds,
    run_slack_walkthrough,
)

__version__ = "0.1.0"

_DESCRIPTION = (
    "AWR interactive installer: one flow for hermes profile install, in-process "
    "setup (.env + identity + YAML patches), plugin enable, and cross-agent "
    "enroll. Esc aborts; partial installs can be --resume'd."
)


def build_parser(prog: str = "awr_install") -> argparse.ArgumentParser:
    """Construct the full argument parser.

    Defaults are deliberately omitted for operator-supplied identity/board
    values so headless mode (T9) can detect "not provided" and error, while the
    interactive wizard (T5) supplies its own prompt defaults.
    """
    p = argparse.ArgumentParser(prog=prog, description=_DESCRIPTION)

    # Mode / lifecycle.
    p.add_argument("--headless", action="store_true",
                   help="run non-interactively from flags/env (no prompts)")
    p.add_argument("--resume", action="store_true",
                   help="resume a partial install from the ~/.awr sidecar")
    p.add_argument("--uninstall", metavar="NAME",
                   help="uninstall the named profile and clean installer state")
    p.add_argument("--dry-run", action="store_true",
                   help="plan only; run no subprocesses and mutate nothing")
    p.add_argument("--verbose", action="store_true",
                   help="tee subprocess output to stderr")
    p.add_argument("--force", action="store_true",
                   help="proceed past a profile collision (see docs §8)")
    p.add_argument("--stage-timeout", type=float, default=300.0, metavar="SECONDS",
                   help="per-stage subprocess timeout (default: 300)")

    # Source + target.
    p.add_argument("--source", metavar="PATH_OR_URL",
                   help="distribution source (local dir or git URL); "
                        "default = the template/ dir containing this installer")
    p.add_argument("--name", metavar="NAME", help="profile name (slug)")
    p.add_argument("--board", metavar="NAME", help="mailbox board (default: shared)")
    p.add_argument("--label", metavar="NAME", help="mailbox label (default: profile name)")

    # Channels.
    p.add_argument("--discord", action="store_true", help="enable Discord channel")
    p.add_argument("--slack", action="store_true", help="enable Slack channel")
    p.add_argument("--no-channels", action="store_true", help="skip channel setup")

    # Identity (C7).
    p.add_argument("--agent-name", metavar="NAME", help="agent name")
    p.add_argument("--display-name", metavar="NAME", help="human-facing display name")
    p.add_argument("--handle", metavar="HANDLE", help="operator handle")
    p.add_argument("--discord-allowed-users", action="append", metavar="USER",
                   help="allowed Discord user (repeatable)")
    p.add_argument("--min-confidence", type=int, default=75, metavar="N",
                   help="persona min-confidence gate (default: 75)")
    p.add_argument("--model", choices=["opus", "sonnet"], default="opus",
                   help="primary model (default: opus)")

    # Channel ids (headless; interactive collects these via the walkthroughs).
    p.add_argument("--discord-channel-id", metavar="ID")
    p.add_argument("--discord-second-channel-id", metavar="ID")
    p.add_argument("--slack-channel-id", metavar="ID")
    p.add_argument("--slack-second-channel-id", metavar="ID")

    # Secrets: env-var name OR file path (F20). Never accepted as a literal flag.
    p.add_argument("--anthropic-key-env", metavar="VAR")
    p.add_argument("--anthropic-key-file", metavar="PATH")
    p.add_argument("--discord-token-env", metavar="VAR")
    p.add_argument("--discord-token-file", metavar="PATH")
    p.add_argument("--slack-app-token-env", metavar="VAR")
    p.add_argument("--slack-app-token-file", metavar="PATH")
    p.add_argument("--slack-bot-token-env", metavar="VAR")
    p.add_argument("--slack-bot-token-file", metavar="PATH")

    return p


# =========================================================================== #
# T5 -- interactive TUI orchestration
# =========================================================================== #
@dataclass
class InstallerAnswers:
    source: str
    profile_name: str
    channels: Set[str]
    discord_creds: Optional[DiscordCreds]
    slack_creds: Optional[SlackCreds]
    anthropic_key: Optional[str]
    agent_name: str
    display_name: str
    handle: str
    discord_allowed_users: List[str]
    min_confidence: int
    model: str  # "opus" | "sonnet"
    board: str
    label: str


class WizardBack(Exception):
    """A stage requested navigation to its predecessor (Esc)."""


class WizardAbort(Exception):
    """A stage requested abort (EOF, or an explicit quit)."""

    def __init__(self, *, write_sidecar: bool = True, reason: str = ""):
        super().__init__(reason)
        self.write_sidecar = write_sidecar
        self.reason = reason


# Control sentinels a caller (real raw-mode renderer, or a test stream) can feed
# on a line to drive navigation deterministically.
_ESC = "\x1b"
_ETX = "\x03"  # Ctrl-C

ALL_STAGES = [
    "source", "name", "channels", "discord", "slack",
    "anthropic", "identity", "model", "board", "confirm",
]

SETTINGS_JSON_NOTICE = "Will modify ~/.claude/settings.json (mailbox hooks)"


class WizardIO:
    """Cooked, injectable line I/O for the wizard.

    A line equal to the ESC sentinel raises :class:`WizardBack`; a line equal to
    the Ctrl-C sentinel raises ``KeyboardInterrupt``; EOF raises
    :class:`WizardAbort`. This lets tests drive every key-binding deterministically
    while a real raw-mode renderer feeds the same sentinels.
    """

    def __init__(self, infile=None, outfile=None):
        self.infile = infile if infile is not None else sys.stdin
        self.outfile = outfile if outfile is not None else sys.stdout

    def write(self, s: str) -> None:
        self.outfile.write(s)
        self.outfile.flush()

    def ask(self, label: str, *, default: Optional[str] = None) -> str:
        suffix = " [%s]" % default if default not in (None, "") else ""
        self.write("%s%s: " % (label, suffix))
        raw = self.infile.readline()
        if raw == "":
            raise WizardAbort(write_sidecar=True, reason="eof")
        s = raw.rstrip("\n")
        if s == _ESC:
            raise WizardBack()
        if s == _ETX:
            raise KeyboardInterrupt()
        s = s.strip()
        if s == "" and default not in (None, ""):
            return default
        return s

    def ask_secret(self, label: str) -> str:
        return masked_prompt.prompt_secret(label, infile=self.infile, outfile=self.outfile)


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
def _is_active(name: str, channels: Set[str]) -> bool:
    if name == "discord":
        return "discord" in channels
    if name == "slack":
        return "slack" in channels
    return True


def _back_target(name: str, channels: Set[str]) -> str:
    """Stage to return to when ``name`` raises WizardBack (§3 table)."""
    if name == "confirm":
        return "source"  # confirm Esc returns to source (§3 step 12)
    idx = ALL_STAGES.index(name)
    j = idx - 1
    while j >= 0 and not _is_active(ALL_STAGES[j], channels):
        j -= 1
    return ALL_STAGES[j] if j >= 0 else "source"


# --------------------------------------------------------------------------- #
# Source / git validation
# --------------------------------------------------------------------------- #
def _looks_like_url(value: str) -> bool:
    v = (value or "").strip()
    return (
        v.startswith(("http://", "https://", "git@", "ssh://", "git://"))
        or "github.com/" in v
        or "github.com:" in v
    )


def _default_git_runner(url: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--exit-code", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, timeout=30,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def default_source() -> str:
    """The template/ directory containing this installer (C4: parents[2])."""
    return str(Path(__file__).resolve().parents[2])


# --------------------------------------------------------------------------- #
# Stages (each returns a value; raises WizardBack/WizardAbort for navigation)
# --------------------------------------------------------------------------- #
def _stage_source(io: WizardIO, *, default: str, git_runner=None) -> str:
    git_runner = git_runner or _default_git_runner
    while True:
        val = io.ask("Source path or git URL", default=default)
        if _looks_like_url(val):
            if git_runner(val):
                return val
            io.write("  git URL unreachable (git ls-remote failed); retry.\n")
            continue
        p = Path(val).expanduser()
        if p.is_dir() and (p / "distribution.yaml").exists():
            return str(p)
        io.write("  need a directory containing distribution.yaml; retry.\n")


def _stage_name(io: WizardIO) -> str:
    while True:
        val = io.ask("Profile name")
        if validators.valid_slug(val):
            return val
        io.write("  invalid slug (lowercase, leading letter, dashes ok); retry.\n")


def _stage_channels(io: WizardIO) -> Set[str]:
    val = io.ask("Channels: discord, slack, both, or none", default="discord")
    parts = {p.strip().lower() for p in val.replace(",", " ").split()}
    channels: Set[str] = set()
    if "both" in parts or "discord" in parts:
        channels.add("discord")
    if "both" in parts or "slack" in parts:
        channels.add("slack")
    return channels


def _run_walkthrough_step(io: WizardIO, step: Step, *, max_retries: int = 3) -> str:
    """Display a walkthrough step and collect/validate its answer (C13/K3/K18).

    Info-only steps return "". Optional steps are skippable with empty input.
    Validators retry up to ``max_retries`` times, then skip-with-warning.
    """
    io.write("\n[%s] %s\n" % (step.n, step.title))
    for line in step.body_lines:
        io.write("  %s\n" % line)
    if not step.prompt_label:
        return ""
    secret = "token" in step.prompt_label.lower()
    attempts = 0
    while True:
        attempts += 1
        val = (io.ask_secret(step.prompt_label) if secret else io.ask(step.prompt_label)).strip()
        if step.optional and val == "":
            return ""  # K18: skip optional step
        if step.validator is None or step.validator(val):
            return val
        if attempts >= max_retries:
            io.write("  still invalid after %d tries; skipping (set manually later).\n" % max_retries)
            return ""
        io.write("  invalid; try again (%d/%d).\n" % (attempts, max_retries))


def _walkthrough_adapter(io: WizardIO):
    def adapter(step, *, context=None):
        return _run_walkthrough_step(io, step)
    return adapter


def _stage_discord(io: WizardIO) -> DiscordCreds:
    return run_discord_walkthrough(_walkthrough_adapter(io), context="installer")


def _stage_slack(io: WizardIO) -> SlackCreds:
    return run_slack_walkthrough(_walkthrough_adapter(io), context="installer")


def _stage_anthropic(io: WizardIO) -> Optional[str]:
    while True:
        val = (io.ask_secret("Anthropic API key (enter to skip)") or "").strip()
        if val == "":
            io.write("  skipped; set ANTHROPIC_API_KEY before first chat.\n")
            return None
        if val.startswith("sk-ant-") and len(val) >= 40:
            return val
        io.write("  key should start with sk-ant- and be >=40 chars; retry.\n")


def _stage_identity(io: WizardIO, *, default_name: str) -> Dict[str, object]:
    while True:
        agent_name = io.ask("Agent name", default=default_name)
        if validators.valid_slug(agent_name):
            break
        io.write("  invalid slug; retry.\n")
    display_name = io.ask("Display name", default=agent_name)
    while True:
        handle = io.ask("Operator handle", default=agent_name)
        if validators.valid_handle(handle):
            break
        io.write("  invalid handle; retry.\n")
    allowed_raw = io.ask("Discord allowed users (comma-separated, optional)", default="")
    allowed = [u.strip() for u in allowed_raw.replace(",", " ").split() if u.strip()]
    while True:
        mc_raw = io.ask("Min confidence (0-100)", default="75")
        try:
            mc = max(0, min(100, int(mc_raw)))
            break
        except ValueError:
            io.write("  enter an integer 0-100; retry.\n")
    return {
        "agent_name": agent_name,
        "display_name": display_name,
        "handle": handle,
        "discord_allowed_users": allowed,
        "min_confidence": mc,
    }


def resolve_model(toggles: Set[str]) -> str:
    """Dual-toggle precedence per setup.py:385 (C8): opus wins unless only sonnet."""
    return "sonnet" if ("model.sonnet" in toggles and "model.opus" not in toggles) else "opus"


def _stage_model(io: WizardIO) -> str:
    val = io.ask("Model: opus, sonnet, or both", default="opus")
    parts = {p.strip().lower() for p in val.replace(",", " ").split()}
    toggles: Set[str] = set()
    if "both" in parts or "opus" in parts:
        toggles.add("model.opus")
    if "both" in parts or "sonnet" in parts:
        toggles.add("model.sonnet")
    return resolve_model(toggles)


def _stage_board_label(io: WizardIO, *, default_label: str) -> Dict[str, str]:
    while True:
        board = io.ask("Mailbox board", default="shared")
        if validators.valid_board_name(board):
            break
        io.write("  invalid board name; retry.\n")
    while True:
        label = io.ask("Mailbox label", default=default_label)
        if validators.valid_handle(label):
            break
        io.write("  invalid label; retry.\n")
    return {"board": board, "label": label}


def render_confirmation(acc: "_Acc") -> str:
    """Confirmation summary; always lists the settings.json side-effect (K11)."""
    channels = ", ".join(sorted(acc.channels)) or "none"
    lines = [
        "About to install:",
        "  Source:        %s" % acc.source,
        "  Profile name:  %s" % acc.profile_name,
        "  Target:        ~/.hermes/profiles/%s" % acc.profile_name,
        "  Channels:      %s" % channels,
        "  Model:         %s" % acc.model,
        "  Board / label: %s / %s" % (acc.board, acc.label),
        "  Anthropic key: %s" % ("******** (-> .env)" if acc.anthropic_key else "(not set)"),
        "",
        "  %s" % SETTINGS_JSON_NOTICE,
        "",
    ]
    return "\n".join(lines)


def _stage_confirm(io: WizardIO, acc: "_Acc") -> bool:
    io.write(render_confirmation(acc))
    val = io.ask("Proceed? [Enter to install, q to abort]", default="yes").strip().lower()
    if val in ("q", "quit", "abort", "n", "no"):
        raise WizardAbort(write_sidecar=False, reason="user-quit-at-confirm")
    return True


# --------------------------------------------------------------------------- #
# Accumulator + orchestration
# --------------------------------------------------------------------------- #
@dataclass
class _Acc:
    source: Optional[str] = None
    profile_name: Optional[str] = None
    channels: Set[str] = field(default_factory=set)
    discord_creds: Optional[DiscordCreds] = None
    slack_creds: Optional[SlackCreds] = None
    anthropic_key: Optional[str] = None
    agent_name: Optional[str] = None
    display_name: Optional[str] = None
    handle: Optional[str] = None
    discord_allowed_users: List[str] = field(default_factory=list)
    min_confidence: int = 75
    model: str = "opus"
    board: Optional[str] = None
    label: Optional[str] = None


def _finalize(acc: "_Acc") -> InstallerAnswers:
    name = acc.profile_name or ""
    return InstallerAnswers(
        source=acc.source or default_source(),
        profile_name=name,
        channels=set(acc.channels),
        discord_creds=acc.discord_creds,
        slack_creds=acc.slack_creds,
        anthropic_key=acc.anthropic_key,
        agent_name=acc.agent_name or name,
        display_name=acc.display_name or acc.agent_name or name,
        handle=acc.handle or acc.agent_name or name,
        discord_allowed_users=list(acc.discord_allowed_users),
        min_confidence=acc.min_confidence,
        model=acc.model,
        board=acc.board or "shared",
        label=acc.label or name,
    )


def sidecar_payload(acc: "_Acc") -> Dict[str, object]:
    """Non-secret snapshot for the resume sidecar (T7 persists it)."""
    return {
        "profile_name": acc.profile_name,
        "source": acc.source,
        "channels": sorted(acc.channels),
        "agent_name": acc.agent_name,
        "display_name": acc.display_name,
        "handle": acc.handle,
        "discord_allowed_users": list(acc.discord_allowed_users),
        "min_confidence": acc.min_confidence,
        "model": acc.model,
        "board": acc.board,
        "label": acc.label,
    }


def _run_stage(name: str, io: WizardIO, acc: "_Acc", *, args, git_runner=None) -> None:
    if name == "source":
        acc.source = _stage_source(io, default=getattr(args, "source", None) or default_source(),
                                   git_runner=git_runner)
    elif name == "name":
        acc.profile_name = _stage_name(io)
    elif name == "channels":
        acc.channels = _stage_channels(io)
    elif name == "discord":
        acc.discord_creds = _stage_discord(io)
    elif name == "slack":
        acc.slack_creds = _stage_slack(io)
    elif name == "anthropic":
        acc.anthropic_key = _stage_anthropic(io)
    elif name == "identity":
        ident = _stage_identity(io, default_name=acc.profile_name or "")
        acc.agent_name = ident["agent_name"]
        acc.display_name = ident["display_name"]
        acc.handle = ident["handle"]
        acc.discord_allowed_users = ident["discord_allowed_users"]
        acc.min_confidence = ident["min_confidence"]
    elif name == "model":
        acc.model = _stage_model(io)
    elif name == "board":
        bl = _stage_board_label(io, default_label=acc.profile_name or "")
        acc.board = bl["board"]
        acc.label = bl["label"]
    elif name == "confirm":
        _stage_confirm(io, acc)


class HeadlessError(Exception):
    """A required headless flag or secret is missing/unreadable (F10)."""


def _read_secret(args, env_attr: str, file_attr: str, env: Dict[str, str]) -> Optional[str]:
    """Resolve a secret from --*-env VAR or --*-file PATH (F20). Never a literal.

    Aborts (HeadlessError) when the named env var is unset/empty or the file is
    missing -- a specified-but-unresolvable secret is a hard error (F10).
    """
    var = getattr(args, env_attr, None)
    path = getattr(args, file_attr, None)
    if var:
        val = env.get(var)
        if not val:
            raise HeadlessError("required env var %s is not set" % var)
        return val.strip()
    if path:
        p = Path(path)
        if not p.is_file():
            raise HeadlessError("token file not found: %s" % path)
        return p.read_text(encoding="utf-8").strip()
    return None


def build_headless_answers(args, *, env: Optional[Dict[str, str]] = None) -> InstallerAnswers:
    """Map CLI flags + resolved secrets to answers (no prompting, F20/F10).

    Requires --name, --source, --board, --agent-name, --display-name. Secrets
    come from --*-env / --*-file; channels are taken from --discord/--slack and
    their walkthroughs are skipped entirely (tokens supplied via flags).
    """
    env = env if env is not None else os.environ

    required = {
        "name": "--name", "source": "--source", "board": "--board",
        "agent_name": "--agent-name", "display_name": "--display-name",
    }
    missing = [flag for attr, flag in required.items() if not getattr(args, attr, None)]
    if missing:
        raise HeadlessError("headless mode requires: %s" % ", ".join(sorted(missing)))

    channels: Set[str] = set()
    if getattr(args, "discord", False):
        channels.add("discord")
    if getattr(args, "slack", False):
        channels.add("slack")

    anthropic_key = _read_secret(args, "anthropic_key_env", "anthropic_key_file", env)

    discord_creds = None
    if "discord" in channels:
        token = _read_secret(args, "discord_token_env", "discord_token_file", env)
        discord_creds = DiscordCreds(
            bot_token=token or "",
            channel_id=getattr(args, "discord_channel_id", None) or "",
            second_channel_id=getattr(args, "discord_second_channel_id", None) or "",
        )

    slack_creds = None
    if "slack" in channels:
        app = _read_secret(args, "slack_app_token_env", "slack_app_token_file", env)
        bot = _read_secret(args, "slack_bot_token_env", "slack_bot_token_file", env)
        slack_creds = SlackCreds(
            app_token=app or "",
            bot_token=bot or "",
            channel_id=getattr(args, "slack_channel_id", None) or "",
            second_channel_id=getattr(args, "slack_second_channel_id", None) or "",
        )

    name = args.name
    return InstallerAnswers(
        source=args.source,
        profile_name=name,
        channels=channels,
        discord_creds=discord_creds,
        slack_creds=slack_creds,
        anthropic_key=anthropic_key,
        agent_name=args.agent_name,
        display_name=args.display_name,
        handle=getattr(args, "handle", None) or args.agent_name,
        discord_allowed_users=list(getattr(args, "discord_allowed_users", None) or []),
        min_confidence=getattr(args, "min_confidence", 75),
        model=getattr(args, "model", "opus") or "opus",
        board=args.board,
        label=getattr(args, "label", None) or name,
    )


def run_tui(args, *, io=None, sidecar=None, restore=None, git_runner=None) -> Optional[InstallerAnswers]:
    """Drive the interactive wizard and return collected answers (or None on
    abort). Headless mode short-circuits to flag-mapping."""
    if getattr(args, "headless", False):
        return build_headless_answers(args)

    io = io if io is not None else WizardIO()
    restore = restore if restore is not None else masked_prompt.emergency_restore
    acc = _Acc()
    i = 0
    try:
        while i < len(ALL_STAGES):
            name = ALL_STAGES[i]
            if not _is_active(name, acc.channels):
                i += 1
                continue
            try:
                _run_stage(name, io, acc, args=args, git_runner=git_runner)
            except WizardBack:
                target = _back_target(name, acc.channels)
                i = ALL_STAGES.index(target)
                continue
            i += 1
        return _finalize(acc)
    except KeyboardInterrupt:
        restore()
        if sidecar is not None:
            sidecar.save(sidecar_payload(acc))
        io.write("\nAborted (Ctrl-C). Resume with: bash install.sh --resume\n")
        return None
    except WizardAbort as exc:
        restore()
        if exc.write_sidecar and sidecar is not None:
            sidecar.save(sidecar_payload(acc))
        io.write("\nAborted.\n")
        return None


def main(argv: Optional[List[str]] = None) -> int:
    """Top-level dispatch. Real behavior is filled in by later tasks.

    T1 ships the skeleton: parse args and route to the correct mode. The wizard
    (T5), execute phase (T6), headless (T9) and uninstall (T11) replace the
    stub bodies below.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.uninstall:
        # T11 fills this in.
        print("awr_install %s: uninstall mode (skeleton)" % __version__)
        return 0

    sidecar = sidecar_state.Sidecar()
    if args.resume:
        state = sidecar.load()
        if state is None:
            print("No resumable install found (or it expired >24h); starting fresh.")
        else:
            print("Resuming %r (pending stages: %s)."
                  % (state.get("profile_name"), sidecar_state.pending_stages(state)))
            reprompt = sidecar_state.channels_needing_reprompt(state)
            if reprompt:
                print("Channel secrets are not stored; you'll re-enter: %s" % ", ".join(reprompt))

    # Interactive + headless both collect answers via run_tui; the execute phase
    # consumes them in-process. The sidecar captures a non-secret snapshot on abort.
    try:
        answers = run_tui(args, sidecar=sidecar)
    except HeadlessError as exc:
        print("headless error: %s" % exc)
        return 2
    if answers is None:
        return 1

    profiles_root = Path("~/.hermes/profiles").expanduser()
    profile_root = profiles_root / answers.profile_name
    inspection = profile_detect.inspect_profile(profile_root)
    action = profile_detect.collision_strategy(inspection, force=args.force)
    if action == profile_detect.ABORT:
        print("Refusing to install %r: %s" % (answers.profile_name, inspection.reason))
        return 2
    skip_install = action == profile_detect.RECONFIGURE

    result = orch.execute(
        answers,
        dry_run=args.dry_run,
        verbose=args.verbose,
        stage_timeout=args.stage_timeout,
        skip_install=skip_install,
    )

    if result.exit_code != 0 and result.failed_stage is not None and not skip_install:
        # Hard failure: offer rollback (refused unconditionally if user data).
        do_rollback = True
        if not args.headless:
            choice = input(
                "Install failed at stage %d. [r]ollback / [k]eep partial? [r] "
                % result.failed_stage
            ).strip().lower()
            do_rollback = choice == "" or choice.startswith("r")
        if do_rollback:
            rb = rollback_mod.rollback(
                profile_root, stages_completed=result.completed_stages, logger=print
            )
            print(rb.reason)

    if result.exit_code == 0 and not args.dry_run:
        sidecar.cleanup()
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
