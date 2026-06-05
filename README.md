# Agentic War Room (AWR)

The **problem-solver 9000**: drop a problem into the war room and a swarm of
agents dogpiles it -- working in parallel, coordinating so they never overlap,
suffocating the issue until it's fixed.

## Layout

```
agentic-war-room/
└── coordination/        # the ambient coordination substrate (seeded from `mailbox`)
    ├── src/mailbox/     # daemon + engine + socket protocol (single-writer, race-free)
    ├── hooks/           # Claude Code lifecycle hooks (reference integration)
    ├── tests/           # full suite incl. test_engine_lanes.py
    └── docs/            # original mailbox design + contract
```

## Coordination model

Two orthogonal collision layers run on one board:

- **File claims** -- two agents never edit the same file. Auto-claimed on every
  write; live holder -> deny, stale holder -> warn+seize.
- **Lane claims** -- two agents never grab the same subtask when dogpiling.
  A lane is a named work-unit (e.g. `repro-and-trace`). Stored as a claim whose
  path is the URI `lane://<id>` -- no wildcards, never starts with `/`, so lanes
  and real file paths are **mutually invisible**. The entire conflict engine
  (deny/warn/seize/release/reload) works on lanes unchanged.

Lane API on the engine: `claim_lane`, `release_lane`, `list_lanes`
(registered as socket ops in `protocol.py`).

### The dogpile flow

```
problem drops -> orchestrator mints a board -> all agents auto-join
  agents self-claim LANES (no duplicate subtasks)
  agents edit FILES (no overwrites)
  findings broadcast as messages, injected into peers' context every tick
```

## Status

- [x] Coordination core (seeded from mailbox, 156 tests)
- [x] Lane claims for dogpile coordination (+12 tests, 168 total)
- [ ] Hermes integration layer (map mailbox's CC-hook shape onto the Hermes
      agent lifecycle: session init -> join, tool exec -> check_write,
      post-tool/inbound -> heartbeat + inbox inject, teardown -> leave)
- [ ] Orchestrator: problem intake -> board mint -> lane decomposition

## Dev

```sh
cd coordination
uv venv .venv && source .venv/bin/activate
uv pip install -e . pytest
python -m pytest -q
```

> The `coordination/` tree is seeded from `~/Documents/Code/mailbox` (the
> source-of-truth mailbox repo). Lane support was added here, not upstream.
