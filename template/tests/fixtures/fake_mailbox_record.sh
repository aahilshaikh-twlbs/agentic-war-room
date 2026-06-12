#!/usr/bin/env bash
# Test fixture: a recording stand-in for the `mailbox` CLI. Appends each
# invocation's argv to $FAKE_MAILBOX_LOG (if set) and exits with
# $FAKE_MAILBOX_EXIT (default 0). Never spawns a daemon, never opens a socket.
if [ -n "${FAKE_MAILBOX_LOG:-}" ]; then
  echo "$*" >> "$FAKE_MAILBOX_LOG"
fi
exit "${FAKE_MAILBOX_EXIT:-0}"
