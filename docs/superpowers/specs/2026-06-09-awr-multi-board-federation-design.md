# Multi-Board Hierarchical Federation — Design

- **Date:** 2026-06-09
- **Sub-project of:** Agentic War Room (AWR). Extends the **mailbox coordination
  package** (`coordination/`) and the **war-room agent template** (`template/`).
- **Depends on:** the mailbox engine's board/presence/message/claim model
  (`coordination/src/mailbox/`); the template's `enroll`/`schema` enrollment path.
- **Referenced by:** `2026-06-09-awr-defcon-severity-design.md` (severity can drive
  auto-escalation) and `2026-06-09-awr-l1-orchestrator-design.md` (the orchestrator
  routes across a federation). This spec is the foundation those two build on.
- **Status:** design, pre-implementation.

## Problem

Today one agent = one home board. The mailbox engine can place a session on its
cwd-derived repo board **plus at most one** named board (`engine.join(...,
board_name=...)` → `board_list = [repo_board] (+ [named])`). There is no notion of
boards relating to each other.

We want **hierarchical federation**: boards form a tree (squad → team → org). An
operator runs N agents across the tree, and signal flows **both directions**:

- **Escalate up** — a child surfaces something to its ancestors (an incident on
  `squad-api` should be visible on `team-platform` and `org`).
- **Broadcast down** — an ancestor reaches all descendants (an `org`-wide
  announcement reaches every squad).

The operator must be able to build and inspect the topology, and see the fleet of
agents across it.

## Core decisions (from brainstorming 2026-06-09)

1. **Topology = a tree** (squad → team → org), arbitrary depth (capped, see below).
2. **Bidirectional propagation** — escalate up AND broadcast down.
3. **Topology lives in board metadata.** Each board's `meta.json` gains an optional
   `parent` (a board id). The engine builds the tree from these links. Decentralized,
   engine-native, survives across profiles, no per-agent config drift.
4. **Primary mechanism = read-time federated views.** Messages carry a `scope`
   (`local` | `escalate` | `broadcast`); the federated set for a board is resolved by
   walking the tree at read time over the engine's already-in-RAM data. No copying,
   no dedup, no message loops, always consistent with the live topology.
5. **The agent still joins exactly ONE home board.** Federation is resolved
   server-side via the tree, so `<profile>/.env` stays single-board (`MAILBOX_BOARD`
   = home). No `MAILBOX_BOARDS` list, no multi-join, no template runtime change beyond
   recording a board's parent at enroll time.
6. **Comprehensive scope.** This spec covers the full feature set — topology,
   read-time federation, presence/claims federation, write-time broadcast delivery,
   and the operator surface. Sequencing is expressed in **Build order** (§Build
   order), not by omission.

## Current state (VERIFIED against `coordination/` source, 2026-06-09)

- `engine.join(session_id, label, cwd, team, member, board_name=None)` →
  `board_list = [repo_board]`, appends one `named-<slug>` board if `board_name` set.
  Persists a `Presence(boards=board_list, ...)`. (`engine.py:98-130`)
- `_ensure_board(board_id, origin, name=None)` writes
  `meta = {"id", "origin", "name", ...}` to `boards/<id>/meta.json`. (`engine.py:33-40`)
- Models: `Message.board`, `Claim.board`, `Presence.boards: List[str]`
  (`boards[0]` = repo board, `boards[1:]` = named). (`models.py:6-90`)
- On load, the engine iterates **every** board dir and merges all presence/claims/
  messages into **global in-RAM dicts** keyed by id (`self.presence`, `self.claims`,
  `self.messages`), each record carrying its own `board`. (`engine.py:77-95`) — this
  is what makes a federated view a cheap in-memory traversal.
- `boards.py`: `derive_repo_board(cwd)`, `board_id_for_name(name) -> "named-"+slug`.
- Hook `coordination/hooks/session_start.py:33` reads a single
  `board_name = os.environ.get("MAILBOX_BOARD")` and calls `join`.
- Template: `WAR_ROOM_KEYS`/`MAILBOX_KEYS` hold a single `board`; `enroll.bootstrap`
  writes `MAILBOX_BOARD`/`MAILBOX_LABEL` to `<profile>/.env`. (`schema.py`,
  `enroll.py:126-184`)

All changes below are **additive and backward-compatible**: a board with no
`parent` is a root; a message with no `scope` is `local`; existing single-board
installs behave identically.

## Architecture & components

Two layers:

- **`coordination/` (the engine of federation):** topology storage + validation,
  federated read resolution, write-time delivery, new CLI verbs, contract update.
- **`template/` (the consumer):** record a board's parent at enroll time; surface
  escalate/broadcast in the war-room skill docs. No runtime/.env shape change.

### 1. Topology model (`coordination/`)

- `meta.json` gains `parent: <board_id> | null` (default `null` = root). Set via
  `_ensure_board(..., parent=None)` and a new `set_parent` engine op.
- New pure helpers in `boards.py` (tree walks over `engine.boards` meta):
  - `parent_of(board_id) -> board_id | None`
  - `ancestors(board_id) -> [parent, grandparent, … root]`
  - `descendants(board_id) -> [all transitive children]`
  - `subtree(board_id) -> [board_id] + descendants`
  - `is_ancestor(a, b)`, `depth(board_id)`
- **Validation:** `set_parent`/`create-board --parent` reject (a) self-parenting,
  (b) a parent that is a descendant (cycle), and (c) trees deeper than
  `MAX_FEDERATION_DEPTH` (default 8) to bound traversal. The parent board must
  already exist (operators build top-down); clear error otherwise.

### 2. Message scope (`coordination/`)

- `Message.scope: str` ∈ {`local`, `escalate`, `broadcast`} (default `local`).
  Serialized in `to_dict`/`from_dict` with a `.get("scope", "local")` fallback for
  back-compat.
- A message always lives on exactly **one** origin board; `scope` says who *else*
  resolves it. `escalate` ⇒ ancestors see it; `broadcast` ⇒ descendants see it.
- Posting: `send`/`post` take an optional `scope`. An escalated/broadcast message
  retains its full body and (if present) its confidence envelope.

### 3. Federated read resolution — the core (Phase 1, `coordination/`)

`federated_messages(board_id) =`
- **own:** `{ m | m.board == board_id }` (any scope), ∪
- **escalated-up:** `{ m | m.board ∈ descendants(board_id) ∧ m.scope == "escalate" }`, ∪
- **broadcast-down:** `{ m | m.board ∈ ancestors(board_id) ∧ m.scope == "broadcast" }`.

Pure filter over the in-RAM `self.messages`. Each federated message is annotated
for the reader with its **origin board** and **direction** so the UI can render
"↑ escalated from `squad-api`" / "↓ broadcast from `org`". `inbox`/`read` and the
SessionStart colocation summary use this view; bare board reads (no federation)
remain available for debugging.

### 4. Presence & claims federation (Phase 2, `coordination/`)

Same traversal, applied to coordination state:
- `federated_presence(board_id)` — who is active across `subtree(board_id)` (an
  ancestor sees the whole fleet beneath it). `mailbox ps` on a parent shows the
  subtree, annotated by board.
- `federated_claims(board_id)` — file/lane claims across the subtree, so dogpile
  avoidance works across a federated team. Lane semantics unchanged; visibility
  widens to the subtree.

Direction note: presence/claims roll **up** only (a parent sees descendants'
coordination state). There is no "broadcast presence down" concept.

### 5. Write-time broadcast delivery (Phase 3, `coordination/`, optional enhancement)

Read-time broadcast means a descendant sees an ancestor's broadcast only when it
*reads*. For broadcasts that must **push** (fire each descendant's SessionStart/
inbox hook as a real local event), add optional delivery: a `broadcast` post fans
out a delivered copy to each descendant board's message store, tagged with
`origin_message_id` + an idempotency key. The tree is acyclic so message loops are
impossible; dedup guards only against re-delivery on topology edits. This is a
strict add-on — Phase 1's read-time broadcast keeps working unchanged. Gated behind
a per-board `delivery: push|pull` meta flag (default `pull` = read-time).

### 6. Operator surface (Phase 4, `coordination/`)

- `mailbox tree [<board>]` — ASCII topology render (whole forest or a subtree).
- `mailbox fleet [<board>]` — federated presence across the subtree (who/where).
- `mailbox create-board <name> --parent <name>` — mint a named board with a parent.
- `mailbox set-parent <board> <parent>` / `--detach` — re-parent (cycle-checked) or
  make a board a root.
- Existing `ps`/`claims`/`inbox`/`read` gain a `--federated/--local` toggle
  (federated default on a board that has a parent or children).

### 7. CLI surface (summary; `coordination/bin/mailbox` + `cli.py`)

| Verb | Purpose |
|---|---|
| `create-board <name> --parent <p>` | mint a named board under a parent |
| `set-parent <board> <p>` / `--detach` | re-parent (cycle-checked) / make root |
| `tree [<board>]` | render topology |
| `fleet [<board>]` | federated presence across the subtree |
| `escalate "<msg>"` (≡ `send --scope escalate`) | post visible to ancestors |
| `broadcast "<msg>"` (≡ `send --scope broadcast`) | post visible to descendants |
| `ps` / `claims` / `inbox` / `read` | gain `--federated/--local` |

### 8. War-room template layer (`template/`)

- `schema.py`: add optional `parent` alongside `board` in the war-room/mailbox
  managed keys (`WAR_ROOM_KEYS` / `MAILBOX_KEYS`) + defaults (`parent: ""`).
- `enroll.bootstrap(profile_root, board, label, parent=None, ...)`: when set, call
  the engine to ensure the home board's `meta.json` records `parent`. `.env` is
  **unchanged** — still a single `MAILBOX_BOARD` (the home board); federation is
  resolved server-side.
- Wizard (`setup.py` / walkthrough): one optional prompt — "Parent board (for
  federation; blank for a standalone board)".
- **Confidence gate is unaffected.** `escalate` changes visibility only; an
  escalated claim keeps its envelope/badge. (Cross-ref: the DEFCON/severity spec
  may make high-severity claims auto-escalate — that hook lives there, not here.)

## Data model & config

```jsonc
// boards/<id>/meta.json  (parent + optional delivery flag are new)
{ "id": "named-team-platform", "origin": "named:team-platform",
  "name": "team-platform", "parent": "named-org", "delivery": "pull" }
```

```jsonc
// Message (scope is new; defaults to "local")
{ "id": "...", "board": "named-squad-api", "scope": "escalate",
  "from": "api-sh", "body": "...", "envelope": {...} }
```

```yaml
# <profile>/config.yaml — war-room managed block (parent is new, optional)
war_room:
  board: squad-api
  parent: team-platform     # NEW — blank/absent => standalone root
  # ...existing keys unchanged...
```

`<profile>/.env` shape is **unchanged**: `MAILBOX_BOARD=squad-api`,
`MAILBOX_LABEL=…`.

## Reliability — failure modes

- **Cycle / self-parent:** rejected at `set_parent`/`create-board` with a clear
  error; never persisted.
- **Depth > MAX_FEDERATION_DEPTH:** rejected (bounds traversal cost, guards against
  pathological trees).
- **Missing parent:** `--parent` requires the parent to exist; clear error.
- **Orphaned board (parent deleted):** treated as a root; `tree` shows it at top
  level with a warning. Federated views degrade gracefully (a missing ancestor just
  drops out of the walk).
- **Back-compat:** no `parent` ⇒ root; no `scope` ⇒ `local`; a root board with no
  children resolves `federated_messages == own messages`. Existing tests must stay
  green unchanged.
- **Topology edits are live:** read-time resolution means re-parenting instantly
  changes what each board sees — no stale cache to invalidate. (Phase 3 push
  delivery is the one place that needs idempotency on re-delivery.)

## Security

- Federation honors existing board boundaries — a board only ever resolves messages
  whose origin is in its own subtree (broadcast) or supertree (escalate); siblings/
  cousins are invisible. No new cross-board read path beyond the tree relation.
- Escalated/broadcast records keep their original `from` + `origin board`, so a
  message can't be spoofed as originating elsewhere.
- Audit log (see Observability) records escalate/broadcast as decisions; bodies are
  hashed per the existing gate-audit convention — no secret leakage on roll-up.

## Observability

- `mailbox tree` / `mailbox fleet` give the operator a live topology + fleet view.
- Federated reads annotate origin + direction on every surfaced record.
- Engine logs topology mutations (`set_parent`, `create-board`) and escalate/
  broadcast posts (origin, scope, target relation) for an audit trail.

## Test strategy

**`coordination/tests`:**
- Unit: `ancestors`/`descendants`/`subtree`/`is_ancestor`/`depth`; cycle &
  self-parent rejection; depth cap; `federated_messages` resolution (own /
  escalate-up / broadcast-down, and the root/leaf degenerate cases);
  `federated_presence`/`federated_claims`; `tree` render; new CLI verbs; scope
  serialization back-compat.
- Integration (real daemon): build a 3-level tree (`org → team → squad`); post a
  `local`, an `escalate`, and a `broadcast`; assert each board's federated read is
  exactly the expected set; re-parent and assert views update live; Phase 3:
  assert push delivery fires the descendant hook exactly once (idempotent).

**`template/tests`:**
- `enroll.bootstrap(parent=...)` records `parent` in the home board's meta and
  leaves `.env` single-board; schema accepts `parent`; no-parent ⇒ root back-compat.

## File-path map (complete)

**`coordination/` (engine of federation):**
- `coordination/src/mailbox/models.py` — `Message.scope`; `meta` `parent`/`delivery`
  helpers (board meta stays a dict).
- `coordination/src/mailbox/boards.py` — tree helpers (`ancestors`, `descendants`,
  `subtree`, `is_ancestor`, `depth`, cycle validation, `MAX_FEDERATION_DEPTH`).
- `coordination/src/mailbox/engine.py` — `_ensure_board(parent=…)`, `set_parent`,
  `federated_messages`/`federated_presence`/`federated_claims`, scope on `send`,
  Phase 3 push delivery, op handlers for new verbs.
- `coordination/src/mailbox/cli.py` — `create-board`, `set-parent`, `tree`, `fleet`,
  `escalate`, `broadcast`, `--federated/--local` flags.
- `coordination/bin/mailbox` — dispatch for new verbs (if not pure cli.py).
- `coordination/hooks/session_start.py` — federated colocation summary (still reads
  single `MAILBOX_BOARD`; no env shape change).
- `coordination/docs/internal/contract.md` — document new ops/fields (the mailbox
  contract is the source of truth for callers).
- `coordination/docs/specs/` — link this design from the mailbox spec index.
- `coordination/tests/` — `test_federation.py` (new), extend `test_engine*`,
  `test_cli*`, `test_hooks.py`.

**`template/` (consumer):**
- `template/warroom_setup/schema.py` — `parent` key + default.
- `template/warroom_setup/enroll.py` — `bootstrap(parent=…)` → engine `set_parent`.
- `template/warroom_setup/setup.py` — managed-block carries `parent` (Option B
  sentinel rewrite is parent-safe).
- `template/warroom_setup/selectables.py` — optional `parent` TextField
  (`enable_if="warroom.enroll"`).
- `template/skills/warroom/SKILL.md` + `template/skills/confidence-gate/SKILL.md` —
  document escalate/broadcast in the war-room protocol.
- `template/tests/` — `test_enroll*`, `test_schema*` extensions.

## Build order (phasing — NOT omission; everything above is in scope)

1. **Phase 1 — foundation + read-time federation:** topology (`parent`, helpers,
   validation), `Message.scope`, `federated_messages`, CLI (`create-board`,
   `set-parent`, `tree`, `escalate`, `broadcast`), template `parent` wiring,
   contract update. This alone delivers working bidirectional federation.
2. **Phase 2 — presence/claims federation:** `federated_presence`/`federated_claims`,
   `mailbox fleet`, `ps`/`claims` `--federated`.
3. **Phase 3 — write-time broadcast delivery:** opt-in push for broadcasts that must
   fire descendant hooks; idempotency + `delivery` meta flag.
4. **Phase 4 — operator surface polish:** richer `tree`/`fleet` rendering, re-parent
   ergonomics, fleet annotations.

Each phase is independently shippable and leaves the system green.

## Out of scope (this spec)

- **Per-board access control / permissions** (who may join or read a board) — a
  separate security concern, orthogonal to topology.
- **Cross-machine / networked federation** — the mailbox state dir is single-host;
  multi-host sync is a future transport problem.
- **Automatic severity-driven escalation** — lives in the DEFCON/severity spec,
  which calls this spec's `escalate`.

## Open questions

1. **`delivery` default** — confirm `pull` (read-time) is the right global default,
   with `push` opt-in per board. (Recommend yes; push is the exception.)
2. **`mailbox ps` federation default** — should `ps` on a board *with* a parent or
   children default to federated, or stay local unless `--federated`? (Recommend
   federated-by-default when the board participates in a tree; `--local` to scope
   down.)
3. **Re-parent of a board with live broadcasts (Phase 3 push)** — on re-parent, do
   we re-deliver to the new subtree? (Recommend no retroactive re-delivery; new
   broadcasts only — keeps idempotency simple.)
