"""warroom CLI. Stdlib only, Python >=3.9. Mirrors ccpkg/cli.py arg shape."""
import argparse
from pathlib import Path

from . import setup
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
    return parser


def _profile_root():
    # Package is at <profile>/warroom_setup/ ; profile root is one up.
    return Path(__file__).resolve().parents[1]


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
    parser.print_help()
    return 2
