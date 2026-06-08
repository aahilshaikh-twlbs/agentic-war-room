# Scripts

Operator-facing entry points for this profile. Run them from the profile root
(`~/.hermes/profiles/<name>`).

## Shipped

### `setup.sh`
The personalization wizard. Wraps `python3 -m warroom_setup setup`.
- `bash scripts/setup.sh` — interactive wizard (toggles + prompts).
- `bash scripts/setup.sh --yes` — headless: replay saved answers / defaults.
- `bash scripts/setup.sh --reconfigure` — re-run the picker.
- `bash scripts/setup.sh --sync` — only recompile `SOUL.md` + the Claude head
  after editing `local/persona/`.

### `publish.sh`
Produces a clean, installable distribution from this template (strips the dev
`.venv/`, validates no symlinks, etc.) so it can be installed from a git URL.

## Planned (land in later PRs)

### `install.sh` (feature B — interactive installer)
A guided installer that wraps `hermes profile install <SOURCE> --name <NAME>
--alias --force -y`, captures stdout+stderr, treats any nonzero exit as failure,
and detects a pre-existing non-distribution profile before overwriting.

### `assimilate.sh` (feature A — assimilate)
Imports/sanitizes content from an existing personal profile into this template
shape, applying the `SANITIZATION.md` blocklist so no employer/operator strings
leak into a published distribution.

## Conventions
- Scripts must be POSIX-`bash`, `set -euo pipefail`, and run from any cwd
  (resolve their own dir).
- Never echo secrets. Never `git add` generated artifacts under `local/`.
