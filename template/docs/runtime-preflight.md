# Runtime pre-flight (Feature C / T0)

Date resolved: 2026-06-08. Status: all three pre-flights resolved.

This document locks the runtime/hook taxonomy that Feature C builds on. Three
empirical questions had to be answered before any production code was written,
because the base plan conflated two different hook lifecycles (Hermes gateway
hooks vs. Claude Code harness hooks) running in different processes.

Method note: pre-flight #1 is resolved by reading Hermes source on disk
(option b). Pre-flights #2 and #3 are resolved by reading the authoritative
Claude Code hooks documentation plus the on-disk mailbox hook source
(option b) — option (a), registering live test hooks in `~/.claude/settings.json`,
was deliberately avoided because a Claude Code session was running at
resolution time and live hook registration would have perturbed it.

---

## Pre-flight #1 — Hermes `hooks.<event>` accepted shape

**Question:** What shape must `config.yaml`'s `hooks:` block take so Hermes
actually fires the hook (vs. silently warn-skipping it)?

**Resolution: option (b) — read `~/.hermes/hermes-agent/agent/shell_hooks.py`.**

`_parse_hooks_block` (line 242) and `_parse_single_entry` (line 290) require:

- `hooks_cfg` must be a `dict`; otherwise `[]` is returned (no hooks). (L250-251)
- Each event's value (`entries`) must be a `list`; a non-list value is
  warn-skipped: `"hooks.%s must be a list of hook definitions; got %s"`. (L275-280)
- Each list entry (`raw`) must be a `dict` (mapping); a non-dict is warn-skipped:
  `"hooks.%s[%d] must be a mapping with a 'command' key; got %s"`. (L293-298)
- The mapping must carry a non-empty string `command`; otherwise warn-skipped:
  `"hooks.%s[%d] is missing a non-empty 'command' field"`. (L300-306)
- `matcher` is optional and only honored for `pre_tool_call` / `post_tool_call`. (L308-323)
- `timeout` defaults to `DEFAULT_TIMEOUT_SECONDS`, clamped to `[1, MAX_TIMEOUT_SECONDS]`. (L325-347)

**Verdict:** The accepted shape is a **list of mappings**, each with a `command`
key:

```yaml
hooks:
  on_session_start:
    - command: "bash <abs-path>/hooks/first_run.sh"
```

The template currently ships `hooks.on_session_start: bash hooks/first_run.sh`
(a scalar string), which `_parse_hooks_block` rejects at the "must be a list"
gate (L275-280) — so **first_run.sh never fires today**. **T0.5 migrates this.**

---

## Pre-flight #2 — Claude Code harness SessionStart hook ordering & registration

**Question:** When multiple `SessionStart` hooks are registered in
`~/.claude/settings.json`, do they execute in registration/array order, and can
the template's hook reliably run *before* mailbox's hook?

**Resolution: option (b) — authoritative Claude Code hooks documentation.**

Source: <https://code.claude.com/docs/en/hooks> (fetched 2026-06-08; the
`docs.anthropic.com/en/docs/claude-code/hooks` URL 301-redirects here).

Direct documentation statement:

> "All matching hooks run in parallel, and identical handlers are deduplicated
> automatically."

The docs do **not** guarantee that separately-registered `SessionStart` hooks
execute in array order. The general execution model is **parallel**, not
sequenced. Registration order is therefore **not a reliable mechanism** for
forcing the template's hook to complete before mailbox's hook.

**Verdict:** Ordering by array position is NOT guaranteed. Combined with
pre-flight #3 below, this means the "register our hook at index 0 so it runs
first and seeds env for mailbox's hook" design is **not viable**.

Live registration of two probe hooks (option a) was intentionally not run
because a Claude Code session was active and would have been affected.

---

## Pre-flight #3 — `CLAUDE_ENV_FILE` write visibility between consecutive SessionStart hooks

**Question (load-bearing):** If SessionStart hook A appends
`export MAILBOX_BOARD=shared` to `$CLAUDE_ENV_FILE`, does a *sibling* SessionStart
hook B (e.g. mailbox's `session_start.py`) see `MAILBOX_BOARD` in `os.environ`
during the **same** SessionStart event?

**Resolution: option (b) — authoritative Claude Code hooks documentation +
on-disk mailbox hook source.**

Direct documentation statements (same source as #2):

> "SessionStart hooks have access to the `CLAUDE_ENV_FILE` environment variable,
> which provides a file path where you can persist environment variables for
> subsequent Bash commands."

> "Any variables written to this file will be available in all subsequent Bash
> commands that Claude Code executes during the session."

The applied scope is explicitly **"subsequent Bash commands ... during the
session"** — i.e. the env file is sourced into the environment used for later
tool/Bash invocations, AFTER all SessionStart hooks complete. It is **not**
re-read into a sibling SessionStart hook's `os.environ` mid-event. Combined with
the parallel-execution model from #2, hook B cannot observe hook A's writes.

Corroborating on-disk evidence — `~/.claude/mailbox/hooks/session_start.py`:

- Line 33-34: mailbox reads `os.environ.get("MAILBOX_BOARD")` /
  `os.environ.get("MAILBOX_LABEL")` at hook entry. It does NOT read any sidecar
  or env file; it relies purely on `os.environ` already being populated.
- Line 53-57: mailbox itself writes `export MAILBOX_SESSION_ID=...` and
  `export MAILBOX_LABEL=...` to `$CLAUDE_ENV_FILE`. This is *why* `mailbox ps`,
  `mailbox send`, etc. work from later Bash subshells — confirming the env file
  propagates to **subsequent Bash commands**, NOT to a sibling hook.

**Verdict: NO.** A SessionStart hook's `CLAUDE_ENV_FILE` writes are NOT visible
to another SessionStart hook in the same event. The plan's primary T3 design
("template hook writes export lines that mailbox's hook reads via os.environ in
the same SessionStart event") **does not work**.

**Consequence (per plan §0 / T3 contingency):** T3 must use the **sidecar-JSON +
wrapper** fallback. The template's `session_start.py` cannot seed env for a
sibling hook; instead it must persist routing to a sidecar
(`<profile>/local/runtime_env.json`) and the env must be injected into mailbox's
hook by some mechanism other than a parallel sibling SessionStart hook.

**Additional wrinkle surfaced to team-lead:** the contingency text says "insert
before mailbox in `~/.claude/settings.json`", but because hooks run in parallel
(#2), "insert before" does not help. A working fallback requires the template
hook to *invoke mailbox's hook itself* (subprocess, with env pre-populated) and
mailbox's own SessionStart registration to be removed/neutralized to avoid a
double `join`. This pivots T3's installer and touches mailbox's registration —
flagged for decision before T3 is implemented.
