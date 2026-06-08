"""Execute phase: in-process orchestration (A1, the load-bearing architecture).

After Stage 1 (`hermes profile install`) lands the template at
``~/.hermes/profiles/<name>/``, the installer puts that profile on ``sys.path``
and imports the profile's OWN ``warroom_setup.setup`` / ``agent_model`` /
``enroll``, then calls them directly in-process. There is NO subprocess to
``warroom setup`` and NO ``installer-answers.json`` bridge file (C1/C2/K2/K10).

Five stages:
  1. hermes profile install            (subprocess)
  2. write .env + identity             (in-process: setup.write_env, agent_model.save)
  3. patch war_room + mailbox blocks   (in-process: setup.patch_*_block)
  4. hermes -p <name> plugins enable   (subprocess; NO -y; failure is advisory)
  5. cross-agent enroll bootstrap      (in-process: enroll.bootstrap)

Risk #1 mitigation: after Stage 1 we verify ``warroom_setup/__init__.py`` exists
and is importable; an ImportError is treated as a Stage 1 failure (-> rollback).

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Sequence, TextIO

import subprocess_runner

# Stage labels (§3 step 13).
STAGE_LABELS = {
    1: "hermes profile install",
    2: "write .env and identity (in-process)",
    3: "patch war_room + mailbox blocks",
    4: "plugins enable warroom-gate",
    5: "cross-agent enroll bootstrap",
}

_LOG_CAP_BYTES = 1_000_000  # K14: 1MB cap


@dataclass
class ExecuteResult:
    exit_code: int
    completed_stages: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failed_stage: Optional[int] = None
    enroll_status: Optional[str] = None
    total_time_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class _InstallLog:
    """Append-only install log, truncated at start, capped at 1MB (K14)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "w", encoding="utf-8")  # truncate
        self.written = 0
        self.capped = False

    def write(self, line: str) -> None:
        if self.capped:
            return
        data = line if line.endswith("\n") else line + "\n"
        if self.written + len(data) > _LOG_CAP_BYTES:
            self.fh.write("... [install.log capped at 1MB]\n")
            self.fh.flush()
            self.capped = True
            return
        self.fh.write(data)
        self.written += len(data)
        self.fh.flush()

    def close(self) -> None:
        try:
            self.fh.close()
        except Exception:  # pragma: no cover - defensive
            pass


# --------------------------------------------------------------------------- #
# Profile import (Risk #1)
# --------------------------------------------------------------------------- #
def verify_profile_importable(profile_root: Path) -> None:
    """Raise ImportError if the post-Stage-1 profile lacks the warroom package."""
    init = Path(profile_root) / "warroom_setup" / "__init__.py"
    if not init.exists():
        raise ImportError("warroom_setup package missing under %s" % profile_root)


def import_profile_modules(profile_root: Path) -> SimpleNamespace:
    """Insert the profile on sys.path and import its setup/agent_model/enroll."""
    verify_profile_importable(profile_root)
    p = str(Path(profile_root))
    if p not in sys.path:
        sys.path.insert(0, p)
    import warroom_setup.agent_model as agent_model
    import warroom_setup.enroll as enroll
    import warroom_setup.setup as setup
    return SimpleNamespace(setup=setup, agent_model=agent_model, enroll=enroll)


# --------------------------------------------------------------------------- #
# Default subprocess runners (wrap subprocess_runner)
# --------------------------------------------------------------------------- #
def _default_hermes_runner(cmd, *, timeout=300.0, tee=None):
    return subprocess_runner.run_capturing(cmd, timeout=timeout, tee=tee)


def _default_plugin_runner(cmd, *, timeout=30.0, tee=None):
    return subprocess_runner.run_capturing(cmd, timeout=timeout, tee=tee)


def hermes_install_cmd(answers) -> List[str]:
    return [
        "hermes", "profile", "install", answers.source,
        "--name", answers.profile_name, "--alias", "--force", "-y",
    ]


def plugin_enable_cmd(answers) -> List[str]:
    # A8/C3: profile-scoped, NO -y flag.
    return ["hermes", "-p", answers.profile_name, "plugins", "enable", "warroom-gate"]


def _env_values_from_answers(answers) -> dict:
    """Secret/.env values from collected answers. Keys mirror .env.template."""
    env: dict = {}
    if answers.anthropic_key:
        env["ANTHROPIC_API_KEY"] = answers.anthropic_key
    if "discord" in answers.channels and answers.discord_creds is not None:
        dc = answers.discord_creds
        if dc.bot_token:
            env["DISCORD_BOT_TOKEN"] = dc.bot_token
        if dc.channel_id:
            env["DISCORD_HOME_CHANNEL"] = dc.channel_id
    if answers.discord_allowed_users:
        env["DISCORD_ALLOWED_USERS"] = ",".join(answers.discord_allowed_users)
    if "slack" in answers.channels and answers.slack_creds is not None:
        sc = answers.slack_creds
        if sc.bot_token:
            env["SLACK_BOT_TOKEN"] = sc.bot_token
        if sc.app_token:
            env["SLACK_APP_TOKEN"] = sc.app_token
        if sc.channel_id:
            env["SLACK_HOME_CHANNEL"] = sc.channel_id
    return env


# --------------------------------------------------------------------------- #
# Execute
# --------------------------------------------------------------------------- #
def execute(
    answers,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    stage_timeout: float = 300.0,
    skip_install: bool = False,
    profiles_root: Optional[Path] = None,
    hermes_runner=None,
    plugin_runner=None,
    importer=None,
    out: Optional[TextIO] = None,
) -> ExecuteResult:
    """Run the five-stage in-process orchestration.

    ``skip_install`` skips Stage 1 (reconfigure path -- §6). Subprocess runners
    and the profile importer are injectable for testing. Returns an
    :class:`ExecuteResult`; ``exit_code`` is the process exit code.
    """
    out = out if out is not None else sys.stdout
    hermes_runner = hermes_runner or _default_hermes_runner
    plugin_runner = plugin_runner or _default_plugin_runner
    importer = importer or import_profile_modules
    tee = sys.stderr if verbose else None  # K16

    profiles_root = Path(profiles_root) if profiles_root else Path("~/.hermes/profiles").expanduser()
    profile_root = profiles_root / answers.profile_name

    result = ExecuteResult(exit_code=0)
    started = time.monotonic()

    if dry_run:
        out.write("[dry-run] would install profile %r from %s\n"
                  % (answers.profile_name, answers.source))
        out.write("[dry-run] would run: %s\n" % " ".join(hermes_install_cmd(answers)))
        out.write("[dry-run] would write .env keys: %s\n"
                  % ", ".join(sorted(_env_values_from_answers(answers))))
        out.write("[dry-run] would run: %s\n" % " ".join(plugin_enable_cmd(answers)))
        out.write("[dry-run] would enroll on board %r label %r\n" % (answers.board, answers.label))
        result.total_time_s = time.monotonic() - started
        out.write("Total time: %.1fs\n" % result.total_time_s)
        return result

    log = _InstallLog(profile_root.parent.joinpath(answers.profile_name, "local", "install.log")
                      if not skip_install else profile_root / "local" / "install.log")

    def _stage_line(n: int, status: str, detail: str = "") -> None:
        msg = "[%d/5] %s ... %s%s" % (n, STAGE_LABELS[n], status, (" -- " + detail) if detail else "")
        out.write(msg + "\n")
        log.write(msg)

    try:
        # ---- Stage 1: hermes profile install -------------------------------
        if skip_install:
            _stage_line(1, "skip", "reconfigure: profile already installed")
            result.completed_stages.append(1)
        else:
            cmd = hermes_install_cmd(answers)
            log.write("$ " + " ".join(cmd))
            res = hermes_runner(cmd, timeout=stage_timeout, tee=tee)
            for ln in res.lines:
                log.write(ln)
            if not res.ok:
                err = subprocess_runner.tail_for_error_line(res.lines) or "non-zero exit"
                _stage_line(1, "FAIL", err)
                result.exit_code = 1
                result.failed_stage = 1
                return result
            _stage_line(1, "ok", "%.1fs" % res.duration_s)
            result.completed_stages.append(1)

        # Risk #1: the profile must be importable post-install.
        try:
            mods = importer(profile_root)
        except ImportError as exc:
            _stage_line(1, "FAIL", "profile not importable: %s" % exc)
            result.exit_code = 1
            result.failed_stage = 1
            return result

        # ---- Stage 2: .env + identity (in-process) -------------------------
        env_values = _env_values_from_answers(answers)
        if env_values:
            mods.setup.write_env(profile_root, env_values, ".env")  # C14: positional filename
        agent_json = profile_root / "local" / "agent.json"
        prior = mods.agent_model.load(agent_json)
        fingerprint = (
            prior.agent_fingerprint if prior
            else "%s-%s" % (answers.agent_name, uuid.uuid4().hex[:12])
        )
        ident = mods.agent_model.AgentIdentity(
            agent_name=answers.agent_name,
            handle=answers.handle,
            display_name=answers.display_name,
            model=answers.model,
            specialist_prefix=answers.agent_name,
            agent_fingerprint=fingerprint,
        )
        mods.agent_model.save(agent_json, ident)
        _stage_line(2, "ok", "%d env key(s), identity %s" % (len(env_values), answers.agent_name))
        result.completed_stages.append(2)

        # ---- Stage 3: war_room + mailbox blocks ----------------------------
        mods.setup.patch_war_room_block(
            profile_root, answers.board, min_confidence=answers.min_confidence
        )
        mods.setup.patch_mailbox_block(
            profile_root, board=answers.board, label=answers.label
        )
        _stage_line(3, "ok", "board %s" % answers.board)
        result.completed_stages.append(3)

        # ---- Stage 4: plugins enable (advisory failure) --------------------
        pcmd = plugin_enable_cmd(answers)
        log.write("$ " + " ".join(pcmd))
        pres = plugin_runner(pcmd, timeout=30.0, tee=tee)
        for ln in pres.lines:
            log.write(ln)
        if pres.ok:
            _stage_line(4, "ok")
        else:
            warn = "plugins enable failed (rc=%s); enable manually: %s" % (
                pres.returncode, " ".join(pcmd))
            _stage_line(4, "warn", warn)
            result.warnings.append(warn)  # F1/K4: advisory, does NOT abort
        result.completed_stages.append(4)

        # ---- Stage 5: enroll bootstrap (in-process) ------------------------
        state = mods.enroll.bootstrap(profile_root, answers.board, answers.label)
        result.enroll_status = state.status
        if state.status == "ok":
            _stage_line(5, "ok", "board %s label %s" % (state.board, state.label))
        else:
            warn = "enroll status=%s (routing written; activates when mailbox CLI lands)" % state.status
            _stage_line(5, "warn", warn)
            result.warnings.append(warn)
        result.completed_stages.append(5)

        result.total_time_s = time.monotonic() - started
        out.write("AWR ready. Total time: %.1fs\n" % result.total_time_s)
        log.write("Total time: %.1fs" % result.total_time_s)
        return result
    finally:
        log.close()
