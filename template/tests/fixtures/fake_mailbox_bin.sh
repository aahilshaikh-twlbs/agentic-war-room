#!/usr/bin/env bash
# Test fixture: a stand-in for the `mailbox` CLI. Prints its argv so discovery
# and status tests can assert it was the binary that got resolved. Does NOT
# spawn a daemon or touch any socket.
echo "fake-mailbox $*"
exit 0
