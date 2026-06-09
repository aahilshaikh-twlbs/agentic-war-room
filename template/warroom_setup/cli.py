"""warroom CLI. Stdlib only, Python >=3.9. Mirrors ccpkg/cli.py arg shape."""
import argparse
import json
from pathlib import Path

from . import assimilate as assimilate_mod
from . import enroll, setup
from .__init__ import __version__


def _build_parser():
    parser = argparse.ArgumentParser(prog="warroom")
    parser.add_argument("--version", action="version", version="warroom " + __version__)
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("setup", help="personalize this installed war-room profile")
    p.add_argument("--yes", "--non-interactive", dest="yes", action="store_true",
                   help="headless: replay saved answers / defaults, no prompts")
    p.add_argument("--reconfigure", dest="reconfigure", action="store_true",
                   help="re-run the interactive wizard even if answers exist")
    p.add_argument("--sync", dest="sync", action="store_true",
                   help="only recompile SOUL.md + Claude head from local/persona/")

    e = sub.add_parser("enroll", help="wire this profile onto a cross-agent mailbox board")
    e.add_argument("--board", default=None, help="board name (updates war_room + mailbox blocks)")
    e.add_argument("--label", default=None, help="board label (defaults to handle)")
    e.add_argument("--status", action="store_true", help="print enrollment JSON + daemon reachability")
    e.add_argument("--reconfigure", action="store_true", help="force re-write even if already enrolled")
    e.add_argument("--dry-run", dest="dry_run", action="store_true", help="resolve + report; write nothing")
    e.add_argument("--profile-root", dest="profile_root", default=None, help="override profile root")

    a = sub.add_parser("assimilate",
                       help="wire an existing (foreign) Hermes profile into a war-room board")
    a.add_argument("profile_root", help="path to the Hermes profile to assimilate")
    a.add_argument("--board", default="default", help="board name (default: default)")
    a.add_argument("--label", default=None,
                   help="board label (default: handle from local/agent.json, else profile dir name)")
    a.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="resolve + report; write nothing")
    a.add_argument("--no-walkthrough", dest="no_walkthrough", action="store_true",
                   help="skip Discord/Slack walkthroughs even if creds are missing")
    a.add_argument("--reconfigure", action="store_true",
                   help="force rewrite if already assimilated")
    a.add_argument("--enforce", action="store_true",
                   help="opt into confidence-gate enforcement (default off; gentler on existing profiles)")
    a.add_argument("--yes", action="store_true",
                   help="headless: suppress the proceed-confirm (needs --no-walkthrough or pre-set creds)")
    return parser


def _profile_root():
    # Package is at <profile>/warroom_setup/ ; profile root is one up.
    return Path(__file__).resolve().parents[1]


def cmd_enroll(args):
    # type: (argparse.Namespace) -> int
    """Exit-code contract (locked):
      0 — ok + daemon reachable, or a non-status command that succeeded
      1 — status=cli-not-found
      2 — status=ok but daemon unreachable (only via --status)
      3 — no state file (enroll never run on this profile)
    """
    profile_root = Path(args.profile_root) if args.profile_root else _profile_root()

    if args.status:
        try:
            st = enroll.enroll_status(profile_root)
        except FileNotFoundError:
            print(json.dumps({"status": "no-state", "daemon_reachable": False}))
            return 3
        print(json.dumps(st, indent=2, sort_keys=True))
        if st.get("status") == "cli-not-found":
            return 1
        if st.get("status") == "ok" and not st.get("daemon_reachable"):
            return 2
        return 0

    # bootstrap path (write/reconfigure)
    state_file = profile_root / "local" / "warroom-enroll.json"
    if state_file.exists() and not args.reconfigure and not args.dry_run:
        print("already enrolled (use --reconfigure to force re-write)")
        return 0

    board = args.board or "default"
    label = args.label or ""
    # --board override keeps war_room.board in sync (decision #13).
    if args.board and not args.dry_run:
        setup.patch_war_room_block(profile_root, board)
    st = enroll.bootstrap(profile_root, board, label, dry_run=args.dry_run)
    print(json.dumps(st.to_dict(), indent=2, sort_keys=True))
    if st.status == "cli-not-found":
        return 1
    return 0


def cmd_assimilate(args):
    # type: (argparse.Namespace) -> int
    """Dispatch `warroom assimilate`. Exit codes per assimilate.EXIT_* (0 ok /
    1 mailbox CLI missing / 2 already assimilated / 3 bad profile / 4 aborted)."""
    return assimilate_mod.assimilate(
        Path(args.profile_root),
        board=args.board,
        label=args.label,
        dry_run=args.dry_run,
        reconfigure=args.reconfigure,
        no_walkthrough=args.no_walkthrough,
        enforce=args.enforce,
        yes=args.yes,
    )


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 2
    if args.cmd == "setup":
        try:
            return setup.run_setup(_profile_root(), yes=args.yes,
                                   reconfigure=args.reconfigure, sync_only=args.sync)
        except KeyboardInterrupt:
            print("\nsetup cancelled")
            return 130
    if args.cmd == "enroll":
        return cmd_enroll(args)
    if args.cmd == "assimilate":
        return cmd_assimilate(args)
    parser.print_help()
    return 2
