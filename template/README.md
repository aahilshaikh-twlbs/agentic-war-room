# War-Room Agent (Hermes profile distribution)

A personalizable Hermes agent for the Agentic War Room: Discord + Slack in, a
dual-runtime persona (Hermes `SOUL.md` + a Claude Code head), and a stub that
joins an AWR coordination board.

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

## Provisioning the channels
- **Discord:** create an app, enable **Message Content** + **Server Members**
  intents, set `DISCORD_BOT_TOKEN` + `DISCORD_ALLOWED_USERS` in `.env`, invite the bot.
- **Slack:** Socket Mode app; set `SLACK_BOT_TOKEN` (xoxb-) + `SLACK_APP_TOKEN` (xapp-).

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
