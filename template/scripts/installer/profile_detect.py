"""Existing-profile detection + collision strategy (A6/F2/§8).

Before installing, the wizard classifies the target ``~/.hermes/profiles/<name>``
so it can pick the right collision behavior. The Hermes-managed signal is the
presence of ``config.yaml`` (NOT ``distribution.yaml`` -- legacy Hermes profiles
predate that file). An AWR-template profile additionally carries a
``warroom_setup/__init__.py``. User data lives under ``local/``.

``inspect_profile`` returns pure data + a recommended ``strategy``;
``collision_strategy`` resolves that to the concrete action the orchestrator
takes, applying ``--force`` and the reconfigure warroom-package guard (F18).

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Recommended strategies emitted by inspect_profile.
PROCEED = "proceed"               # safe to install fresh
RECONFIGURE = "reconfigure"       # AWR profile w/ user data: skip Stage 1, re-run in-process
ABORT = "abort"                   # foreign/corrupt profile: refuse
CONFIRM_OVERWRITE = "confirm-overwrite"  # non-Hermes dir in the way: confirm before clobber
# Resolved action collision_strategy may additionally return.
OVERWRITE = "overwrite"           # confirmed/forced clobber of a non-Hermes dir


@dataclass
class ProfileInspection:
    path: Path
    exists: bool
    is_hermes_managed: bool
    has_warroom_setup: bool
    has_user_data: bool
    strategy: str
    reason: str = ""


def _dir_nonempty(p: Path) -> bool:
    try:
        return p.is_dir() and any(p.iterdir())
    except OSError:
        return False


def _detect_user_data(path: Path) -> bool:
    local = path / "local"
    return (
        (local / "agent.json").exists()
        or (local / ".warroom-setup.json").exists()
        or _dir_nonempty(local / "persona")
    )


def inspect_profile(path) -> ProfileInspection:
    """Classify a candidate profile path per §8."""
    path = Path(path)
    if not path.exists():
        return ProfileInspection(
            path=path, exists=False, is_hermes_managed=False,
            has_warroom_setup=False, has_user_data=False,
            strategy=PROCEED, reason="path does not exist",
        )

    is_hermes = (path / "config.yaml").exists()
    has_warroom = (path / "warroom_setup" / "__init__.py").exists()
    has_user_data = _detect_user_data(path)

    if is_hermes and has_warroom:
        if has_user_data:
            strategy, reason = RECONFIGURE, "AWR-template profile with user data"
        else:
            strategy, reason = PROCEED, "AWR-template profile, no user data"
    elif is_hermes and not has_warroom:
        strategy, reason = ABORT, "Hermes profile from a different distribution"
    else:  # exists but not Hermes-managed (no config.yaml)
        strategy, reason = CONFIRM_OVERWRITE, "non-Hermes directory at target path"

    return ProfileInspection(
        path=path, exists=True, is_hermes_managed=is_hermes,
        has_warroom_setup=has_warroom, has_user_data=has_user_data,
        strategy=strategy, reason=reason,
    )


def collision_strategy(inspection: ProfileInspection, *, force: bool = False) -> str:
    """Resolve the recommended strategy into the action the orchestrator takes.

    * ``proceed`` / ``abort`` pass through.
    * ``reconfigure`` is downgraded to ``abort`` if the warroom_setup package is
      missing (F18) -- we cannot re-run in-process setup against a profile that
      lacks the package.
    * ``confirm-overwrite`` resolves to ``overwrite`` only when ``force`` is set;
      otherwise it defaults to ``abort`` (the picker's default cursor, §7).
    """
    strat = inspection.strategy
    if strat == RECONFIGURE and not inspection.has_warroom_setup:
        return ABORT
    if strat == CONFIRM_OVERWRITE:
        return OVERWRITE if force else ABORT
    return strat


def collision_options(inspection: ProfileInspection):
    """Three single-toggle picker entries with first-match-wins precedence (C23).

    Returns ``[(key, label, recommended_bool), ...]`` ordered so the default
    cursor (first entry) is the safe choice for the detected situation.
    """
    if inspection.strategy == RECONFIGURE:
        return [
            (RECONFIGURE, "Reconfigure (keep data, re-run setup)", True),
            (ABORT, "Abort (keep existing untouched)", False),
            (OVERWRITE, "Overwrite (DESTROYS user data)", False),
        ]
    if inspection.strategy == CONFIRM_OVERWRITE:
        return [
            (ABORT, "Abort (leave directory untouched)", True),
            (OVERWRITE, "Overwrite (replace this directory)", False),
        ]
    # PROCEED / ABORT have no meaningful multi-choice.
    return [(inspection.strategy, inspection.reason, True)]
