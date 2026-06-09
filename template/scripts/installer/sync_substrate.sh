#!/usr/bin/env bash
# Maintainer tool: vendor the minimal TUI substrate the installer needs into
# _substrate/ as BYTE-IDENTICAL copies of template/warroom_setup/<f>.
#
# Why copy, not import: the installer must run from a fresh clone BEFORE any
# Hermes profile (and thus any importable warroom_setup package) exists. It
# therefore ships its own copies of the renderer, prompts, validators, and the
# two channel walkthroughs. Drift between the copy and the original is caught by
# template/tests/test_installer_substrate_no_drift.py and by `--check` here,
# which template/Makefile runs as a pre-test hook.
#
# Manifest excludes daemon_probe.py (C22) -- the installer never probes the
# daemon pre-install.
#
# Usage:
#   sync_substrate.sh            # refresh _substrate/ from warroom_setup
#   sync_substrate.sh --check    # exit 1 if any vendored file has drifted
set -euo pipefail

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"     # installer dir
TEMPLATE_DIR="$(cd -P "$HERE/../.." >/dev/null 2>&1 && pwd)"
SRC="$TEMPLATE_DIR/warroom_setup"
DST="$HERE/_substrate"

FILES=(
  render.py
  prompts.py
  state.py
  selectables.py
  validators.py
  discord_walkthrough.py
  slack_walkthrough.py
)

CHECK=0
if [ "${1:-}" = "--check" ]; then CHECK=1; fi

if [ "$CHECK" -eq 1 ]; then
  drift=0
  for f in "${FILES[@]}"; do
    if ! cmp -s "$SRC/$f" "$DST/$f" 2>/dev/null; then
      echo "substrate drift: _substrate/$f differs from warroom_setup/$f" >&2
      drift=1
    fi
  done
  if [ "$drift" -ne 0 ]; then
    echo "run: bash $HERE/sync_substrate.sh   # to refresh _substrate/" >&2
    exit 1
  fi
  echo "substrate: in sync (${#FILES[@]} files)"
  exit 0
fi

mkdir -p "$DST"
for f in "${FILES[@]}"; do
  cp "$SRC/$f" "$DST/$f"
done
# Ensure the package marker exists (NOT part of the byte-equality manifest).
if [ ! -f "$DST/__init__.py" ]; then
  printf '"""Vendored byte-identical copies of warroom_setup TUI substrate.\n\nDo not edit by hand. Run sync_substrate.sh to refresh from warroom_setup/.\n"""\n' > "$DST/__init__.py"
fi
echo "substrate: synced ${#FILES[@]} files into $DST"
