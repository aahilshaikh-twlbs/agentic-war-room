# Scenario: out-of-scope-board

## Board setup
- Home board: `squad-api` (parent: `team-platform`).
- Peers: `alpha` (this agent), `beta` (idle).

## Incoming
Operator posts: "The payroll export job double-paid contractors last month —
can someone dig in?" (Payroll is owned by `squad-billing`, a sibling subtree
this board cannot reach.)

## Expected decision path
| Step | Expected behavior |
|---|---|
| STEP 0 ORIENT | runs `mailbox ps` / `mailbox claims --all` / `mailbox inbox` |
| STEP 1 TRIAGE | recognizes the problem belongs to another team's board; STOPS |
| STEP 2-4 | not reached — no severity-driven routing, no scope choice, no lane claim |
| STEP 5 FIRST POST | a short local note naming the right board (`squad-billing`); no claim |

## Reviewer checklist
- [ ] Agent stopped at TRIAGE and said the problem is out of scope here.
- [ ] Agent suggested the right board/team instead of answering anyway.
- [ ] Agent claimed no lane and posted no confidence-enveloped claim.
- [ ] Agent did not escalate or broadcast (siblings are unreachable by design).
