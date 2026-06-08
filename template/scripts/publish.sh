#!/usr/bin/env bash
# Publish template/ as the ROOT of a separate git repo so `hermes profile install
# <git-url>` works (Hermes requires distribution.yaml at the clone root; it does
# NOT support subdirectories — verified in profile_distribution.py:407-416).
#
# Usage: scripts/publish.sh <dist-remote-url> [branch]
#   e.g. scripts/publish.sh git@github.com:you/war-room-agent-dist.git main
set -euo pipefail
REMOTE="${1:?usage: publish.sh <dist-remote-url> [branch]}"
BRANCH="${2:-main}"
# Run from the AWR repo root (the dir that CONTAINS template/).
AWR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$AWR_ROOT"
test -f template/distribution.yaml || { echo "template/distribution.yaml not found"; exit 1; }
# Produce a synthetic branch whose root IS template/.
git subtree split --prefix=template -b _dist_publish
git push "$REMOTE" "_dist_publish:${BRANCH}" --force
git branch -D _dist_publish
echo "Published template/ to ${REMOTE} (${BRANCH}). Install with:"
echo "  hermes profile install ${REMOTE%.git} --name war-room-agent"
