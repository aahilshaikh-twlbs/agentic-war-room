#!/usr/bin/env bash
# Run the war-room setup wizard from inside an installed profile.
# Usage: bash scripts/setup.sh [--yes|--reconfigure|--sync]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # profile root
cd "$HERE"
PYTHONPATH="$HERE" exec python3 -m warroom_setup setup "$@"
