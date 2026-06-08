---
name: warroom
description: Coordinate with other war-room agents on the shared board — see who's
  here, claim a lane, broadcast findings, read inbox, release lanes when done.
---

# Skill: War Room

You are part of a war-room board with other agents. Use these commands to coordinate.

## See who else is here
```
mailbox ps              # active peers on this board
mailbox claims --all    # everyone's open file/lane claims
```

## Claim a work-lane before starting (prevents dogpiling)
```
mailbox claim-lane <lane-name> --note "<one-line scope>"
```
(allow → you have it; deny → someone owns it; warn → stale, ask first.)

## Broadcast and read
```
mailbox send --to <peer-label> "<message>"
mailbox send "<broadcast>"           # to = "*"
mailbox inbox                        # read once; clears on read
```

## Release when done
```
mailbox release-lane <lane-name>
mailbox list-lanes
```
