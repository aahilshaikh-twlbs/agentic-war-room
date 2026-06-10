import hashlib
import os
import time
import uuid
from typing import Dict, Optional

from . import config
from . import matching
from . import store
from . import boards as boards_mod
from .models import Presence, Claim, Message


class MailboxEngine:
    def __init__(self, state_dir, now_fn=time.time):
        self.state_dir = state_dir
        self.now = now_fn
        self.boards = {}        # board_id -> meta dict
        self.presence = {}      # session_id -> Presence
        self.claims = {}        # claim_id -> Claim
        self.messages = {}      # msg_id -> Message
        self.load()

    # ----- helpers -----
    def _now(self):
        return self.now()

    def _gen_id(self, prefix):
        return prefix + uuid.uuid4().hex[:12]

    def _board_dir(self, board_id):
        return os.path.join(self.state_dir, "boards", board_id)

    def _ensure_board(self, board_id, origin, name=None, parent=None):
        if board_id in self.boards:
            return
        meta = {"id": board_id, "origin": origin, "name": name,
                "created": self._now(), "parent": parent}
        self.boards[board_id] = meta
        store.atomic_write_json(
            os.path.join(self._board_dir(board_id), "meta.json"), meta)

    def _persist_board_meta(self, board_id):
        store.atomic_write_json(
            os.path.join(self._board_dir(board_id), "meta.json"),
            self.boards[board_id])

    def _resolve_board_ref(self, ref):
        """Resolve an operator-supplied board reference to a known board id:
        an exact id first (named-/repo-/cwd-), else the named-board id for
        the bare name. None when nothing matches."""
        if ref is None:
            return None
        if ref in self.boards:
            return ref
        named = boards_mod.board_id_for_name(ref)
        if named in self.boards:
            return named
        return None

    def _audit_federation(self, line):
        """Append one line to <state_dir>/federation.log. This is an
        append-only audit log, not a state record — the atomic temp+replace
        rule applies to records; logs append (same idiom as the enroll/gate
        logs on the template side)."""
        os.makedirs(self.state_dir, exist_ok=True)
        path = os.path.join(self.state_dir, "federation.log")
        with open(path, "a") as fh:
            fh.write("%.3f %s\n" % (self._now(), line))

    def _persist_presence(self, p):
        store.atomic_write_json(
            os.path.join(self._board_dir(p.boards[0]), "presence",
                         p.session_id + ".json"),
            p.to_dict())

    def _persist_claim(self, c):
        store.atomic_write_json(
            os.path.join(self._board_dir(c.board), "claims",
                         c.id + ".json"),
            c.to_dict())

    def _persist_message(self, m):
        store.atomic_write_json(
            os.path.join(self._board_dir(m.board), "messages",
                         m.id + ".json"),
            m.to_dict())

    def _is_live(self, p):
        return (p.status == "active"
                and (self._now() - p.last_heartbeat)
                <= config.HEARTBEAT_STALE_SECONDS)

    def _repo_board(self, session_id):
        return self.presence[session_id].boards[0]

    def _primary_board(self, session_id):
        return self.presence[session_id].boards[-1]

    # ----- load -----
    def load(self):
        self.boards = {}
        self.presence = {}
        self.claims = {}
        self.messages = {}
        boards_root = os.path.join(self.state_dir, "boards")
        if not os.path.isdir(boards_root):
            return
        for board_id in os.listdir(boards_root):
            bdir = os.path.join(boards_root, board_id)
            if not os.path.isdir(bdir):
                continue
            meta = store.read_json(os.path.join(bdir, "meta.json"))
            if meta is not None:
                self.boards[board_id] = meta
            for _, d in store.iter_json(os.path.join(bdir, "presence")):
                p = Presence.from_dict(d)
                self.presence[p.session_id] = p
            for _, d in store.iter_json(os.path.join(bdir, "claims")):
                c = Claim.from_dict(d)
                self.claims[c.id] = c
            for _, d in store.iter_json(os.path.join(bdir, "messages")):
                m = Message.from_dict(d)
                self.messages[m.id] = m

    # ----- join -----
    def join(self, session_id, label, cwd, team=None, member=None,
             board_name=None):
        repo_board, origin = boards_mod.derive_repo_board(cwd)
        self._ensure_board(repo_board, origin, name=None)
        board_list = [repo_board]
        if board_name:
            named_id = boards_mod.board_id_for_name(board_name)
            self._ensure_board(named_id, "named:" + board_name,
                               name=board_name)
            board_list.append(named_id)

        now = self._now()
        existing = self.presence.get(session_id)
        was_offline = existing is not None and existing.status == "offline"
        newly_created = existing is None
        joined = existing.joined if existing is not None else now

        p = Presence(
            session_id=session_id,
            label=label,
            cwd=cwd,
            boards=board_list,
            joined=joined,
            last_heartbeat=now,
            status="active",
            team=team,
            member=member,
        )
        self.presence[session_id] = p
        self._persist_presence(p)

        colocated = {}
        if newly_created or was_offline:
            for bid in board_list:
                # Federated colocation: a joiner on a parent board counts the
                # live fleet across its subtree (presence rolls UP only). With
                # no children this is exactly the v1 single-board check.
                sub = set(boards_mod.subtree(self.boards, bid))
                others = []
                for other in self.presence.values():
                    if other.session_id == session_id:
                        continue
                    if (sub & set(other.boards)) and self._is_live(other):
                        others.append(other.label)
                if others:
                    colocated[bid] = others
                    origin_kind = ("checkout"
                                   if bid == repo_board else "board")
                    n_active = len(others) + 1
                    body = ("%s joined %s — %d now active; coordinate via "
                            "mailbox" % (label, origin_kind, n_active))
                    m = Message(
                        id=self._gen_id("msg_"),
                        board=bid,
                        from_session=session_id,
                        from_label=label,
                        to="*",
                        kind="note",
                        body=body,
                        created=now,
                    )
                    self.messages[m.id] = m
                    self._persist_message(m)

        return {"boards": board_list, "colocated": colocated,
                "label": label}

    # ----- topology (multi-board federation) -----
    def create_board(self, name, parent=None):
        """Mint (or reuse) the named board for `name`; optionally link it
        under an EXISTING parent (operators build top-down). Validation per
        boards.validate_parent; errors are returned as {"error": ...} and
        never persisted."""
        board_id = boards_mod.board_id_for_name(name)
        parent_id = None
        if parent is not None:
            parent_id = self._resolve_board_ref(parent)
            if parent_id is None:
                return {"error": "no-such-board: " + str(parent)}
        if board_id not in self.boards:
            self._ensure_board(board_id, "named:" + name, name=name)
        if parent_id is not None:
            err = boards_mod.validate_parent(self.boards, board_id, parent_id)
            if err:
                return {"error": err}
            self.boards[board_id]["parent"] = parent_id
            self._persist_board_meta(board_id)
        self._audit_federation(
            "create-board id=%s parent=%s" % (board_id, parent_id))
        meta = self.boards[board_id]
        return {"id": board_id, "name": meta.get("name"),
                "parent": meta.get("parent")}

    def set_parent(self, board, parent=None, detach=False):
        """Re-parent `board` under `parent` (cycle/depth-validated), or
        detach it into a root. Both refs accept a board id or a bare name."""
        board_id = self._resolve_board_ref(board)
        if board_id is None:
            return {"error": "no-such-board: " + str(board)}
        was = self.boards[board_id].get("parent")
        if detach:
            self.boards[board_id]["parent"] = None
            self._persist_board_meta(board_id)
            self._audit_federation(
                "set-parent id=%s parent=None was=%s" % (board_id, was))
            return {"id": board_id, "parent": None, "was": was}
        parent_id = self._resolve_board_ref(parent)
        if parent_id is None:
            return {"error": "no-such-board: " + str(parent)}
        err = boards_mod.validate_parent(self.boards, board_id, parent_id)
        if err:
            return {"error": err}
        self.boards[board_id]["parent"] = parent_id
        self._persist_board_meta(board_id)
        self._audit_federation(
            "set-parent id=%s parent=%s was=%s" % (board_id, parent_id, was))
        return {"id": board_id, "parent": parent_id, "was": was}

    # ----- tree -----
    def tree(self, board=None):
        """Topology render data: {"roots": [node...]}; node = {"id", "name",
        "orphan", "children": [...]}. A board whose parent id has no meta is
        surfaced as an orphan root (spec: degrade gracefully). Cycle-safe via
        a visited set."""
        if board is not None:
            root_id = self._resolve_board_ref(board)
            if root_id is None:
                return {"error": "no-such-board: " + str(board)}
            root_ids = [root_id]
            orphans = set()
        else:
            root_ids = []
            orphans = set()
            for bid in sorted(self.boards):
                parent = self.boards[bid].get("parent")
                if not parent:
                    root_ids.append(bid)
                elif parent not in self.boards:
                    root_ids.append(bid)
                    orphans.add(bid)

        seen = set()

        def _node(bid):
            seen.add(bid)
            meta = self.boards.get(bid, {})
            children = []
            for cid in sorted(self.boards):
                if cid in seen:
                    continue
                if self.boards[cid].get("parent") == bid:
                    children.append(_node(cid))
            return {"id": bid, "name": meta.get("name"),
                    "orphan": bid in orphans, "children": children}

        return {"roots": [_node(r) for r in root_ids]}

    # ----- heartbeat -----
    def heartbeat(self, session_id):
        p = self.presence.get(session_id)
        if p is None:
            return {"ok": False, "need_join": True}
        now = self._now()
        p.last_heartbeat = now
        if p.status == "offline":
            p.status = "active"
        self._persist_presence(p)
        new_expires = now + config.AUTO_CLAIM_TTL_SECONDS
        for c in self.claims.values():
            if (c.session_id == session_id and c.kind == "auto"
                    and not c.released and c.expires >= now):
                c.expires = new_expires
                self._persist_claim(c)
        return {"ok": True}

    # ----- leave -----
    def leave(self, session_id):
        p = self.presence.get(session_id)
        if p is not None:
            p.status = "offline"
            self._persist_presence(p)
        for c in self.claims.values():
            if c.session_id == session_id and not c.released:
                c.released = True
                self._persist_claim(c)
        return {"ok": True}

    # ----- check_write -----
    def check_write(self, session_id, abs_path):
        presence = self.presence.get(session_id)
        if presence is None:
            return {"decision": "allow", "reason": "no-presence"}

        boards = set(presence.boards)

        conflicts = []
        for c in self.claims.values():
            if c.released:
                continue
            if c.session_id == session_id:
                continue
            if c.board not in boards:
                continue
            if any(matching.path_matches(g, abs_path) for g in c.paths):
                conflicts.append(c)

        live = []
        for c in conflicts:
            holder = self.presence.get(c.session_id)
            if holder is not None and self._is_live(holder):
                live.append(c)

        if live:
            c = live[0]
            holder = self.presence.get(c.session_id)
            return {
                "decision": "deny",
                "holder": c.label,
                "holder_session": c.session_id,
                "note": c.note,
                "since_seconds": self._now() - holder.last_heartbeat,
                "claim_id": c.id,
            }

        if conflicts:
            c = conflicts[0]
            holder = self.presence.get(c.session_id)
            if holder is not None:
                stale_seconds = self._now() - holder.last_heartbeat
            else:
                stale_seconds = self._now() - c.created
            return {
                "decision": "warn",
                "holder": c.label,
                "note": c.note,
                "stale_seconds": stale_seconds,
                "claim_id": c.id,
            }

        repo_board = self._repo_board(session_id)
        auto = None
        for c in self.claims.values():
            if (
                c.session_id == session_id
                and c.board == repo_board
                and c.kind == "auto"
                and not c.released
            ):
                auto = c
                break

        now = self._now()
        expires = now + config.AUTO_CLAIM_TTL_SECONDS
        if auto is None:
            auto = Claim(
                id=self._gen_id("clm_"),
                board=repo_board,
                session_id=session_id,
                label=presence.label,
                paths=[abs_path],
                kind="auto",
                created=now,
                expires=expires,
            )
            self.claims[auto.id] = auto
        else:
            if abs_path not in auto.paths:
                auto.paths.append(abs_path)
            auto.expires = expires

        self._persist_claim(auto)
        return {"decision": "allow", "claim_id": auto.id}

    # ----- lanes -----
    # A "lane" is a named work-unit (subtask) for dogpile coordination. It is
    # stored as a claim whose single path is the URI "lane://<id>". Because that
    # string contains no glob wildcards and never starts with "/", it can only
    # ever match itself via matching.path_matches -- so lanes and real file
    # paths are mutually invisible, and the whole conflict engine (live->deny,
    # stale->warn, release, seize, reload) works on lanes unchanged.
    _LANE_PREFIX = "lane://"

    def _lane_uri(self, lane):
        return self._LANE_PREFIX + lane

    def claim_lane(self, session_id, lane, note=None):
        uri = self._lane_uri(lane)

        # Already mine and live? Idempotent -- return the existing claim.
        for c in self.claims.values():
            if (c.session_id == session_id and not c.released
                    and uri in c.paths):
                return {"decision": "allow", "lane": lane, "claim_id": c.id}

        # Conflict scan: same shape as check_write, scoped to shared boards.
        presence = self.presence.get(session_id)
        boards = set(presence.boards) if presence is not None else set()
        conflicts = []
        for c in self.claims.values():
            if c.released or c.session_id == session_id:
                continue
            if c.board not in boards:
                continue
            if uri in c.paths:
                conflicts.append(c)

        live = []
        for c in conflicts:
            holder = self.presence.get(c.session_id)
            if holder is not None and self._is_live(holder):
                live.append(c)

        if live:
            c = live[0]
            holder = self.presence.get(c.session_id)
            return {
                "decision": "deny",
                "lane": lane,
                "holder": c.label,
                "holder_session": c.session_id,
                "note": c.note,
                "since_seconds": self._now() - holder.last_heartbeat,
                "claim_id": c.id,
            }

        if conflicts:
            c = conflicts[0]
            holder = self.presence.get(c.session_id)
            if holder is not None:
                stale_seconds = self._now() - holder.last_heartbeat
            else:
                stale_seconds = self._now() - c.created
            return {
                "decision": "warn",
                "lane": lane,
                "holder": c.label,
                "note": c.note,
                "stale_seconds": stale_seconds,
                "claim_id": c.id,
            }

        created = self.claim(session_id, [uri], note=note, kind="explicit")
        return {"decision": "allow", "lane": lane,
                "claim_id": created["id"]}

    def release_lane(self, session_id, lane):
        return self.release(session_id, self._lane_uri(lane))

    def list_lanes(self, session_id):
        p = self.presence.get(session_id)
        boards = set(p.boards) if p is not None else set()
        out = []
        for c in self.claims.values():
            if c.released:
                continue
            if c.board not in boards:
                continue
            lane_paths = [pth for pth in c.paths
                          if pth.startswith(self._LANE_PREFIX)]
            if not lane_paths:
                continue
            holder = self.presence.get(c.session_id)
            live = holder is not None and self._is_live(holder)
            for pth in lane_paths:
                out.append({
                    "lane": pth[len(self._LANE_PREFIX):],
                    "claim_id": c.id,
                    "session_id": c.session_id,
                    "label": c.label,
                    "note": c.note,
                    "live": live,
                })
        out.sort(key=lambda r: r["lane"])
        return out

    # ----- claim -----
    def claim(self, session_id, globs, note=None, kind="explicit"):
        board = self._repo_board(session_id)
        label = ""
        p = self.presence.get(session_id)
        if p is not None:
            label = p.label
        now = self._now()
        if kind == "explicit":
            ttl = config.EXPLICIT_CLAIM_TTL_SECONDS
        else:
            ttl = config.AUTO_CLAIM_TTL_SECONDS
        c = Claim(
            id=self._gen_id("clm_"),
            board=board,
            session_id=session_id,
            label=label,
            paths=list(globs),
            kind=kind,
            created=now,
            expires=now + ttl,
            released=False,
            note=note,
        )
        self.claims[c.id] = c
        self._persist_claim(c)
        return c.to_dict()

    # ----- release -----
    def release(self, session_id, selector, force=False):
        released = []
        if selector == "all":
            for c in self.claims.values():
                if c.session_id == session_id and not c.released:
                    c.released = True
                    self._persist_claim(c)
                    released.append(c.id)
            return {"released": released}
        target = self.claims.get(selector)
        if target is not None:
            if not target.released and (target.session_id == session_id or force):
                target.released = True
                self._persist_claim(target)
                released.append(target.id)
            return {"released": released}
        # selector is treated as an exact glob string
        for c in self.claims.values():
            if c.session_id == session_id and not c.released and selector in c.paths:
                c.released = True
                self._persist_claim(c)
                released.append(c.id)
        return {"released": released}

    # ----- seize -----
    def seize(self, session_id, abs_path):
        conflicts = []
        for c in self.claims.values():
            if c.released or c.session_id == session_id:
                continue
            if any(matching.path_matches(g, abs_path) for g in c.paths):
                conflicts.append(c)
        for c in conflicts:
            holder = self.presence.get(c.session_id)
            if holder is not None and self._is_live(holder):
                return {"error": "holder-live", "holder": c.label}
        seized = []
        for c in conflicts:
            c.released = True
            self._persist_claim(c)
            seized.append(c.id)
        claim = self.claim(session_id, [abs_path], note="seized", kind="explicit")
        return {"seized": seized, "claim": claim}

    # ----- send -----
    def send(self, session_id, to, kind, body, ref_paths=None, scope="local"):
        if scope not in ("local", "escalate", "broadcast"):
            return {"error": "bad-scope: " + str(scope)}
        presence = self.presence.get(session_id)
        if presence is None:
            return {"error": "no presence for session"}
        board = self._primary_board(session_id)
        msg = Message(
            id=self._gen_id("msg_"),
            board=board,
            from_session=session_id,
            from_label=presence.label,
            to=to,
            kind=kind,
            body=body,
            created=self._now(),
            read_by=[],
            ref_paths=list(ref_paths) if ref_paths else [],
            scope=scope,
        )
        self.messages[msg.id] = msg
        self._persist_message(msg)
        if scope != "local":
            body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
            self._audit_federation(
                "send scope=%s board=%s from=%s body_sha=%s"
                % (scope, board, presence.label, body_sha))
        return {"id": msg.id}

    # ----- federated reads (multi-board federation) -----
    def federated_messages(self, board_id):
        """Read-time federation (spec §3): own messages (any scope), plus
        escalations from descendants, plus broadcasts from ancestors. Pure
        filter over the in-RAM message dict; each row is annotated with its
        origin board and direction ("local" | "up" | "down") so a renderer
        can show 'escalated from squad-api' / 'broadcast from org'."""
        anc = set(boards_mod.ancestors(self.boards, board_id))
        desc = set(boards_mod.descendants(self.boards, board_id))
        out = []
        for m in self.messages.values():
            if m.board == board_id:
                direction = "local"
            elif m.board in desc and m.scope == "escalate":
                direction = "up"
            elif m.board in anc and m.scope == "broadcast":
                direction = "down"
            else:
                continue
            d = m.to_dict()
            d["origin_board"] = m.board
            d["direction"] = direction
            out.append(d)
        out.sort(key=lambda d: d["created"])
        return out

    # ----- poll_inbox -----
    def poll_inbox(self, session_id, federated=True):
        presence = self.presence.get(session_id)
        if presence is None:
            return []
        boards = set(presence.boards)
        # Federated view (D2: federated by default; degenerates to the v1
        # local behavior when no board has a parent or children).
        fed_up = set()       # boards whose ESCALATIONS this session sees
        fed_down = set()     # boards whose BROADCASTS this session sees
        if federated:
            for b in boards:
                fed_up.update(boards_mod.descendants(self.boards, b))
                fed_down.update(boards_mod.ancestors(self.boards, b))
        label = presence.label
        matched = []
        directions = {}
        for msg in self.messages.values():
            if msg.board in boards:
                direction = "local"
            elif msg.board in fed_up and msg.scope == "escalate":
                direction = "up"
            elif msg.board in fed_down and msg.scope == "broadcast":
                direction = "down"
            else:
                continue
            if msg.from_session == session_id:
                continue
            if session_id in msg.read_by:
                continue
            if msg.to == "*" or msg.to == session_id or msg.to == label:
                matched.append(msg)
                directions[msg.id] = direction
        matched.sort(key=lambda m: m.created)
        result = []
        for msg in matched:
            msg.read_by.append(session_id)
            self._persist_message(msg)
            d = msg.to_dict()
            d["origin_board"] = msg.board
            d["direction"] = directions[msg.id]
            result.append(d)
        return result

    # ----- request_release -----
    def request_release(self, session_id, abs_path):
        holder = None
        for claim in self.claims.values():
            if claim.released:
                continue
            if claim.session_id == session_id:
                continue
            if any(matching.path_matches(g, abs_path) for g in claim.paths):
                holder = claim
                break
        if holder is None:
            return {"error": "no-holder"}
        self.send(
            session_id=session_id,
            to=holder.label,
            kind="release-request",
            body="Please release " + abs_path,
            ref_paths=[abs_path],
        )
        return {"sent_to": holder.label}

    # ----- list_claims -----
    def list_claims(self, session_id, scope="board"):
        p = self.presence.get(session_id)
        if p is not None:
            boards = set(p.boards)
        else:
            boards = set()
        out = []
        for c in self.claims.values():
            if c.released:
                continue
            if scope == "mine":
                if c.session_id != session_id:
                    continue
            elif scope == "all":
                pass
            else:  # "board"
                if c.board not in boards:
                    continue
            holder = self.presence.get(c.session_id)
            if holder is None or holder.status == "offline":
                holder_status = "offline"
            elif self._is_live(holder):
                holder_status = "active"
            else:
                holder_status = "stale"
            entry = c.to_dict()
            entry["live"] = holder_status == "active"
            entry["holder_status"] = holder_status
            out.append(entry)
        return out

    # ----- _status_of -----
    def _status_of(self, p):
        # "active" if live (fresh heartbeat); "stale" if active-status but past
        # the stale threshold; "offline" if marked offline.
        if p.status == "offline":
            return "offline"
        if self._is_live(p):
            return "active"
        return "stale"

    # ----- ps -----
    def ps(self, session_id):
        me = self.presence.get(session_id)
        if me is None:
            return []
        my_boards = set(me.boards)
        rows = []
        for p in self.presence.values():
            if not (my_boards & set(p.boards)):
                continue
            rows.append({
                "session_id": p.session_id,
                "label": p.label,
                "cwd": p.cwd,
                "member": p.member,
                "status": self._status_of(p),
                "last_seen_seconds": self._now() - p.last_heartbeat,
                "boards": list(p.boards),
            })
        rows.sort(key=lambda r: r["label"])
        return rows

    # ----- whoami -----
    def whoami(self, session_id):
        p = self.presence.get(session_id)
        if p is None:
            return {"exists": False}
        out = p.to_dict()
        out["exists"] = True
        return out

    # ----- board -----
    def board(self, session_id):
        me = self.presence.get(session_id)
        if me is None:
            return {"boards": []}
        out = []
        for board_id in me.boards:
            meta = self.boards.get(board_id, {})
            members = sum(
                1 for p in self.presence.values()
                if board_id in p.boards and p.status != "offline"
            )
            claim_count = sum(
                1 for c in self.claims.values()
                if c.board == board_id and not c.released
            )
            out.append({
                "id": board_id,
                "origin": meta.get("origin"),
                "name": meta.get("name"),
                "members": members,
                "claims": claim_count,
            })
        return {"boards": out}

    # ----- gc -----
    def gc(self):
        now = self._now()
        presence_offlined = 0
        claims_reaped = 0
        messages_gc = 0

        # 1) Live presence gone stale past OFFLINE_GRACE -> offline +
        #    release that session's auto claims.
        for p in self.presence.values():
            if p.status == "offline":
                continue
            if now - p.last_heartbeat > config.OFFLINE_GRACE_SECONDS:
                p.status = "offline"
                presence_offlined += 1
                self._persist_presence(p)
                for c in self.claims.values():
                    if (c.session_id == p.session_id
                            and c.kind == "auto"
                            and not c.released):
                        c.released = True
                        claims_reaped += 1
                        self._persist_claim(c)

        # 2) Claims:
        #    a) released + old (> MESSAGE_RETENTION since created) -> delete.
        #    b) auto expired (now > expires) -> released.
        #    c) holder offline -> released.
        for c in list(self.claims.values()):
            if c.released and now - c.created > config.MESSAGE_RETENTION_SECONDS:
                path = os.path.join(
                    self._board_dir(c.board), "claims", c.id + ".json")
                store.remove(path)
                del self.claims[c.id]
                claims_reaped += 1
                continue
            if not c.released and c.kind == "auto" and now > c.expires:
                c.released = True
                claims_reaped += 1
                self._persist_claim(c)
                continue
            if not c.released:
                holder = self.presence.get(c.session_id)
                if holder is not None and holder.status == "offline":
                    c.released = True
                    claims_reaped += 1
                    self._persist_claim(c)

        # 3) Messages older than MESSAGE_RETENTION -> delete.
        for m in list(self.messages.values()):
            if now - m.created > config.MESSAGE_RETENTION_SECONDS:
                path = os.path.join(
                    self._board_dir(m.board), "messages", m.id + ".json")
                store.remove(path)
                del self.messages[m.id]
                messages_gc += 1

        # 4) Offline presence older than PRESENCE_RETENTION -> delete.
        for p in list(self.presence.values()):
            if (p.status == "offline"
                    and now - p.last_heartbeat > config.PRESENCE_RETENTION_SECONDS):
                for board_id in p.boards:
                    path = os.path.join(
                        self._board_dir(board_id),
                        "presence", p.session_id + ".json")
                    store.remove(path)
                del self.presence[p.session_id]

        return {
            "presence_offlined": presence_offlined,
            "claims_reaped": claims_reaped,
            "messages_gc": messages_gc,
        }
