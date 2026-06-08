# War-Room Agent (Hermes profile distribution)

A personalizable Hermes agent for the Agentic War Room: Discord + Slack in, a
dual-runtime persona (Hermes `SOUL.md` + a Claude Code head), and a stub that
joins an AWR coordination board.

_Shared-core (mailbox routing, Discord/Slack walkthroughs, sanitization guard) as of 2026-06-08._

## Prerequisites
1. Install Hermes Agent (>=0.12): see the Hermes docs. Confirm with `hermes --version`.

## Install
**Local (this repo / dev):** `distribution.yaml` is at the root of this directory.
```sh
hermes profile install /path/to/agentic-war-room/template --name war-room-agent
```
**Public (git URL):** Hermes installs only from a repo whose `distribution.yaml`
is at the **root**. Use the published distribution repo (produced by
`scripts/publish.sh`):
```sh
hermes profile install https://github.com/<you>/war-room-agent-dist --name war-room-agent
```

## Personalize (required — install runs no setup automatically)
```sh
cd ~/.hermes/profiles/war-room-agent
bash scripts/setup.sh                 # interactive wizard (arrow/space/Enter/Esc + prompts)
bash scripts/setup.sh --yes           # headless: replay saved answers / defaults
bash scripts/setup.sh --reconfigure   # re-run the picker
bash scripts/setup.sh --sync          # only recompile SOUL.md + Claude head after editing local/persona/
```
Setup seeds your editable persona into `local/persona/` (this survives
`hermes profile update`), collects identity/tokens, writes `.env`, patches
`config.yaml`, and compiles `SOUL.md` + `~/.claude/agents/<name>.md`.

Fill in your persona: edit `local/persona/*.md` (replace every `<<FILL-IN>>`),
then `bash scripts/setup.sh --sync`.

## Run
```sh
hermes -p war-room-agent gateway install     # one-time: writes the launchd service
hermes -p war-room-agent gateway restart     # start / restart after changes
hermes -p war-room-agent gateway status
```

## Updating the template
`hermes profile update war-room-agent` refreshes shipped files (skills, the
`persona/` skeleton, templates) but PRESERVES your `.env`, `config.yaml`, and the
entire `local/` overlay (your filled persona + identity). After an update, run
`bash scripts/setup.sh --sync` to recompile from your overlay.

## Memory convention
The agent's durable memory lives in two Markdown files under `memories/` (this
directory is user-owned and survives `hermes profile update`):
- `memories/USER.md` — durable **facts about the operator**: preferences,
  workflow, hard constraints.
- `memories/MEMORY.md` — **session-flavored knowledge** learned over time that is
  worth carrying forward (not operator facts).

Both files use the same on-disk shape: a flat list of entries, where each entry
is separated from the next by a line containing only the section sign `§`. An
entry is free-form Markdown. Ship them empty (header only); the agent appends
entries over time. This README is the single source of truth for the convention.

## Provisioning the channels
- **Discord:** create an app, enable **Message Content** + **Server Members**
  intents, set `DISCORD_BOT_TOKEN` + `DISCORD_ALLOWED_USERS` in `.env`, invite the bot.
- **Slack:** Socket Mode app; set `SLACK_BOT_TOKEN` (xoxb-) + `SLACK_APP_TOKEN` (xapp-).

## Coordination (mailbox routing)
The agent joins an AWR coordination board via the mailbox runtime. Routing config
is **non-secret** and lives in a top-level `mailbox:` block in `config.yaml` — NOT
in `.env` (env is tokens-only) and NOT in any `local/*.env` file:
```yaml
mailbox:
  board: default          # board to join
  label: <your-handle>    # how you appear on the board (defaults to your handle)
  mailbox_home: ""         # blank -> mailbox runtime default location
  socket_path: ""          # blank -> mailbox runtime default location
```
`war_room.board` (the confidence-gate scope) and `mailbox.board` are kept in sync
by the wizard — it writes the same value to both. The gate reads only
`war_room.board`; cross-agent routing reads only `mailbox.board`.

What `warroom setup` does for coordination: records `board` and `label` in the
`mailbox:` block (the canonical, human-readable source), then runs `warroom
enroll`, which persists runtime state and writes `MAILBOX_BOARD` / `MAILBOX_LABEL`
into `<profile>/.env`. Hermes loads `.env` into the environment that reaches
mailbox's own `SessionStart` hook, so the next session joins the chosen board.
No `~/.claude/settings.json` edit and no extra hook are installed — config.yaml
is what you read/edit, `.env` is the runtime delivery channel, and the wizard
keeps them in sync (re-sync a manual config.yaml edit with
`warroom enroll --reconfigure`).

### Installing the mailbox runtime
Cross-agent features need the `mailbox` CLI/daemon. If `warroom enroll` reports
`cli-not-found`, install it:
```
python3 coordination/install.py        # from a checkout
```
Discovery precedence: `$MAILBOX_HOME/mailbox` → `~/.claude/mailbox/mailbox` →
`<repo>/coordination/bin/mailbox` (checkout only) → `mailbox` on `$PATH`. Set
`MAILBOX_HOME` to relocate the runtime; the expected installed layout is a
symlink at `~/.claude/mailbox/mailbox`.

### `warroom enroll`
```
warroom enroll --board shared --label alpha-sh   # (re)wire routing
warroom enroll --status                          # print JSON + daemon reachability
warroom enroll --reconfigure                      # force re-write past the no-op guard
```
Exit codes: `0` ok+reachable, `1` cli-not-found, `2` ok-but-daemon-unreachable
(`--status` only), `3` never enrolled. `--status` pings the socket with a stdlib
connect — it never spawns a daemon.

### How profiles meet on a board
Two profiles that set the same `mailbox.board` land on the same named board
regardless of cwd. `warroom enroll` writes `MAILBOX_BOARD` / `MAILBOX_LABEL`
(and, only when non-default, `MAILBOX_HOME` / `MAILBOX_SOCKET`) into
`<profile>/.env`; Hermes carries those into mailbox's own SessionStart hook,
which joins the chosen board:
```
# Terminal 1
hermes profile install ./template --name alpha-sh --alias --force -y
bash scripts/setup.sh          # wire routing BEFORE first chat (see caveat below)
hermes -p alpha-sh chat        # ask: "what's mailbox ps say?"
# Terminal 2
hermes profile install ./template --name beta-sh --alias --force -y
bash scripts/setup.sh
hermes -p beta-sh chat         # ask: "broadcast 'hello' to the board"
```

> **First-session caveat:** Hermes loads `<profile>/.env` into `os.environ` at
> gateway start. If you run `hermes chat` on a fresh install without first
> running setup, `first_run.sh` writes `.env` *after* the env is already loaded,
> so the FIRST session's mailbox hook falls back to the cwd-derived board.
> Subsequent sessions work. **Canonical path: run `bash scripts/setup.sh` before
> the first `hermes chat`.** The `first_run.sh` auto-setup is a safety net, not
> the canonical path.

### Debugging cross-agent issues
```
cat <profile>/local/warroom-enroll.log     # per-bootstrap + session_start lines
cat <profile>/local/warroom-enroll.json     # resolved board/label/cli/socket/status
mailbox ps                                   # who the daemon thinks is present
warroom enroll --status                      # state + daemon reachability
```

Lanes (named work-units for dogpile coordination) are managed from the shell:
`mailbox claim-lane <lane>`, `mailbox release-lane <lane>`, `mailbox list-lanes`.

### Configuration reference
- `mailbox.board` — board to join (source of truth for routing).
- `mailbox.label` — how you appear on the board (defaults to the Hermes handle).
- `mailbox.mailbox_home` (optional) — blank = runtime default `~/.claude/mailbox`.
- `mailbox.socket_path` (optional) — blank = `<mailbox_home>/mailboxd.sock`.

## MCP servers
MCP servers are registered in `config.yaml` under a top-level `mcp_servers:` block —
there is **no separate `mcp.json`** in the profile root. Add servers as:
```yaml
mcp_servers:
  <<NAME>>:
    url: <<URL>>
    # transport / headers as needed
```

## Verified
End-to-end smoke against Hermes Agent v0.15.1 (2026-06-08):
- `hermes profile install <template> --name awr-smoke` populated the profile and
  renamed `.env.template` → `.env.EXAMPLE`.
- `scripts/setup.sh` (interactive) seeded `local/persona/`, wrote `local/agent.json`
  (handle `awr-smoke`), compiled `SOUL.md` (no unsubstituted `{{...}}`) and
  `~/.claude/agents/awr-smoke.md`, wrote `.env` at mode `0600`, and patched the
  sentinel-managed `war_room` block (`min_confidence: 75`).
- `hermes profile update awr-smoke` preserved the `local/` overlay (the user's
  persona edit + identity) while refreshing the shipped `persona/` skeleton.
- `hermes profile delete awr-smoke` torn down cleanly.

Confidence-gate Layer 2 end-to-end (2026-06-08, separate `awr-gate-smoke` profile):
- Plugin shipped at `<profile>/plugins/warroom-gate/` with all 7 `wg_*.py` modules
  and `plugin.yaml`.
- `hermes plugins list` discovered `warroom-gate 0.1.0` from `user` source;
  `hermes plugins enable warroom-gate` flipped it to `enabled`.
- Sentinel-managed `war_room` block carried `enabled: true`, `min_confidence: 75`,
  `enforce: true`, `show_confidence_badge: true` (T8 extension verified).
- Direct invocation of the `register()` callback with a fake `register_hook` ctx
  registered `transform_llm_output`; the callback then exercised all four
  decision branches against synthetic responses:
  - low-conf ungrounded claim → abstention with missing items listed
  - high-conf grounded claim → pass-through with confidence badge appended
  - claim text with NO envelope → fail-closed abstention (the critical case)
  - chatter combo → conservative classifier abstained (documented behavior)
- Audit log at `local/war_room/gate.log` was created at mode `0600`; recorded all
  four decisions with action / reason / conf / kind / sha — no secrets.

> Note: `template/.venv/` is a dev-only artifact (gitignored). Install from a clean
> checkout, or publish via `scripts/publish.sh` — a published distribution contains
> no `.venv`. Hermes rejects distributions containing symlinks.

## Known limitations
- `scripts/setup.sh --yes` is intended for re-runs after an initial interactive setup
  has saved answers to `local/.warroom-setup.json`. On a fresh install with no saved
  answers and no stdin, the headless path falls back to default identity ("warroom")
  rather than the installed profile name; tracked as a follow-up.
- Cross-agent runtime (feature C): without the `coordination/` mailbox runtime
  installed, enrollment fail-warns (`cli-not-found`) and war-room features are
  inert until you install it (see "Installing the mailbox runtime").
- A custom `MAILBOX_SOCKET` (or `MAILBOX_HOME`) segregates daemons: profiles only
  see each other if they share the same socket/home. Override deliberately.
- Lane claims are enforced on the cwd-derived repo board, not the named board —
  peers in different working directories see each other (`ps`/`send`/`inbox`) but
  do NOT see each other's lane claims. Same-repo peers get full lane enforcement.
- First-fire: Hermes does no `{{PROFILE_ROOT}}` substitution, so the shipped
  hook command is relative; `warroom setup` rewrites it to an absolute path. If
  your gateway doesn't run hooks from the profile cwd, run `warroom setup` once
  manually to self-heal the path.

## Sanitization
This is a public template — no employer/operator names, internal hostnames,
channel IDs, or secrets may land in it. Before shipping any change (especially
content copied from a personal profile), read [SANITIZATION.md](SANITIZATION.md)
and run the guard:
```sh
python3 scripts/sanitize_check.py template/ --name <employer> --name <you>
```
It fails on org artifacts that leak by shape (Slack/Discord IDs, internal
hostnames, vault paths, agent fingerprints) plus any names you pass.
