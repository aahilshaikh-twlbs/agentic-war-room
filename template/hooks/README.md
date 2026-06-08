# Hooks

Lifecycle scripts the gateway invokes at well-known points. A hook is an
executable in this directory; the gateway calls it by convention and passes
context via environment variables. Hooks should be idempotent and fail open
(exit 0 even on internal error) so a bad hook never wedges the agent.

## Contracts

### `on_session_start`
- **When:** once when a gateway session starts.
- **Shipped example:** `first_run.sh` — runs `warroom setup --yes` exactly once,
  guarded by a `local/.setup-done` sentinel so it never re-runs.
- **Use for:** one-time provisioning, sentinel-guarded first-run setup, warming caches.
- **Must:** be safe to call on every start (guard with a sentinel); fail open.

### `pre_tool_use`
- **When:** immediately before the agent executes a tool call.
- **Context:** the proposed tool name + arguments (via env / stdin per the
  gateway's hook protocol).
- **Use for:** policy checks, claim/lane coordination before a write, redaction.
- **Must:** be fast (it is on the hot path) and fail open unless you are
  intentionally enforcing a deny.

### `post_tool_use`
- **When:** immediately after a tool call returns.
- **Context:** the tool name + result.
- **Use for:** audit logging, releasing claims, post-write notifications.
- **Must:** never raise; treat logging failures as non-fatal.

## Notes
- Confidence-gating of model OUTPUT is handled by the `warroom-gate` plugin
  (`plugins/warroom-gate/`), not by a hook — plugins can transform LLM output;
  hooks bracket tool execution.
- Keep secrets out of hook output and logs. Hook logs in this profile are written
  under `local/` (user-owned, gitignored).
