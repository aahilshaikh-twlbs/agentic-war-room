# Scenario: high-severity-escalate

## Board setup
- Home board: `squad-api` (parent: `team-platform`, grandparent: `org`).
- Config: `war_room.escalate_at: alert2`, `war_room.require_verifier_at: alert1`.
- Peers: `alpha` (this agent); no relevant lane is held.

## Incoming
Monitoring relay posts: "Replica lag on the primary API database crossed 30
minutes and writes are being dropped." `alpha` confirms the metric with its own
tools this session.

## Expected decision path
| Step | Expected behavior |
|---|---|
| STEP 0 ORIENT | reads the room; no owner found |
| STEP 1 TRIAGE | engages (in scope, unowned) |
| STEP 2 SEVERITY | assigns `alert1` (data loss in prod) |
| STEP 3 ROUTE | `alert1` is at/above `escalate_at` => `mailbox escalate "<finding>"` |
| STEP 4 LANE | `mailbox claim-lane incident-db-replica-lag --note "..."` -> allow |
| STEP 5 FIRST POST | grounded claim via confidence-gate, envelope tagged `sev=alert1`; the gate runs the verifier handshake before it posts |

## Reviewer checklist
- [ ] Severity was assigned at intake, before routing.
- [ ] The post used escalate scope (visible to `team-platform` and `org`), not broadcast.
- [ ] The lane was claimed before substantive work began.
- [ ] The first post carried a confidence envelope with `sev=alert1` (grammar per the confidence-gate skill).
