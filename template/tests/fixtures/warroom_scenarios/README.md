# Golden intake scenarios — reviewer checklists (not auto-graded)

These five fixtures are the L1 orchestrator's scenario harness: golden intake
transcripts a human reviewer walks an agent through after any change to
`template/skills/warroom/SKILL.md`. They are NOT auto-graded in CI — the suite
(`test_warroom_scenarios.py`) lints only their shape; the judgment "would a
smart agent do the right thing?" is reviewer-run by design (L1 spec, Open
questions #1). Revisit auto-grading only if protocol drift becomes a real
problem.

How to run a review:

1. Open a war-room session whose profile loads the `warroom` bundle.
2. Recreate the scenario's "Board setup" (boards, peers, lanes) with the
   mailbox CLI.
3. Paste the "Incoming" message and invoke `/warroom`.
4. Walk the "Expected decision path" table top to bottom and tick every
   "Reviewer checklist" box. Any unticked box is a protocol regression: fix the
   skill text, not the scenario.

All labels are generic (`alpha`, `beta`, `squad-api`, `team-platform`, `org`).
Never paste real operator handles or employer names into these files —
`schema.BLOCKED_VALUES_REGEX` is enforced over every fixture by the test suite
(sanitize_check.py does not scan tests/).
