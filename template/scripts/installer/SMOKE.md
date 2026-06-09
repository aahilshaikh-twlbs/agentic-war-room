# Installer smoke test (manual)

Operator-driven end-to-end check that the interactive installer brings two
agents up and lands them on the same coordination board. Uses neutral handles
`alpha-sh` / `beta-sh` and board `shared` throughout. ~10 minutes.

Prereq: a fresh clone of this repo, `hermes` >=0.12 on PATH, and (optionally) a
Discord bot token if you want to exercise the channel walkthrough. The smoke
recipe works channel-less too (choose `none` at the channels step).

## 1. Pre-flight

```sh
cd <repo>
bash install.sh            # the title + pre-flight panel must show all [ok]
```

If any line is `[fail]`, fix it (the hint says how) before continuing. Expected
checks: Python, `hermes` on PATH, `hermes` version, profile-install surface,
plugins-enable surface, POSIX terminal, writable `~/.hermes/profiles/`, substrate
import. (See `docs/installer-preflight.md`.)

## 2. Install the first agent (`alpha-sh`)

Run `bash install.sh` and answer:

- Source: accept the default (this repo's `template/`).
- Profile name: `alpha-sh`
- Channels: `discord` (then complete the walkthrough) or `none`.
- Anthropic key: paste a key (masked) or press Enter to skip.
- Identity: agent name `alpha-sh`, display name `Alpha`, handle `alpha-sh`.
- Model: `opus`.
- Board / label: `shared` / `alpha-sh`.
- Confirm screen lists `~/.claude/settings.json (mailbox hooks)` — proceed.

Watch the 5 stage lines all reach `ok` (Stage 2 `plugins enable` may `warn` if
`warroom-gate` is already enabled — that is advisory and does not abort). Stage
order: 1 install → 2 plugins enable → 3 .env + identity → 4 patch war_room +
mailbox → 5 enroll. Note the `Total time: Ns` summary.

## 3. Install the second agent (`beta-sh`)

Repeat step 2 with profile name `beta-sh`, display name `Beta`, label `beta-sh`,
board `shared`.

## 4. Confirm both are wired

```sh
cat ~/.hermes/profiles/alpha-sh/local/install.log    # 5 stages, no secret values
cat ~/.hermes/profiles/alpha-sh/config.yaml          # war_room: + mailbox: blocks, board: shared
hermes -p alpha-sh exec warroom enroll --status      # informational

# Acceptance: EXACTLY one sentinel-bounded war_room: and one mailbox: (no dups).
grep -c '^war_room:'        ~/.hermes/profiles/alpha-sh/config.yaml   # -> 1
grep -c '^mailbox:'         ~/.hermes/profiles/alpha-sh/config.yaml   # -> 1
grep -c 'warroom-managed'   ~/.hermes/profiles/alpha-sh/config.yaml   # -> 2 (begin+end)
grep -c 'warroom-mailbox'   ~/.hermes/profiles/alpha-sh/config.yaml   # -> 2 (begin+end)
```

`install.log` must contain NO token/key values (only stage names + the install
command lines). The `grep -c` counts above are the structural acceptance bar:
Hermes' `plugins enable` re-emits config.yaml (stripping comments), so the
installer runs it FIRST (Stage 2) and re-writes the sentinel blocks afterward
(Stage 4) — duplicate `war_room:`/`mailbox:` keys mean that ordering regressed.

## 5. Verify they meet on board `shared`

Start each agent's gateway (or trigger a chat session so the SessionStart hook
runs), then:

```sh
mailbox ps                 # both alpha-sh and beta-sh appear on board `shared`
```

Both labels on the same board = success.

## 6. Uninstall round-trip

```sh
bash install.sh --uninstall beta-sh    # confirm if it reports user data
```

It runs `hermes profile delete beta-sh -y`, cleans the `~/.awr` sidecar, and
warns that `~/.claude/settings.json` mailbox hooks are NOT auto-removed. Confirm
`beta-sh` is gone (`hermes profile list`) and `alpha-sh` is untouched.

Record completion in the PR description.
