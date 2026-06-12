import argparse
import os
import sys
from typing import List, Optional

from . import client


def _resolve_session(args) -> Optional[str]:
    if getattr(args, "session", None):
        return args.session
    env = os.environ.get("MAILBOX_SESSION_ID")
    if env:
        return env
    return None


def _abspath(p: str) -> str:
    return os.path.abspath(p)


_LANE_PREFIX = "lane://"


def _lane_name(arg: str) -> str:
    """Return the bare lane name for an engine lane op.

    A ``lane://`` URI is preserved verbatim -- it is NEVER routed through
    ``os.path.abspath`` (which would mangle ``lane://x`` into ``<cwd>/lane:/x``
    and silently fail the engine's lane conflict scan). The ``lane://`` prefix
    is stripped here because the engine re-adds it canonically.
    """
    if arg.startswith(_LANE_PREFIX):
        return arg[len(_LANE_PREFIX):]
    return arg


# Topology verbs run without a session id (operator commands, not session
# ops). fleet (Phase 2) resolves a session's board only when one is present.
_SESSION_OPTIONAL_CMDS = {"create-board", "set-parent", "set-delivery",
                          "tree", "fleet"}

# New-verb error contract: an {"error": ...} data dict exits 1 with the error
# on stderr. Existing v1 verbs keep their print-the-dict behavior unchanged.
_FEDERATION_CMDS = {"create-board", "set-parent", "set-delivery", "tree",
                    "fleet", "escalate", "broadcast"}


def _add_fed_flags(sp):
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--federated", dest="federated", action="store_true",
                   default=True,
                   help="federated view across the board tree (default)")
    g.add_argument("--local", dest="federated", action="store_false",
                   help="restrict to own boards (no federation)")


def _print_inbox(messages: list, as_json: bool = False) -> None:
    if as_json:
        import json
        print(json.dumps(messages))
        return
    if not messages:
        print("(no messages)")
        return
    for m in messages:
        direction = m.get("direction")
        origin = ""
        if direction == "up":
            origin = " (^ escalated from %s)" % m.get("origin_board", "?")
        elif direction == "down":
            origin = " (v broadcast from %s)" % m.get("origin_board", "?")
        print("[%s] from %s%s: %s" % (
            m.get("kind", "note"),
            m.get("from_label", "?"),
            origin,
            m.get("body", ""),
        ))


def _print_claims(claims: list) -> None:
    if not claims:
        print("(no claims)")
        return
    for c in claims:
        print("%s  %-8s  %-7s  %s%s" % (
            c.get("id", "?"),
            c.get("holder_status", "?"),
            c.get("kind", "?"),
            ",".join(c.get("paths", [])),
            ("  # " + c["note"]) if c.get("note") else "",
        ))


def _print_lanes(lanes: list) -> None:
    if not lanes:
        print("(no lanes)")
        return
    for l in lanes:
        print("%-20s  %-5s  %-20s  %s%s" % (
            l.get("lane", "?"),
            "live" if l.get("live") else "stale",
            l.get("label", "?"),
            l.get("claim_id", "?"),
            ("  # " + l["note"]) if l.get("note") else "",
        ))


def _print_ps(rows: list) -> None:
    if not rows:
        print("(nobody here)")
        return
    for r in rows:
        print("%-20s  %-7s  %ss ago  %s" % (
            r.get("label", "?"),
            r.get("status", "?"),
            int(r.get("last_seen_seconds", 0)),
            r.get("cwd", ""),
        ))


def _print_tree(data: dict) -> None:
    roots = data.get("roots", []) if isinstance(data, dict) else []
    if not roots:
        print("(no boards)")
        return

    def _walk(node, indent):
        line = "%s%s" % (indent, node.get("id", "?"))
        name = node.get("name")
        if name:
            line += "  (%s)" % name
        tags = []
        members = node.get("members")
        if members is not None:
            tags.append("%d member%s" % (members, "" if members == 1 else "s"))
        claims = node.get("claims")
        if claims:
            tags.append("%d claim%s" % (claims, "" if claims == 1 else "s"))
        if node.get("delivery") == "push":
            tags.append("push")
        if node.get("orphan"):
            tags.append("orphan: parent missing")
        if tags:
            line += "  [%s]" % ", ".join(tags)
        print(line)
        for child in node.get("children", []):
            _walk(child, indent + "    ")

    for root in roots:
        _walk(root, "")


def _print_fleet(data: dict) -> None:
    rows = data.get("rows", []) if isinstance(data, dict) else []
    if not rows:
        print("(nobody in subtree)")
        return
    for r in rows:
        via = r.get("via_board", "?")
        via_name = r.get("via_name")
        if via_name:
            via += "  (%s)" % via_name
        print("%-20s  %-7s  %ss ago  %s" % (
            r.get("label", "?"),
            r.get("status", "?"),
            int(r.get("last_seen_seconds", 0)),
            via,
        ))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mailbox")
    p.add_argument("--session", default=None)
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("join")
    sp.add_argument("--board", default=None)
    sp.add_argument("--label", default=None)

    sp = sub.add_parser("claim")
    sp.add_argument("globs", nargs="+")
    sp.add_argument("--note", default=None)

    sp = sub.add_parser("release")
    sp.add_argument("selector")
    sp.add_argument("--force", action="store_true")

    # Lane subcommands: a lane argument is preserved verbatim (no _abspath).
    sp = sub.add_parser("claim-lane")
    sp.add_argument("lane")
    sp.add_argument("--note", default=None)

    sp = sub.add_parser("release-lane")
    sp.add_argument("lane")

    sub.add_parser("list-lanes")

    sp = sub.add_parser("seize")
    sp.add_argument("path")

    sp = sub.add_parser("request-release")
    sp.add_argument("path")

    sp = sub.add_parser("send")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")
    sp.add_argument("--scope", default="local",
                    choices=["local", "escalate", "broadcast"])

    # Federation verbs (multi-board federation spec, 2026-06-09).
    sp = sub.add_parser("escalate")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")

    sp = sub.add_parser("broadcast")
    sp.add_argument("body")
    sp.add_argument("--to", default="*")
    sp.add_argument("--kind", default="note")

    sp = sub.add_parser("create-board")
    sp.add_argument("name")
    sp.add_argument("--parent", default=None)

    sp = sub.add_parser("set-parent")
    sp.add_argument("board")
    sp.add_argument("parent", nargs="?", default=None)
    sp.add_argument("--detach", action="store_true")

    sp = sub.add_parser("set-delivery")
    sp.add_argument("board")
    sp.add_argument("mode", choices=["pull", "push"])

    sp = sub.add_parser("tree")
    sp.add_argument("board", nargs="?", default=None)

    sp = sub.add_parser("fleet")
    sp.add_argument("board", nargs="?", default=None)

    sp = sub.add_parser("inbox")
    _add_fed_flags(sp)
    sp.add_argument("--json", dest="as_json", action="store_true",
                    help="emit inbox messages as a JSON array (machine-readable)")

    sp = sub.add_parser("claims")
    sp.add_argument("--mine", action="store_true")
    sp.add_argument("--all", action="store_true")
    _add_fed_flags(sp)

    sp = sub.add_parser("ps")
    _add_fed_flags(sp)
    sub.add_parser("board")
    sub.add_parser("whoami")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "cmd", None):
        parser.print_help(sys.stderr)
        return 1

    cmd = args.cmd

    session_id = _resolve_session(args)
    if not session_id and cmd not in _SESSION_OPTIONAL_CMDS:
        print("no session id (run inside a Claude session)", file=sys.stderr)
        return 1

    if cmd == "join":
        op = "join"
        op_args = {
            "session_id": session_id,
            "label": args.label or session_id,
            "cwd": os.getcwd(),
            "board_name": args.board,
        }
    elif cmd == "claim":
        op = "claim"
        op_args = {
            "session_id": session_id,
            "globs": [_abspath(g) for g in args.globs],
            "note": args.note,
        }
    elif cmd == "release":
        op = "release"
        op_args = {
            "session_id": session_id,
            "selector": args.selector,
            "force": args.force,
        }
    elif cmd == "claim-lane":
        op = "claim_lane"
        op_args = {
            "session_id": session_id,
            "lane": _lane_name(args.lane),
            "note": args.note,
        }
    elif cmd == "release-lane":
        op = "release_lane"
        op_args = {
            "session_id": session_id,
            "lane": _lane_name(args.lane),
        }
    elif cmd == "list-lanes":
        op = "list_lanes"
        op_args = {"session_id": session_id}
    elif cmd == "seize":
        op = "seize"
        op_args = {
            "session_id": session_id,
            "abs_path": _abspath(args.path),
        }
    elif cmd == "request-release":
        op = "request_release"
        op_args = {
            "session_id": session_id,
            "abs_path": _abspath(args.path),
        }
    elif cmd == "send":
        op = "send"
        op_args = {
            "session_id": session_id,
            "to": args.to,
            "kind": args.kind,
            "body": args.body,
            "scope": args.scope,
        }
    elif cmd in ("escalate", "broadcast"):
        op = "send"
        op_args = {
            "session_id": session_id,
            "to": args.to,
            "kind": args.kind,
            "body": args.body,
            "scope": cmd,
        }
    elif cmd == "create-board":
        op = "create_board"
        op_args = {"name": args.name, "parent": args.parent}
    elif cmd == "set-parent":
        if not args.detach and args.parent is None:
            print("set-parent: pass a parent board or --detach",
                  file=sys.stderr)
            return 1
        op = "set_parent"
        op_args = {"board": args.board, "parent": args.parent,
                   "detach": args.detach}
    elif cmd == "set-delivery":
        op = "set_delivery"
        op_args = {"board": args.board, "mode": args.mode}
    elif cmd == "tree":
        op = "tree"
        op_args = {"board": args.board}
    elif cmd == "fleet":
        op = "fleet"
        op_args = {"session_id": session_id, "board": args.board}
    elif cmd == "inbox":
        op = "poll_inbox"
        op_args = {"session_id": session_id, "federated": args.federated}
    elif cmd == "claims":
        if args.all:
            scope = "all"
        elif args.mine:
            scope = "mine"
        else:
            scope = "board"
        op = "list_claims"
        op_args = {"session_id": session_id, "scope": scope,
                   "federated": args.federated}
    elif cmd == "ps":
        op = "ps"
        op_args = {"session_id": session_id, "federated": args.federated}
    elif cmd == "board":
        op = "board"
        op_args = {"session_id": session_id}
    elif cmd == "whoami":
        op = "whoami"
        op_args = {"session_id": session_id}
    else:
        print("unknown command: %s" % cmd, file=sys.stderr)
        return 1

    resp = client.request(op, op_args)

    if not resp.get("ok"):
        print(resp.get("error", "error"), file=sys.stderr)
        return 1

    data = resp.get("data")
    if (cmd in _FEDERATION_CMDS and isinstance(data, dict)
            and data.get("error")):
        print(data["error"], file=sys.stderr)
        return 1
    if cmd == "inbox":
        _print_inbox(data or [], as_json=getattr(args, "as_json", False))
    elif cmd == "tree":
        _print_tree(data or {})
    elif cmd == "fleet":
        _print_fleet(data or {})
    elif cmd == "claims":
        _print_claims(data or [])
    elif cmd == "list-lanes":
        _print_lanes(data or [])
    elif cmd == "ps":
        _print_ps(data or [])
    else:
        print(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
