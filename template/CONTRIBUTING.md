# Contributing to the war-room template

Stdlib-only, Python >=3.9. No third-party runtime dependencies. Run the suite
with `make test` (which first runs the substrate drift guard) or directly with
`.venv/bin/python -m pytest -q`.

## Installer substrate (`scripts/installer/_substrate/`)

The interactive installer (`bash install.sh`) must run from a fresh clone
**before** any Hermes profile exists, so it cannot import `warroom_setup` at
start-up. Instead it ships **byte-identical copies** of the seven modules it
needs for the pre-install TUI:

```
render.py  prompts.py  state.py  selectables.py
validators.py  discord_walkthrough.py  slack_walkthrough.py
```

(`daemon_probe.py` is intentionally excluded -- the installer never probes the
daemon pre-install.)

### Golden rule: never hand-edit `_substrate/`

`_substrate/` is generated. If you change a substrate-source module under
`warroom_setup/`, refresh the copies:

```sh
bash scripts/installer/sync_substrate.sh
```

Then commit the refreshed `_substrate/` files alongside your change.

### Drift is enforced

* `tests/test_installer_substrate_no_drift.py` fails (via `filecmp`) if any
  vendored file diverges from its `warroom_setup/` original.
* `make test` runs `sync_substrate.sh --check` as a **pre-test hook**, so drift
  is caught before the suite even starts. CI runs `make test`.

If a PR touches `warroom_setup/render.py` (or any other substrate source) and
forgets to re-sync, both guards will fail with the exact file that drifted and
the command to fix it.

## Sanitization

Everything shipped must be employer-/operator-neutral. `make sanitize` (or
`python3 scripts/sanitize_check.py`) scans the tree for blocked shapes and
names. Examples in docs and tests use `alpha-sh` / `beta-sh` / `shared`.
