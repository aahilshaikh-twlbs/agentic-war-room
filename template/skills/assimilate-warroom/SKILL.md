---
name: assimilate-warroom
description: Wire this Hermes profile into a cross-agent war-room board. Trigger
  when the owner says "join the war room", "assimilate", "wire me into the war
  room", or asks to coordinate with another agent on a shared board.
---

# Skill: Assimilate Into the War Room

The owner of this profile wants to add war-room coordination capability without
disturbing its existing channel wiring, persona, hooks, plugins, or skills. You
will confirm scope, run the CLI, and tell them how to activate it.

## 1. Confirm scope
Ask the owner two things in one message:
- Board name (default: `default` — must match the board their peer is on).
- Label for this agent on the board (default: this profile's handle from
  `local/agent.json` if present, else the profile directory name).

## 2. Run the CLI
```
python -m warroom_setup assimilate "$CLAUDE_PROJECT_DIR" \
  --board <board> --label <label>
```
The CLI will:
- Detect this profile's shape (existing channels, hooks, plugins, persona).
- Print a pre-flight report of what it will create/modify, then ask to proceed.
- Walk through Discord setup ONLY if no `DISCORD_BOT_TOKEN` is already wired.
- Walk through Slack setup ONLY if no `SLACK_BOT_TOKEN` is already wired.
- Write walkthrough credentials to `.env` BEFORE enrolling, so a partial failure
  never strands a freshly-entered token.
- Patch the sentinel-managed `war_room:` + `mailbox:` blocks (never clobbers
  surrounding config; `enforce` is OFF by default — pass `--enforce` to opt in).
- Append a persona rule teaching you to `mailbox claim-lane` before edits.
- Run enrollment so the next session joins the board.

Useful flags:
- `--dry-run` — report only; writes nothing.
- `--no-walkthrough` — skip Discord/Slack setup even if creds are missing
  (war-room messaging will be CLI-only until you add tokens).
- `--reconfigure` — force a rewrite if the profile was already assimilated.
- `--yes` — headless; requires `--no-walkthrough` (or pre-set creds).

## 3. After it runs
Restart this Claude Code session so the new `MAILBOX_BOARD` / `MAILBOX_LABEL`
env vars load (Hermes reads `<profile>/.env` at session start, not on change).
Then run `mailbox ps`. If it shows empty, the daemon may need a manual `mailbox`
invocation to spawn — run it once and re-check.

## Exit codes
- `0` — assimilated (or dry-run reported cleanly).
- `1` — mailbox CLI not found; config blocks are written but the runtime is
  inactive. Install the mailbox runtime (see `template/README.md`) and re-run
  `warroom enroll`.
- `2` — already assimilated; pass `--reconfigure` to force a rewrite.
- `3` — the path is not a Hermes profile (no `config.yaml`).
- `4` — owner aborted, a walkthrough/label validation failed, or `config.yaml`
  carries a war-room sentinel block with no enroll state (manual review).

## Failure modes
- "already assimilated" — pass `--reconfigure`.
- "war-room template profile" — this profile was built from the template; use
  `warroom setup` / `warroom enroll --reconfigure` instead of assimilate.
- A walkthrough field won't validate — re-run; nothing is written until you
  confirm the pre-flight report.
