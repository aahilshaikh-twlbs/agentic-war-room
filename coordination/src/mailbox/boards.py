import hashlib
import os
import re
import subprocess
from typing import List, Optional, Tuple


def derive_repo_board(cwd: str) -> Tuple[str, str]:
    """Derive the auto repo board id and its origin path for a working dir.

    Tries `git -C <cwd> rev-parse --show-toplevel` (the working-tree root, NOT
    --git-common-dir, so worktrees are distinct boards). On success returns
    ("repo-" + sha1(toplevel)[:12], toplevel). On any failure (not a repo,
    git missing, timeout, empty output) falls back to
    ("cwd-" + sha1(cwd)[:12], cwd).
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )
        if proc.returncode == 0:
            toplevel = proc.stdout.decode("utf-8", "replace").strip()
            if toplevel:
                board_id = "repo-" + hashlib.sha1(toplevel.encode()).hexdigest()[:12]
                return (board_id, toplevel)
    except (OSError, subprocess.SubprocessError):
        pass

    root = os.path.realpath(cwd)
    board_id = "cwd-" + hashlib.sha1(root.encode()).hexdigest()[:12]
    return (board_id, root)


def board_id_for_name(name: str) -> str:
    """Map a human board name to a stable id: "named-" + slug.

    Slug: lowercase, every run of non-[a-z0-9] chars -> "-", strip leading/
    trailing "-", capped at 40 chars.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return "named-" + slug


# --- Federation topology (multi-board federation spec, 2026-06-09) ----------
#
# Pure tree walks over the engine's in-RAM board-meta dict
# ({board_id: meta_dict}). A meta's "parent" key (absent/None = root) is the
# only topology input. Every walk is cycle-safe via a visited set: set_parent
# validation prevents persisting cycles, but a hand-edited meta.json must
# never hang the daemon.

MAX_FEDERATION_DEPTH = 8   # max allowed depth value (root = 0): 9-level chain


def parent_of(boards: dict, board_id: str) -> Optional[str]:
    """The parent board id recorded in board_id's meta, or None (root)."""
    meta = boards.get(board_id) or {}
    return meta.get("parent") or None


def _children_index(boards: dict) -> dict:
    """{parent_id: [child ids, sorted]} over every meta with a parent link."""
    idx = {}
    for bid in boards:
        p = parent_of(boards, bid)
        if p is not None:
            idx.setdefault(p, []).append(bid)
    for p in idx:
        idx[p].sort()
    return idx


def ancestors(boards: dict, board_id: str) -> List[str]:
    """[parent, grandparent, ..., root]. A parent id with no meta (orphan
    link) ends the walk — the missing ancestor just drops out (spec: degrade
    gracefully). Cycle-safe."""
    out = []
    seen = {board_id}
    cur = parent_of(boards, board_id)
    while cur is not None and cur in boards and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = parent_of(boards, cur)
    return out


def descendants(boards: dict, board_id: str) -> List[str]:
    """All transitive children, breadth-first, children sorted by id."""
    idx = _children_index(boards)
    out = []
    seen = {board_id}
    frontier = list(idx.get(board_id, []))
    while frontier:
        bid = frontier.pop(0)
        if bid in seen:
            continue
        seen.add(bid)
        out.append(bid)
        frontier.extend(idx.get(bid, []))
    return out


def subtree(boards: dict, board_id: str) -> List[str]:
    """[board_id] + descendants(board_id)."""
    return [board_id] + descendants(boards, board_id)


def is_ancestor(boards: dict, a: str, b: str) -> bool:
    """True iff a is a transitive ancestor of b."""
    return a in ancestors(boards, b)


def depth(boards: dict, board_id: str) -> int:
    """Edges from board_id up to its root (root = 0)."""
    return len(ancestors(boards, board_id))


def height(boards: dict, board_id: str) -> int:
    """Longest downward path (edges) from board_id; 0 for a leaf."""
    idx = _children_index(boards)
    best = 0
    seen = {board_id}
    stack = [(board_id, 0)]
    while stack:
        bid, d = stack.pop()
        for cid in idx.get(bid, []):
            if cid in seen:
                continue
            seen.add(cid)
            if d + 1 > best:
                best = d + 1
            stack.append((cid, d + 1))
    return best


def validate_parent(boards: dict, board_id: str, parent_id: str) -> Optional[str]:
    """Validate linking board_id under parent_id. Returns an error string, or
    None when the link is legal. Rejects (a) self-parenting, (b) a parent that
    is a descendant of the board (cycle), (c) a parent with no meta, and
    (d) a resulting tree deeper than MAX_FEDERATION_DEPTH."""
    if parent_id == board_id:
        return "self-parent: a board cannot be its own parent"
    if parent_id not in boards:
        return "no-such-board: " + str(parent_id)
    if parent_id in descendants(boards, board_id):
        return "cycle: %s is a descendant of %s" % (parent_id, board_id)
    if depth(boards, parent_id) + 1 + height(boards, board_id) > MAX_FEDERATION_DEPTH:
        return "too-deep: federation depth would exceed %d" % MAX_FEDERATION_DEPTH
    return None
