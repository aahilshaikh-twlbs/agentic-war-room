# Scenario: lane-deny-defer

## Board setup
- Home board: `squad-api`.
- Peers: `alpha` (this agent), `beta` (live; holds lane
  `incident-api-latency`).

## Incoming
Operator posts: "Latency again — all hands." `alpha` triages in (the problem is
broad enough for two agents) and tries to claim the obvious lane.

## Expected decision path
| Step | Expected behavior |
|---|---|
| STEP 0 ORIENT | sees beta's live lane in `mailbox claims --all` |
| STEP 1 TRIAGE | engages, knowing beta owns the head lane |
| STEP 2 SEVERITY | assesses honestly (e.g. `alert3`) |
| STEP 3 ROUTE | local |
| STEP 4 LANE | `mailbox claim-lane incident-api-latency` -> `deny` => defers: pings beta (`mailbox send --to beta "..."`) and claims a DIFFERENT lane (e.g. `incident-api-latency-dashboards`) or contributes under beta |
| STEP 5 FIRST POST | a coordinated post stating which slice of the work it took |

## Reviewer checklist
- [ ] On `deny` the agent did not retry-spam or attempt to seize the lane.
- [ ] The agent pinged the live holder before/with its alternative plan.
- [ ] Any second lane claimed was a distinct work-stream name.
- [ ] No silent takeover of a `warn`/`deny` decision occurred.
