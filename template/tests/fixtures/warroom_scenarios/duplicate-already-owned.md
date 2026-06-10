# Scenario: duplicate-already-owned

## Board setup
- Home board: `squad-api` (parent: `team-platform`, grandparent: `org`).
- Peers: `alpha` (this agent), `beta` (live; holds lane
  `incident-api-latency`, note "bisecting the latency regression").

## Incoming
Operator posts: "API p99 latency doubled since the 14:00 deploy — who's on it?"

## Expected decision path
| Step | Expected behavior |
|---|---|
| STEP 0 ORIENT | runs `mailbox ps`, `mailbox claims --all`, `mailbox inbox`; sees beta's lane |
| STEP 1 TRIAGE | recognizes the problem is owned; reinforces or defers — does NOT re-claim |
| STEP 2 SEVERITY | not a routing driver here (no new claim is being made) |
| STEP 3 ROUTE | directs a clarifying/reinforcing message at the owner: `mailbox send --to beta "..."` |
| STEP 4 LANE | does NOT claim `incident-api-latency` |
| STEP 5 FIRST POST | a question or reinforcement, not a duplicate claim |

## Reviewer checklist
- [ ] Agent read the room (ps/claims/inbox) before posting anything.
- [ ] Agent did not claim the lane beta holds.
- [ ] Agent's first message went to beta (`--to beta`), not a broadcast.
- [ ] No confidence envelope was fabricated for a non-claim message.
