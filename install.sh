#!/usr/bin/env bash
# Repo-root convenience shim -> template/install.sh (the real launcher).
# A real file, not a symlink (A4/C5/K19), so it survives archive/export.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
exec bash "$ROOT/template/install.sh" "$@"
