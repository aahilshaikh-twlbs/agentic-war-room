#!/usr/bin/env bash
# on_session_start hook: run setup once, then never again (sentinel-guarded).
set -euo pipefail
PROFILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SENTINEL="$PROFILE_ROOT/local/.setup-done"
[ -f "$SENTINEL" ] && exit 0
mkdir -p "$PROFILE_ROOT/local"
# Headless: replay defaults (the interactive wizard cannot run inside the gateway).
PYTHONPATH="$PROFILE_ROOT" python3 -m warroom_setup setup --yes >>"$PROFILE_ROOT/local/setup.log" 2>&1 || true
touch "$SENTINEL"
exit 0
