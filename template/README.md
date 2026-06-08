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
