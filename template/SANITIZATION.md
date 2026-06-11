# Sanitization

**How we keep any employer (and operator) out of this public template.**

This template ships publicly. No employer name, no operator/colleague names, no
internal hostnames, no specific channel/user IDs, no project codenames, and no
secrets may land in it. Persona content ships as `<<FILL-IN: ...>>` markers;
channel references ship as `<CHANNEL_ID>` placeholders.

The CI guard `scripts/sanitize_check.py` enforces the shape-based rules below and
accepts a configurable name blocklist:

```sh
python3 scripts/sanitize_check.py template/            # shape checks only
python3 scripts/sanitize_check.py template/ --name acme --name jane
```

Exit 0 = clean; exit 1 = violations (printed as `path:line`).

## Value patterns CI fails on (shape-based)

These are matched by `schema.BLOCKED_VALUES_REGEX` and need no literal names:

| Pattern | Catches |
|---|---|
| `U0[A-Z0-9]{8,}` | Slack user IDs |
| `T0[A-Z0-9]{8,}` | Slack team IDs |
| `\b\d{17,20}\b` | Discord/Slack snowflake channel/guild IDs |
| `<slug>-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | agent-fingerprint UUIDs |
| `[A-Za-z0-9-]+\.(internal\|corp\|local\|lan)` | non-public hostnames |
| `/Users/<name>/Documents/` | vault-style absolute home paths |

Matched separately (configurable, not hardcoded — you pass them in):
- The employer brand name (case-insensitive substring).
- Operator / colleague / manager handles and real names.

## Key names to scrub before shipping

In `config.yaml` and friends, blank or remove these (they carry org-specific
values): `slack.extra.allow_admin_from`, `slack.extra.group_allow_admin_from`,
`slack.allowed_channels`, `discord.allowed_channels`, `telegram.allowed_chats`,
`*.channel_prompts`, `discord.dm_role_auth_guild`, `discord.server_actions`,
`dashboard.oauth.client_id`, `dashboard.oauth.portal_url`, `dashboard.public_url`,
`timezone`, any `auxiliary.*.api_key` / `auxiliary.*.base_url`,
`kanban.orchestrator_profile`, `kanban.default_assignee`, `delegation.api_key`,
`delegation.base_url`.

## Files to drop entirely (never ship)

`auth.json`, `.env`, `.env.bak-*`, `state.db*`, `sessions/**`, `logs/**`,
`cache/**`, `*_cache/**`, `home/**`, `lsp/**`, `models_dev_cache.json`,
`.skills_prompt_snapshot.json`, `*.lock`, `*.pid`, `cron/output/**`,
`skills/.usage.json`, `skills/.curator_state`, `skills/.hub/audit.log`,
`skills/.hub/index-cache/**`, `skills/.hub/quarantine/**`,
`slack-manifest-current.json`, `slack-manifest-merged.json`.

## Pre-brief pack docs (`shared/prebrief/**`)

The pre-brief pack doc (`shared/prebrief/<pack>.md`) is injected verbatim into
the always-loaded `SOUL.md` and the Claude head agent file via persona-sync, so
it is a public, distribution-owned surface. `sanitize_check.py` already scans it
(`shared/` is not in `EXCLUDE_DIRS` and `.md` is a scanned suffix), and the test
`test_warroom_bundle.py::test_sanitize_check_scans_shared_prebrief` locks that
in. No employer/operator name, channel ID, or secret may appear in a pack doc.

## Skills folders hard-excluded

- **Any org-namespaced skill directory** — e.g. `skills/<your-employer>/**`.
  These are employer-specific by construction; never auto-copy them.
- **Any employer-initials-prefixed skill namespace** — e.g. `skills/<org>/<org>-*`.
  The naming convention itself encodes the employer.

Ship only generic, functional category names (`software-development/`,
`productivity/`, `research/`, `dogfood/`, ...). The `<<FILL-IN>>` persona and the
empty `channel_directory.json` / `memories/*.md` skeletons are the safe defaults.

## Cross-agent routing (`mailbox:` block)

- `MAILBOX_BOARD` / `MAILBOX_LABEL` are **non-secret routing**, never tokens.
  They never belong in `.env` or in any vault — the `mailbox:` block in
  `config.yaml` is the single source of truth.
- `mailbox.label` defaults to the Hermes handle. Use a generic handle for public
  demos; a real-name handle reveals operator identity.
- The SHIPPED `template/config.yaml` MUST have `label: ""` in the `mailbox:`
  block. The wizard populates it in the installed `<profile>/config.yaml` only.

## Interactive installer (`scripts/installer/`)

The installer ships in the public template, so the same rules apply to it:

- `sanitize_check.py` walks `scripts/` by default (it is **not** in
  `EXCLUDE_DIRS`), so every installer module, the vendored `_substrate/` copies,
  and `SMOKE.md` are scanned on each run. Examples in installer source, tests,
  and `SMOKE.md` use the neutral handles `alpha-sh` / `beta-sh` / board `shared`.
- **`install.log` carries no secrets.** The orchestrator logs stage names and the
  install/enable command lines (which contain only source + profile name), never
  token or key values. Stage 2 logs a count of `.env` keys, not their values.
- **The resume sidecar (`~/.awr/install-state.json`) excludes secrets.** Keys
  whose name contains `token` / `key` / `secret` / `password` / `cred` are
  stripped before write; on resume, channel tokens are re-prompted (never read
  from disk).
- **Installer imports are restricted to stdlib + the vendored `_substrate.*`.**
  The bundled `warroom_setup` is imported only lazily, post-install, from the
  *installed profile* (the in-process orchestration step) — never at module load.

## Persona content to strip on auto-copy

- `SOUL.md` sections matching `^## With ` (peer-by-name sections).
- The `SOUL.md` "Agent fingerprint:" line.
- Any "DO NOT EDIT. Generated from vault ..." banner.
- `memories/USER.md` and `memories/MEMORY.md` contents entirely (operator-private).

## Instructions for contributors copying from a personal profile

1. Never copy `auth.json`, `.env*`, `state.db*`, `sessions/`, caches, or locks.
2. Replace every persona line with a `<<FILL-IN: ...>>` marker — no real content.
3. Blank the key names listed above; ship channel directories empty.
4. Drop any org-namespaced skill directory; keep only generic categories.
5. Run `python3 scripts/sanitize_check.py template/ --name <employer> --name <you>`
   and fix every reported line before opening a PR.
