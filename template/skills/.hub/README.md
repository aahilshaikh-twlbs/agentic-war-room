# Skills hub state

This directory holds the skills-hub plumbing for the profile.

## `taps.json`
Registers **extra** custom GitHub skill sources (taps). The official skills-hub
tap is built in (it lives in the runtime's `DEFAULT_TAPS`), so it does NOT need to
be listed here — this file is for additional sources only. The template ships it
empty:
```json
{ "taps": [] }
```
To add a custom tap, append an entry under `"taps"` per your runtime's tap schema
(typically a name + GitHub `owner/repo`).

## `../.bundled_manifest` (runtime-managed — do not hand-edit)
`skills/.bundled_manifest` is a curator-maintained integrity cache written in
`name:hash` lines. The runtime computes it from the bundled-skills directory; a
skill listed there but absent from `skills/` is treated as *user-deleted* and is
not re-added. The template therefore ships it **empty** — listing skills that are
not physically present would suppress them.

## Recommended starter skills (install via the hub, not pre-bundled)
These generic skills are a good starting set; install them through the hub rather
than committing their bodies into the template:
- `software-development/writing-plans`
- `software-development/test-driven-development`
- `dogfood`
