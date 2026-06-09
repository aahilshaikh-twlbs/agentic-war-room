#!/usr/bin/env bash
# AWR interactive installer launcher (the real launcher; ships in the
# distribution). Resolves python3, puts the installer package directory on
# PYTHONPATH so its flat modules + the vendored _substrate package import, then
# execs the TUI module. Override the interpreter with AWR_PYTHON if needed.
set -euo pipefail

# Resolve this script's own directory (template/), following symlinks.
SELF="${BASH_SOURCE[0]}"
while [ -h "$SELF" ]; do
  DIR="$(cd -P "$(dirname "$SELF")" >/dev/null 2>&1 && pwd)"
  SELF="$(readlink "$SELF")"
  case "$SELF" in
    /*) ;;
    *) SELF="$DIR/$SELF" ;;
  esac
done
TEMPLATE_DIR="$(cd -P "$(dirname "$SELF")" >/dev/null 2>&1 && pwd)"
INSTALLER_DIR="$TEMPLATE_DIR/scripts/installer"

PYTHON="${AWR_PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: python3 not found on PATH (set AWR_PYTHON to override)" >&2
  exit 1
fi

# Installer dir goes FIRST so its modules win; any caller PYTHONPATH is kept.
export PYTHONPATH="$INSTALLER_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$INSTALLER_DIR"
exec "$PYTHON" -m awr_install "$@"
