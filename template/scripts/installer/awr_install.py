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
import sys
from typing import List, Optional

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


def main(argv: Optional[List[str]] = None) -> int:
    """Top-level dispatch. Real behavior is filled in by later tasks.

    T1 ships the skeleton: parse args and route to the correct mode. The wizard
    (T5), execute phase (T6), headless (T9) and uninstall (T11) replace the
    stub bodies below.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.uninstall:
        mode = "uninstall"
    elif args.resume:
        mode = "resume"
    elif args.headless:
        mode = "headless"
    else:
        mode = "interactive"

    # Skeleton dispatch -- replaced incrementally by T5/T6/T9/T11.
    print("awr_install %s: %s mode (skeleton)" % (__version__, mode))
    return 0


if __name__ == "__main__":
    sys.exit(main())
