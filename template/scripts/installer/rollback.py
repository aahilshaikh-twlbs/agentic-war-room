"""Rollback of a failed install, guarded by a HARD INVARIANT (A9/C10).

Before removing anything, :func:`rollback` RE-INSPECTS the profile via
``profile_detect.inspect_profile`` and refuses to ``rmtree`` when:

  * the profile carries user data (``has_user_data``) -- UNCONDITIONAL, or
  * the path is not a Hermes-managed profile (a foreign directory we did not
    create -- the confirm-overwrite case).

Removal happens only for a clean Hermes profile with no user data (a partial
install we created). The re-inspect is deliberate: state may have changed since
the install started, so we never trust a cached verdict.

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import profile_detect


@dataclass
class RollbackResult:
    removed: bool
    refused: bool
    reason: str


def rollback(
    profile_path,
    *,
    stages_completed: List[int],
    logger: Optional[Callable[[str], None]] = None,
    rmtree: Callable[[str], None] = shutil.rmtree,
) -> RollbackResult:
    """Attempt to roll back ``profile_path``. Returns a decision record.

    Never raises on a failed removal; reports it in the result instead.
    """
    def _log(msg: str) -> None:
        if logger is not None:
            logger(msg)

    insp = profile_detect.inspect_profile(profile_path)

    if not insp.exists:
        reason = (
            "stage 1 incomplete; no profile to roll back"
            if 1 not in (stages_completed or [])
            else "profile path does not exist"
        )
        _log("rollback noop: %s (%s)" % (profile_path, reason))
        return RollbackResult(removed=False, refused=False, reason=reason)

    # HARD INVARIANT (A9): never rmtree a path with user data.
    if insp.has_user_data:
        reason = "refused: user data present"
        _log("rollback REFUSED: %s (%s)" % (profile_path, reason))
        return RollbackResult(removed=False, refused=True, reason=reason)

    # Never delete a directory we did not create (non-Hermes / confirm-overwrite).
    if not insp.is_hermes_managed:
        reason = "refused: not a Hermes-managed profile (won't delete a foreign directory)"
        _log("rollback REFUSED: %s (%s)" % (profile_path, reason))
        return RollbackResult(removed=False, refused=True, reason=reason)

    try:
        rmtree(str(insp.path))
    except OSError as exc:
        reason = "rmtree failed: %s" % exc
        _log("rollback FAILED: %s (%s)" % (profile_path, reason))
        return RollbackResult(removed=False, refused=False, reason=reason)

    reason = "removed clean partial install"
    _log("rollback removed: %s (%s)" % (profile_path, reason))
    return RollbackResult(removed=True, refused=False, reason=reason)
