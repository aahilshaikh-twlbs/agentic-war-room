"""T0 pre-flight capability validation for the AWR interactive installer.

Stdlib only, Python >=3.9. Verifies the host has every capability the installer
depends on BEFORE any profile mutation happens:

  1. Python >=3.9                       (sys.version_info)
  2. ``hermes`` on PATH                 (shutil.which)
  3. ``hermes --version`` >= 0.12       (robust regex parse; unparseable -> warn)
  4. ``hermes profile install --help``  (confirms --name/--alias/--force/-y)
  5. ``hermes plugins enable --help``   (confirms ``name`` positional; records
                                         ``plugins_enable_has_yes`` -- A8/F1)
  6. POSIX terminal                     (import termios, tty; hard-fail on Windows)
  7. ``~/.hermes/profiles/`` writable   (probe file)
  8. vendored ``_substrate`` imports    (subprocess under PYTHONPATH)

The ``git`` check is added ONLY when ``source`` is a URL (K23).

Results are pure data (:class:`PrecheckResult`); the TUI renders them and
:func:`assert_all_pass` raises :class:`PrecheckError` on any hard failure (a
``warn`` never blocks). :func:`write_preflight_doc` renders the captured
outcomes to ``template/docs/installer-preflight.md`` (DoD gate 10).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

MIN_PYTHON: Tuple[int, int] = (3, 9)
MIN_HERMES: Tuple[int, int] = (0, 12)

# Flags the installer relies on from `hermes profile install` (A8/§4).
_INSTALL_FLAGS = ("--name", "--alias", "--force")

# First dotted-number token in a version string. `hermes --version` prints
# e.g. "Hermes Agent v0.15.1 (2026.5.29)"; search picks "0.15.1" before the date.
_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")

# A `--source` value that needs cloning rather than a local path.
_URL_RE = re.compile(r"^(?:https?://|git@|ssh://|git://)|github\.com[:/]")

HermesRunner = Callable[[List[str]], Tuple[int, str]]


@dataclass
class PrecheckResult:
    """Outcome of one pre-flight check.

    ``status`` is ``"pass"`` | ``"warn"`` | ``"fail"``. A ``warn`` is advisory
    (e.g. an unparseable hermes version) and does NOT block the install.
    ``data`` carries machine-readable extras (e.g. ``plugins_enable_has_yes``).
    """

    name: str
    status: str
    detail: str = ""
    hint: str = ""
    data: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status != "fail"


class PrecheckError(RuntimeError):
    """Raised by :func:`assert_all_pass` when one or more checks hard-failed."""

    def __init__(self, failures: List[PrecheckResult]):
        self.failures = list(failures)
        msg = "; ".join(
            "%s: %s" % (r.name, r.hint or r.detail) for r in self.failures
        )
        super().__init__("pre-flight checks failed: " + msg)


# --------------------------------------------------------------------------- #
# Pure helpers (independently unit-tested)
# --------------------------------------------------------------------------- #
def _parse_hermes_version(text: str) -> Optional[Tuple[int, int, int]]:
    """Parse the first ``MAJOR.MINOR[.PATCH]`` token. ``None`` if unparseable."""
    m = _VERSION_RE.search(text or "")
    if not m:
        return None
    major, minor, patch = m.group(1), m.group(2), m.group(3)
    return (int(major), int(minor), int(patch) if patch else 0)


def _source_is_url(source: Optional[str]) -> bool:
    if not source:
        return False
    return bool(_URL_RE.search(str(source).strip()))


def _default_hermes_runner(args: List[str], *, timeout: float = 15.0) -> Tuple[int, str]:
    """Run ``hermes <args>``; merge stdout+stderr; never raise."""
    try:
        proc = subprocess.run(
            ["hermes", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            text=True,
        )
    except FileNotFoundError:
        return 127, "hermes: command not found"
    except subprocess.TimeoutExpired:
        return 124, "hermes: timed out after %ss" % timeout
    except OSError as exc:  # pragma: no cover - defensive
        return 1, "hermes: %s" % exc
    return proc.returncode, proc.stdout or ""


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def _check_python_version() -> PrecheckResult:
    ok = sys.version_info[:2] >= MIN_PYTHON
    return PrecheckResult(
        "python_version",
        "pass" if ok else "fail",
        detail="Python %d.%d.%d" % sys.version_info[:3],
        hint="" if ok else "Python >=%d.%d required." % MIN_PYTHON,
    )


def _check_hermes_on_path(path: Optional[str] = None) -> PrecheckResult:
    found = shutil.which("hermes", path=path)
    if found:
        return PrecheckResult("hermes_on_path", "pass", detail=found, data={"path": found})
    return PrecheckResult(
        "hermes_on_path",
        "fail",
        detail="hermes not found on PATH",
        hint="Install the hermes CLI and ensure it is on PATH.",
    )


def _check_hermes_version(runner: HermesRunner) -> PrecheckResult:
    _, out = runner(["--version"])
    ver = _parse_hermes_version(out)
    if ver is None:
        return PrecheckResult(
            "hermes_version",
            "warn",
            detail="could not parse version from: %r" % (out.strip()[:80]),
            hint="Proceeding; verify hermes >=%d.%d manually." % MIN_HERMES,
            data={"version": None},
        )
    status = "pass" if ver[:2] >= MIN_HERMES else "fail"
    return PrecheckResult(
        "hermes_version",
        status,
        detail="hermes %d.%d.%d" % ver,
        hint="" if status == "pass" else "hermes >=%d.%d required; run 'hermes update'." % MIN_HERMES,
        data={"version": list(ver)},
    )


def _check_profile_install_surface(runner: HermesRunner) -> PrecheckResult:
    _, out = runner(["profile", "install", "--help"])
    missing = [f for f in _INSTALL_FLAGS if f not in out]
    has_yes = ("-y" in out) or ("--yes" in out)
    if not has_yes:
        missing.append("-y/--yes")
    if missing:
        return PrecheckResult(
            "hermes_profile_install_surface",
            "fail",
            detail="missing flags: %s" % ", ".join(missing),
            hint="hermes 'profile install' lacks expected flags; upgrade hermes.",
        )
    return PrecheckResult(
        "hermes_profile_install_surface",
        "pass",
        detail="--name --alias --force -y present",
    )


def _check_plugins_enable_surface(runner: HermesRunner) -> PrecheckResult:
    _, out = runner(["plugins", "enable", "--help"])
    has_name = bool(re.search(r"\bname\b", out))
    has_yes = ("-y" in out) or ("--yes" in out)
    status = "pass" if has_name else "fail"
    return PrecheckResult(
        "hermes_plugins_enable_surface",
        status,
        detail="name positional %s; -y flag %s"
        % ("present" if has_name else "MISSING", "present" if has_yes else "absent"),
        hint="" if has_name else "hermes 'plugins enable' surface unexpected; upgrade hermes.",
        data={"plugins_enable_has_yes": has_yes},
    )


def _check_posix_terminal() -> PrecheckResult:
    try:
        import termios  # noqa: F401
        import tty  # noqa: F401
    except ImportError:
        return PrecheckResult(
            "posix_terminal",
            "fail",
            detail="termios/tty unavailable (non-POSIX platform)",
            hint="The interactive installer needs a POSIX terminal; use WSL or --headless.",
        )
    return PrecheckResult("posix_terminal", "pass", detail="termios/tty available")


def _check_profiles_dir_writable(profiles_dir: Optional[Path] = None) -> PrecheckResult:
    target = Path(profiles_dir) if profiles_dir is not None else Path("~/.hermes/profiles").expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(target), prefix=".awr-probe-"):
            pass
    except OSError as exc:
        return PrecheckResult(
            "profiles_dir_writable",
            "fail",
            detail="%s not writable: %s" % (target, exc),
            hint="Ensure %s exists and is writable." % target,
        )
    return PrecheckResult("profiles_dir_writable", "pass", detail=str(target))


def _check_substrate_imports(
    installer_dir: Optional[Path] = None, *, python: Optional[str] = None
) -> PrecheckResult:
    base = Path(installer_dir) if installer_dir is not None else Path(__file__).resolve().parent
    interp = python or sys.executable
    env = dict(os.environ)
    env["PYTHONPATH"] = str(base)
    try:
        proc = subprocess.run(
            [interp, "-c", "import _substrate.render, _substrate.prompts, _substrate.validators"],
            cwd=str(base),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=30,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - defensive
        return PrecheckResult(
            "substrate_imports",
            "fail",
            detail=str(exc),
            hint="Vendored _substrate package failed to import; run sync_substrate.sh.",
        )
    if proc.returncode == 0:
        return PrecheckResult(
            "substrate_imports", "pass", detail="_substrate imports cleanly under PYTHONPATH"
        )
    return PrecheckResult(
        "substrate_imports",
        "fail",
        detail=(proc.stdout or "").strip()[-200:],
        hint="Vendored _substrate package failed to import; run sync_substrate.sh.",
    )


def _check_git_for_url_source(source: str) -> PrecheckResult:
    git = shutil.which("git")
    if git:
        return PrecheckResult("git_for_url_source", "pass", detail=git, data={"path": git})
    return PrecheckResult(
        "git_for_url_source",
        "fail",
        detail="git not found",
        hint="Install git to clone a remote --source.",
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_prechecks(
    env: Optional[Dict[str, str]] = None,
    *,
    source: Optional[str] = None,
    installer_dir: Optional[Path] = None,
    hermes_runner: Optional[HermesRunner] = None,
    profiles_dir: Optional[Path] = None,
) -> List[PrecheckResult]:
    """Run every applicable pre-flight check and return the ordered results.

    The hermes-surface checks are skipped when hermes is not on PATH (so the
    user sees one clear "install hermes" failure rather than a cascade). The
    ``git`` check is appended only when ``source`` is a URL (K23).
    """
    runner = hermes_runner or _default_hermes_runner
    path = (env or {}).get("PATH") if env else None

    results: List[PrecheckResult] = [_check_python_version()]
    on_path = _check_hermes_on_path(path=path)
    results.append(on_path)
    if on_path.status == "pass":
        results.append(_check_hermes_version(runner))
        results.append(_check_profile_install_surface(runner))
        results.append(_check_plugins_enable_surface(runner))
    results.append(_check_posix_terminal())
    results.append(_check_profiles_dir_writable(profiles_dir))
    results.append(_check_substrate_imports(installer_dir))
    if _source_is_url(source):
        results.append(_check_git_for_url_source(str(source)))
    return results


def assert_all_pass(results: List[PrecheckResult]) -> None:
    """Raise :class:`PrecheckError` if any result hard-failed (warns are OK)."""
    failures = [r for r in results if r.status == "fail"]
    if failures:
        raise PrecheckError(failures)


# --------------------------------------------------------------------------- #
# Doc rendering (DoD gate 10)
# --------------------------------------------------------------------------- #
_STATUS_MARK = {"pass": "[ok]", "warn": "[warn]", "fail": "[fail]"}


def render_preflight_doc(results: List[PrecheckResult]) -> str:
    """Render captured outcomes as Markdown for ``installer-preflight.md``."""
    lines = [
        "# AWR installer pre-flight (T0)",
        "",
        "Generated by `precheck.run_prechecks`. Each row is one capability the",
        "interactive installer verifies before mutating any Hermes profile.",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for r in results:
        detail = (r.detail or "").replace("|", "\\|")
        lines.append("| `%s` | %s | %s |" % (r.name, _STATUS_MARK.get(r.status, r.status), detail))
    lines.append("")
    return "\n".join(lines)


def write_preflight_doc(results: List[PrecheckResult], path: Path) -> Path:
    """Write the rendered pre-flight doc to ``path`` (atomic-enough for a doc)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_preflight_doc(results), encoding="utf-8")
    return path
