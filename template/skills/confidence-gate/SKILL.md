---
name: confidence-gate
description: War-room anti-hallucination protocol. Every claim posted to a war-room channel must be grounded in evidence and carry a confidence; below the board threshold, abstain and state the gap instead of guessing.
metadata:
  hermes:
    tags: [coordination, war-room, safety]
---

# Skill: Confidence Gate (war room, not chat room)

A war room must not contain hallucinated answers. Before you post information, an
answer, or any factual claim to a war-room channel:

1. GROUND IT. Each claim must trace to evidence you actually have this session: a
   tool result, a file you read, a retrieved source, or a cited message.
   Assertions with no such backing are ungrounded.
2. SCORE IT (from grounding, not vibes). Confidence reflects how much of the claim
   is grounded and how directly. Well-sourced -> high; inference beyond your
   evidence -> low; guess -> ~0. Do not inflate to suppress uncertainty.
3. GATE IT against the board threshold (`war_room.min_confidence`, default 75%):
   - At/above threshold: post the answer + the envelope below.
   - Below threshold: DO NOT post the claim. Post the gap instead:
     "Not confident enough to answer (<n>%). To verify I'd need: <what's missing>."
4. ENVELOPE. End a claim-bearing message with the canonical footer the gate reads:
       ⟦conf=0.82 grounded=tool,file missing=none⟧
   conf in [0,1]; grounded = evidence kinds used; missing = what would raise it.
   Chatter (greetings, acks, clarifying questions) needs no envelope and is not gated.

Higher severity = stricter bar: treat Alert 1/2 boards as demanding independent
verification, not just self-scoring. Abstaining loudly is correct war-room
behavior; confident wrongness is not.

Federation note: on a federated board tree, `mailbox escalate "<msg>"` /
`mailbox broadcast "<msg>"` change *visibility only* (ancestors / descendants
of your home board see the post). An escalated claim is still a claim: it
keeps its confidence envelope and gates exactly like a local post. Never
escalate to dodge the gate — abstain loudly instead.

## Severity (DEFCON) and the independent verifier

Tag a claim's severity in the envelope's optional trailing `sev=` field:

    ⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧

- `sev` is one of `alert1` (highest) > `alert2` > `alert3` > `default`. Omit it
  for ordinary claims (treated as `default`). Tag honestly: a higher severity
  only raises your own bar, it never lowers it.
- Higher severity demands a higher confidence floor (`war_room.severity_thresholds`).
  A claim that clears the baseline but not its alert floor is held back — abstain
  loudly and state the gap.
- At/above `war_room.require_verifier_at` (default top tier only), clearing the
  floor is necessary but not sufficient: the gate asks a second agent (the
  configured `verifier_label`) to independently confirm before your claim posts.
  If no signed verdict arrives in time, the gate holds the claim back. This is
  correct — a top-severity claim with no second signoff does not post.

You never run the handshake by hand; the gate does it. Your job is to tag `sev=`
honestly and ground the claim well enough that an adversarial second agent can
confirm it.

## Auto-escalation is the orchestrator's job, not the gate's

The confidence gate annotates severity (in the audit and your envelope) but does
NOT escalate. When your assessed severity is at/above `war_room.escalate_at`, the
`/warroom` orchestrator performs the `mailbox escalate "<finding>"` post so the
finding becomes visible up the board tree. The gate stays a pure transform with
exactly one outbound message — the verifier request — and never double-posts.
