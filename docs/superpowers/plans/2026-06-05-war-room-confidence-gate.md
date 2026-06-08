# War-Room Confidence Gate (Layer 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Hermes **plugin** inside the war-room agent distribution that, on every outbound turn, suppresses ungrounded/low-confidence claims before they reach the channel — replacing them with an abstention that states the gap.

**Architecture:** A directory plugin at `template/plugins/warroom-gate/` (lands at `<profile>/plugins/warroom-gate/`, auto-discovered because the gateway runs with `HERMES_HOME=<profile>`). Its `register(ctx)` wires a `transform_llm_output` callback. The callback parses the agent's canonical confidence **envelope** off the last line, classifies claim-vs-chatter, and gates against `war_room.min_confidence`: pass (strip envelope, optional badge), or abstain (return a replacement string). It is **internally fail-closed** — it never raises, because Hermes leaves the text unchanged (fail-open) if a hook raises.

**Tech Stack:** Python ≥3.9, **stdlib only**, `# type:` comment hints, `pytest` dev-only. Builds on the war-room agent template (idea #1) and its Layer 1 confidence-gate protocol/config.

---

## Ground Truth (verified against Hermes v0.15.1 — `file:line`)

- **Hook event = `transform_llm_output`**, fired once per turn after the tool loop, before the response is sent (`agent/conversation_loop.py:4588-4608`). Receives `response_text`, `session_id`, `model`, `platform`. **First non-empty string returned replaces the output**; `None`/empty leaves it unchanged. → abstention = in-place replacement.
- **`pre_gateway_dispatch` is the WRONG hook** — it is *inbound* (the user's `MessageEvent`, before auth; `skip`/`rewrite`/`allow`) (`gateway/run.py:7226-7265`). Do not use it.
- **Shell hooks cannot transform LLM output** — `shell_hooks._parse_response` (`agent/shell_hooks.py:496-539`) honors only `pre_tool_call` block and `pre_llm_call` context, returns `None` otherwise. → must be an **in-process Python plugin**, not a `config.yaml` shell hook.
- **Plugin contract** (`hermes_cli/plugins.py:19, :1248, :935, :1474`): a directory with **`plugin.yaml`** + **`__init__.py`** exposing `register(ctx)`; loaded as a package `hermes_plugins.<slug>`; `ctx.register_hook(name, callback)` registers a callback.
- **Discovery** (`plugins.py:1077-1082`): user plugins load from `get_hermes_home()/plugins`. The gateway sets `HERMES_HOME=<profile dir>` (`gateway.py:2378`, `:777-780`). → a distribution-shipped `<profile>/plugins/warroom-gate/` is auto-loaded. Gated by `plugins.enabled` in `config.yaml`.
- **Hermes is fail-OPEN on hook error** (`conversation_loop.py:4607-4608`): a raising hook → text passes unchanged. → our callback must catch everything and **return an abstention** instead of raising.
- **No `chat_id` / no session-evidence** in the callback payload → gating is **profile-wide**; the only grounding signal is the agent's envelope; an independent verifier is **deferred** (spec §Verifier).

### File layout (this plan)

```
template/
  plugins/warroom-gate/
    plugin.yaml          # manifest (name, kind: standalone, version)
    __init__.py          # path-insert + `from wg_gate import register`
    wg_envelope.py       # parse/strip the ⟦conf=… grounded=… missing=…⟧ envelope (pure)
    wg_classify.py       # claim vs chatter (pure)
    wg_policy.py         # decision table (pure)
    wg_render.py         # abstention message + badge (pure)
    wg_gateconfig.py     # read war_room.* from config.yaml managed block (IO)
    wg_audit.py          # append-only gate log, no secrets (IO)
    wg_gate.py           # the callback + register(ctx) (effectful edge; fail-closed)
  config.yaml            # + plugins.enabled, + enforce/show_confidence_badge in managed block
  tests/
    test_gate_manifest.py test_envelope.py test_classify.py test_policy.py
    test_render.py test_gateconfig.py test_audit.py test_gate_callback.py
```

Flat `wg_*` module names + a `sys.path` insert in `__init__.py` make the same
code importable under Hermes' package loader *and* in tests (pyproject adds
`plugins/warroom-gate` to `pythonpath`); the `wg_` prefix avoids any global
module-name collision.

---

## Task 0: Scaffold the plugin + manifest + test path

**Files:**
- Create: `template/plugins/warroom-gate/plugin.yaml`
- Create: `template/plugins/warroom-gate/__init__.py`
- Modify: `template/pyproject.toml` (add the plugin dir to `pythonpath`)
- Test: `template/tests/test_gate_manifest.py`

- [ ] **Step 1: Write `plugin.yaml`**

```yaml
name: warroom-gate
kind: standalone
version: 0.1.0
description: "War-room confidence gate: suppresses ungrounded/low-confidence claims before they reach the channel."
```

- [ ] **Step 2: Write `__init__.py`** (path-insert so flat `wg_*` imports resolve under Hermes' loader)

```python
"""War-room confidence gate plugin. Stdlib only, Python >=3.9.

Loaded by Hermes as a package (hermes_plugins.warroom-gate). The sys.path insert
lets the flat wg_* modules import each other identically here and in tests.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wg_gate import register  # noqa: E402  (must follow the path insert)

__all__ = ["register"]
```

- [ ] **Step 3: Add the plugin dir to `pyproject.toml` test path**

Change:

```toml
pythonpath = ["."]
```

to:

```toml
pythonpath = [".", "plugins/warroom-gate"]
```

- [ ] **Step 4: Write the failing test `tests/test_gate_manifest.py`**

```python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "warroom-gate"


def test_plugin_dir_has_manifest_and_init():
    assert (PLUGIN / "plugin.yaml").is_file()
    assert (PLUGIN / "__init__.py").is_file()


def test_manifest_has_name_and_kind():
    text = (PLUGIN / "plugin.yaml").read_text()
    assert re.search(r"^name:\s*warroom-gate\s*$", text, re.M)
    assert re.search(r"^kind:\s*standalone\s*$", text, re.M)
```

- [ ] **Step 5: Run** — note `wg_gate` does not exist yet, so importing `__init__` fails; this test only reads files, so it passes. Verify:

Run: `cd template && python3 -m pytest tests/test_gate_manifest.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add template/plugins/warroom-gate/plugin.yaml template/plugins/warroom-gate/__init__.py \
        template/pyproject.toml template/tests/test_gate_manifest.py
git commit -m "AWR gate: scaffold warroom-gate plugin (manifest + init + test path)"
```

---

## Task 1: `wg_envelope.py` — parse/strip the confidence envelope

**Files:**
- Create: `template/plugins/warroom-gate/wg_envelope.py`
- Test: `template/tests/test_envelope.py`

- [ ] **Step 1: Write the failing test `tests/test_envelope.py`**

```python
import wg_envelope as E


def test_parses_canonical_last_line():
    env, body = E.parse_last_line("The DB is down.\n⟦conf=0.82 grounded=tool,file missing=none⟧")
    assert env is not None
    assert env.conf == 0.82
    assert env.grounded == ("tool", "file")
    assert env.missing == "none"
    assert body == "The DB is down."


def test_no_envelope_returns_none_and_original():
    env, body = E.parse_last_line("just chatting, no envelope")
    assert env is None
    assert body == "just chatting, no envelope"


def test_malformed_envelope_is_absent():
    env, _ = E.parse_last_line("x\n⟦conf=high grounded=tool missing=none⟧")
    assert env is None


def test_spoof_midmessage_envelope_ignored():
    # A user-quoted lookalike NOT on the final line must be ignored.
    text = "> user said ⟦conf=0.99 grounded=tool missing=none⟧\nactually unverified"
    env, body = E.parse_last_line(text)
    assert env is None                      # last line has no envelope
    assert body == text


def test_grounded_none_only():
    env, _ = E.parse_last_line("claim\n⟦conf=0.40 grounded=none missing=a repro⟧")
    assert env.grounded == ("none",)
    assert env.missing == "a repro"


def test_regex_is_linear_no_redos():
    # Pathological input must return quickly (bounded quantifiers).
    import time
    payload = "⟦conf=0." + "9" * 100000 + " grounded=tool missing=none⟧"
    t = time.time()
    E.parse_last_line("x\n" + payload)
    assert time.time() - t < 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_envelope.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wg_envelope'`.

- [ ] **Step 3: Write `wg_envelope.py`**

```python
"""Confidence-envelope parsing. Stdlib only, Python >=3.9.

Canonical form (agent-controlled, last line only):
    ⟦conf=0.82 grounded=tool,file missing=none⟧
Anti-spoof: only an envelope occupying the entire final non-empty line is
honored; lookalikes elsewhere (e.g. quoted user text) are ignored.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

GROUNDED_VOCAB = ("tool", "file", "source", "citation", "memory", "none")

# Sentinel brackets as \uXXXX escapes so the matching logic never depends on how
# the source file's non-ASCII bytes are decoded. U+27E6/U+27E7 = the ⟦ / ⟧ pair.
_L = "\u27e6"
_R = "\u27e7"

# Bounded quantifiers only -> linear, ReDoS-safe. Strict closing (a single _R,
# no optional open bracket) keeps the grammar tight for anti-spoof.
_ENV_RE = re.compile(
    "^" + _L
    + r"conf=(?P<conf>0(?:\.\d{1,3})?|1(?:\.0{1,3})?)"
    + r" grounded=(?P<grounded>[a-z,]{1,64})"
    + r" missing=(?P<missing>[^" + _L + _R + r"\n]{0,200})"
    + _R + "$"
)
_STRAY_RE = re.compile(_L + r"conf=[^" + _R + r"\n]{0,300}" + _R)


@dataclass
class Envelope:
    conf: float
    grounded: Tuple[str, ...]
    missing: str


def parse_last_line(text):
    # type: (str) -> Tuple[Optional[Envelope], str]
    if not isinstance(text, str) or not text:
        return None, text
    lines = text.rstrip("\n").split("\n")
    last = lines[-1].strip()
    m = _ENV_RE.match(last)
    if not m:
        return None, text
    grounded = tuple(g for g in m.group("grounded").split(",") if g in GROUNDED_VOCAB)
    if not grounded:
        return None, text
    env = Envelope(conf=float(m.group("conf")), grounded=grounded, missing=m.group("missing").strip())
    body = "\n".join(lines[:-1]).rstrip("\n")
    return env, body


def strip_stray_envelopes(text):
    # type: (str) -> str
    return _STRAY_RE.sub("", text)
```

> The bracket sentinels (`⟦`=U+27E6, `⟧`=U+27E7) are written as `\uXXXX` escapes
> in the matching code, so the gate logic never depends on how the source file's
> non-ASCII bytes are decoded; the canonical form is shown literally in the
> docstring only for readability (the file is UTF-8). The grammar is strict: a
> single closing `⟧`, and `missing` excludes *both* sentinels — so a stray or
> nested bracket (e.g. `…missing=x⟦⟧`) is rejected, not absorbed (anti-spoof).

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_envelope.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_envelope.py template/tests/test_envelope.py
git commit -m "AWR gate: confidence-envelope parser (last-line-only, ReDoS-safe)"
```

---

## Task 2: `wg_classify.py` — claim vs chatter

**Files:**
- Create: `template/plugins/warroom-gate/wg_classify.py`
- Test: `template/tests/test_classify.py`

- [ ] **Step 1: Write the failing test `tests/test_classify.py`**

```python
import wg_classify as C


def test_chatter_is_not_a_claim():
    for t in ["ok", "got it", "thanks!", "on it", "👍", "hey", "yes"]:
        assert C.is_claim(t) is False, t


def test_pure_question_is_not_a_claim():
    assert C.is_claim("which service owns the checkout flow?") is False


def test_substantive_assertion_is_a_claim():
    assert C.is_claim("The outage is caused by a 30s timeout in api/pay.py:88.") is True


def test_terse_declarative_is_a_claim():
    # Short, no period, but still an assertion — must be gated, not exempted.
    for t in ["it's down", "payments are failing", "db is corrupted"]:
        assert C.is_claim(t) is True, t


def test_empty_is_not_a_claim():
    assert C.is_claim("   ") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_classify.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `wg_classify.py`**

```python
"""Claim vs chatter heuristic. Stdlib only, Python >=3.9.

Conservative: when unsure, treat as a claim (so it gets gated). Chatter =
greetings/acks, very short non-declarative text, or a pure question.
This heuristic is the main accuracy risk (see spec); tune with real traffic.
"""
_CHATTER = {
    "ok", "okay", "kk", "got it", "thanks", "thank you", "ty", "on it", "sure",
    "yep", "yes", "no", "nope", "hi", "hey", "hello", "ack", "acknowledged",
    "done", "+1", "👍", "✅",
}


def is_claim(text):
    # type: (str) -> bool
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower().strip(" .!👍✅")
    if low in _CHATTER:
        return False
    # Pure question (asking, not asserting): single line, no declarative sentence.
    if t.endswith("?") and "\n" not in t and len(t) < 200 and "." not in t.rstrip("?"):
        return False
    # NOTE: no length-based exemption. Terse declaratives ("it's down",
    # "payments are failing", "db is corrupted") are claims and MUST be gated.
    # See spec — any length short-circuit is a bug, not a convenience.
    return True
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_classify.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_classify.py template/tests/test_classify.py
git commit -m "AWR gate: claim-vs-chatter classifier"
```

---

## Task 3: `wg_policy.py` — the decision table

**Files:**
- Create: `template/plugins/warroom-gate/wg_policy.py`
- Test: `template/tests/test_policy.py`

- [ ] **Step 1: Write the failing test `tests/test_policy.py`**

```python
import wg_policy as P
from wg_envelope import Envelope


def _env(conf, grounded=("tool",), missing="none"):
    return Envelope(conf=conf, grounded=grounded, missing=missing)


def test_chatter_passes():
    d = P.decide(False, None, 0.75)
    assert d.action == P.PASS and d.reason == "chatter"


def test_claim_no_envelope_abstains():
    d = P.decide(True, None, 0.75)
    assert d.action == P.ABSTAIN and d.reason == "no-envelope"


def test_claim_ungrounded_abstains():
    d = P.decide(True, _env(0.9, grounded=("none",)), 0.75)
    assert d.action == P.ABSTAIN and d.reason == "ungrounded"


def test_claim_below_threshold_abstains_with_missing():
    d = P.decide(True, _env(0.60, missing="a repro"), 0.75)
    assert d.action == P.ABSTAIN and d.reason == "below-threshold" and d.missing == "a repro"


def test_claim_grounded_and_confident_passes():
    d = P.decide(True, _env(0.80), 0.75)
    assert d.action == P.PASS and d.reason == "ok"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `wg_policy.py`**

```python
"""Gate decision. Stdlib only, Python >=3.9. Pure."""
from dataclasses import dataclass
from typing import Optional

from wg_envelope import Envelope

PASS = "pass"
ABSTAIN = "abstain"


@dataclass
class Decision:
    action: str          # PASS | ABSTAIN
    reason: str          # chatter | ok | no-envelope | ungrounded | below-threshold | internal-error
    missing: str = ""


def decide(is_claim, env, threshold):
    # type: (bool, Optional[Envelope], float) -> Decision
    if not is_claim:
        return Decision(PASS, "chatter")
    if env is None:
        return Decision(ABSTAIN, "no-envelope")
    if not env.grounded or env.grounded == ("none",):
        return Decision(ABSTAIN, "ungrounded", env.missing)
    if env.conf < threshold:
        return Decision(ABSTAIN, "below-threshold", env.missing)
    return Decision(PASS, "ok")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_policy.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_policy.py template/tests/test_policy.py
git commit -m "AWR gate: decision-table policy"
```

---

## Task 4: `wg_render.py` — abstention message + badge

**Files:**
- Create: `template/plugins/warroom-gate/wg_render.py`
- Test: `template/tests/test_render.py`

- [ ] **Step 1: Write the failing test `tests/test_render.py`**

```python
import wg_render as R
import wg_policy as P


def test_below_threshold_abstention_names_gap_and_numbers():
    d = P.Decision(P.ABSTAIN, "below-threshold", "a prod log line")
    msg = R.abstention(d, conf_pct=62, threshold_pct=75)
    assert "62%" in msg and "75%" in msg and "a prod log line" in msg


def test_ungrounded_abstention():
    d = P.Decision(P.ABSTAIN, "ungrounded", "a citation")
    msg = R.abstention(d, None, None)
    assert "isn't grounded" in msg and "a citation" in msg


def test_no_envelope_abstention():
    d = P.Decision(P.ABSTAIN, "no-envelope")
    msg = R.abstention(d, None, None)
    assert "no confidence envelope" in msg.lower()


def test_with_badge_appends_when_shown():
    out = R.with_badge("The fix is in api/pay.py.", 0.82, True)
    assert "82%" in out and out.startswith("The fix")


def test_with_badge_noop_when_hidden():
    assert R.with_badge("body", 0.82, False) == "body"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `wg_render.py`**

```python
"""Abstention + badge rendering. Stdlib only, Python >=3.9. Pure."""
from typing import Optional

from wg_policy import Decision


def abstention(decision, conf_pct=None, threshold_pct=None):
    # type: (Decision, Optional[int], Optional[int]) -> str
    miss = decision.missing or "more grounded evidence"
    if decision.reason == "below-threshold" and conf_pct is not None and threshold_pct is not None:
        return ("\U0001f6d1 Holding back - not confident enough to post that "
                "(%d%% < %d%% bar).\n   To clear it I'd need: %s." % (conf_pct, threshold_pct, miss))
    if decision.reason == "ungrounded":
        return ("\U0001f6d1 Holding back - that claim isn't grounded in evidence I can cite.\n"
                "   To clear it I'd need: %s." % miss)
    if decision.reason == "no-envelope":
        return ("\U0001f6d1 Holding back - no confidence envelope on a claim; "
                "not posting unverified info to the war room.")
    return ("\U0001f6d1 Holding back - gate error; not posting unverified info to the war room.")


def with_badge(body, conf, show):
    # type: (str, float, bool) -> str
    if not show:
        return body
    pct = int(round(conf * 100))
    return body.rstrip("\n") + "\n\n- \u2713 %d%%" % pct
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_render.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_render.py template/tests/test_render.py
git commit -m "AWR gate: abstention + badge rendering"
```

---

## Task 5: `wg_gateconfig.py` — read `war_room.*` from config.yaml

**Files:**
- Create: `template/plugins/warroom-gate/wg_gateconfig.py`
- Test: `template/tests/test_gateconfig.py`

- [ ] **Step 1: Write the failing test `tests/test_gateconfig.py`**

```python
import wg_gateconfig as G


def test_reads_managed_block(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model: {}\n"
        "# >>> warroom-managed (set via `warroom setup`) >>>\n"
        "war_room:\n"
        "  enabled: true\n"
        "  board: incident-1\n"
        "  min_confidence: 80\n"
        "  gate_action: abstain\n"
        "  enforce: true\n"
        "  show_confidence_badge: false\n"
        "# <<< warroom-managed <<<\n"
        "plugins:\n  enabled: true\n"
    )
    cfg = G.read(tmp_path)
    assert cfg["enforce"] is True
    assert cfg["min_confidence"] == 80
    assert cfg["show_badge"] is False


def test_defaults_when_missing(tmp_path):
    cfg = G.read(tmp_path)            # no config.yaml
    assert cfg == {"enforce": False, "min_confidence": 75, "show_badge": True}


def test_enforce_defaults_false_when_absent(tmp_path):
    (tmp_path / "config.yaml").write_text("war_room:\n  board: x\n")
    assert G.read(tmp_path)["enforce"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_gateconfig.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `wg_gateconfig.py`**

```python
"""Read war_room.* from <profile>/config.yaml. Stdlib only, Python >=3.9.

Line-based scan of the `war_room:` block (no PyYAML). Conservative defaults;
`enforce` defaults False so an un-set-up profile does not gate.
"""
import re
from pathlib import Path
from typing import Dict

_DEFAULTS = {"enforce": False, "min_confidence": 75, "show_badge": True}


def _scan(text):
    # type: (str) -> Dict
    out = dict(_DEFAULTS)
    in_wr = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("war_room:"):
            in_wr = True
            continue
        if in_wr:
            # A non-indented, non-comment, non-empty line ends the block.
            if line[:1] not in (" ", "\t", "#") and s:
                break
            m = re.match(r"(enforce|min_confidence|show_confidence_badge):\s*(\S+)", s)
            if m:
                k, v = m.group(1), m.group(2)
                if k == "enforce":
                    out["enforce"] = v.lower() == "true"
                elif k == "min_confidence":
                    try:
                        out["min_confidence"] = max(0, min(100, int(v)))
                    except ValueError:
                        pass
                elif k == "show_confidence_badge":
                    out["show_badge"] = v.lower() == "true"
    return out


def read(profile_root):
    # type: (Path) -> Dict
    p = Path(profile_root) / "config.yaml"
    if not p.is_file():
        return dict(_DEFAULTS)
    try:
        return _scan(p.read_text(encoding="utf-8"))
    except OSError:
        return dict(_DEFAULTS)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_gateconfig.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_gateconfig.py template/tests/test_gateconfig.py
git commit -m "AWR gate: config reader for war_room block"
```

---

## Task 6: `wg_audit.py` — gate decision log (no secrets)

**Files:**
- Create: `template/plugins/warroom-gate/wg_audit.py`
- Test: `template/tests/test_audit.py`

- [ ] **Step 1: Write the failing test `tests/test_audit.py`**

```python
import os
import stat
import wg_audit as A
import wg_policy as P


def test_log_appends_no_secret_text(tmp_path):
    d = P.Decision(P.ABSTAIN, "below-threshold", "a repro")
    A.log(tmp_path, d, 0.6, "claim", "SECRET answer body with sk-xxx token")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert logf.is_file()
    text = logf.read_text()
    assert "abstain" in text and "below-threshold" in text
    assert "sk-xxx" not in text and "SECRET answer body" not in text   # only a hash prefix


def test_log_file_is_0600(tmp_path):
    A.log(tmp_path, P.Decision(P.PASS, "ok"), 0.9, "claim", "body")
    logf = tmp_path / "local" / "war_room" / "gate.log"
    assert stat.S_IMODE(os.stat(logf).st_mode) == 0o600


def test_log_never_raises_on_bad_root(tmp_path):
    # A non-writable / odd root must not raise (logging is best-effort).
    A.log(tmp_path / "nonexistent-parent" / "x", P.Decision(P.PASS, "ok"), None, "chatter", "")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `wg_audit.py`**

```python
"""Append-only gate-decision log. Stdlib only, Python >=3.9.

Records the decision, never the message text or any secret. Best-effort:
logging failures never propagate (the gate must not fail because logging did).
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from wg_policy import Decision


def log(profile_root, decision, conf, kind, text):
    # type: (Path, Decision, Optional[float], str, str) -> None
    try:
        digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:8]
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conf_s = "-" if conf is None else ("%.2f" % conf)
        line = "%s action=%s reason=%s conf=%s kind=%s sha=%s\n" % (
            ts, decision.action, decision.reason, conf_s, kind, digest)
        d = Path(profile_root) / "local" / "war_room"
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(d), 0o700)
        except OSError:
            pass
        f = d / "gate.log"
        with open(str(f), "a", encoding="utf-8") as fh:
            fh.write(line)
        try:
            os.chmod(str(f), 0o600)
        except OSError:
            pass
    except Exception:
        return  # logging is best-effort; never raise
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_audit.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add template/plugins/warroom-gate/wg_audit.py template/tests/test_audit.py
git commit -m "AWR gate: audit log (no secrets, 0600, best-effort)"
```

---

## Task 7: `wg_gate.py` — the callback + `register(ctx)` (fail-closed)

**Files:**
- Create: `template/plugins/warroom-gate/wg_gate.py`
- Test: `template/tests/test_gate_callback.py`

- [ ] **Step 1: Write the failing test `tests/test_gate_callback.py`**

```python
import wg_gate
import wg_policy


def _profile(tmp_path, enforce=True, min_conf=75, badge=True):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enabled: true\n"
        "  enforce: %s\n"
        "  min_confidence: %d\n"
        "  show_confidence_badge: %s\n" % (str(enforce).lower(), min_conf, str(badge).lower())
    )
    return tmp_path


def test_disabled_enforce_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, enforce=False)))
    assert wg_gate.gate(response_text="The DB is down.\n⟦conf=0.9 grounded=tool missing=none⟧") is None


def test_chatter_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    assert wg_gate.gate(response_text="thanks!") is None


def test_low_confidence_claim_is_replaced_with_abstention(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, min_conf=75)))
    out = wg_gate.gate(response_text="The outage is X.\n⟦conf=0.50 grounded=tool missing=a prod log⟧")
    assert out is not None
    assert "Holding back" in out and "a prod log" in out


def test_ungrounded_claim_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    out = wg_gate.gate(response_text="It is definitely a memory leak.\n⟦conf=0.95 grounded=none missing=a heap dump⟧")
    assert out is not None and "Holding back" in out


def test_claim_without_envelope_abstains(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    out = wg_gate.gate(response_text="The root cause is a race in the scheduler at line 88 of run.py.")
    assert out is not None and "Holding back" in out


def test_high_confidence_grounded_claim_passes_with_badge(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path, min_conf=75, badge=True)))
    out = wg_gate.gate(response_text="The fix is api/pay.py:88.\n⟦conf=0.88 grounded=tool,file missing=none⟧")
    # envelope stripped, badge added, no envelope left
    assert out is not None
    assert "⟦" not in out and "88%" in out and "api/pay.py:88" in out


def test_never_raises_even_on_internal_bug(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(_profile(tmp_path)))
    # Force an internal error by monkeypatching decide to blow up.
    monkeypatch.setattr(wg_gate.wg_policy, "decide", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = wg_gate.gate(response_text="A claim that should error.\n⟦conf=0.9 grounded=tool missing=none⟧")
    assert isinstance(out, str) and "Holding back" in out      # fail closed, no exception


def test_register_wires_transform_llm_output():
    seen = {}

    class Ctx:
        def register_hook(self, name, cb):
            seen[name] = cb

    wg_gate.register(Ctx())
    assert "transform_llm_output" in seen
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_gate_callback.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wg_gate'`.

- [ ] **Step 3: Write `wg_gate.py`**

```python
"""transform_llm_output callback for the war-room confidence gate.
Stdlib only, Python >=3.9.

CRITICAL: Hermes is fail-OPEN on hook error (it leaves text unchanged if the
hook raises - conversation_loop.py:4607). So this callback catches everything
and returns an abstention rather than raising. It returns None to leave text
unchanged (chatter / disabled / nothing to do), or a string to replace it.
"""
import os
from pathlib import Path

import wg_audit
import wg_classify
import wg_envelope
import wg_gateconfig
import wg_policy
import wg_render


def _profile_root():
    # type: () -> Path
    hh = os.environ.get("HERMES_HOME")
    if hh:
        return Path(hh)
    # Fallback: plugin dir is <profile>/plugins/warroom-gate/ -> parents[2] = profile.
    return Path(__file__).resolve().parents[2]


def gate(response_text="", session_id="", model="", platform="", **_):
    # type: (str, str, str, str, object) -> object
    try:
        if not isinstance(response_text, str) or not response_text.strip():
            return None
        root = _profile_root()
        cfg = wg_gateconfig.read(root)
        if not cfg["enforce"]:
            return None

        env, body = wg_envelope.parse_last_line(response_text)
        claim = wg_classify.is_claim(body if env is not None else response_text)

        if not claim:
            cleaned = wg_envelope.strip_stray_envelopes(response_text).rstrip()
            return cleaned if cleaned != response_text.rstrip() else None

        threshold = cfg["min_confidence"] / 100.0
        decision = wg_policy.decide(True, env, threshold)
        conf = env.conf if env is not None else None
        wg_audit.log(root, decision, conf, "claim", response_text)

        if decision.action == wg_policy.PASS:
            out = wg_render.with_badge(body, env.conf, cfg["show_badge"]) if env is not None else body
            return out if out != response_text else None

        conf_pct = int(round(env.conf * 100)) if env is not None else None
        return wg_render.abstention(decision, conf_pct, cfg["min_confidence"])
    except Exception:
        # FAIL CLOSED: never propagate (Hermes would pass the ungated text).
        try:
            return wg_render.abstention(
                wg_policy.Decision(wg_policy.ABSTAIN, "internal-error"), None, None)
        except Exception:
            return "\U0001f6d1 Holding back - gate error; not posting unverified info."


def register(ctx):
    ctx.register_hook("transform_llm_output", gate)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_gate_callback.py -v`
Expected: 8 passed.

- [ ] **Step 5: Verify the package imports cleanly under the Hermes-style path insert**

Run: `cd template && python3 -c "import importlib.util, pathlib; p=pathlib.Path('plugins/warroom-gate/__init__.py'); s=importlib.util.spec_from_file_location('hermes_plugins.warroom_gate', p, submodule_search_locations=[str(p.parent)]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('register' , hasattr(m,'register'))"`
Expected: `register True` (proves `__init__.py`'s path insert + `from wg_gate import register` works when loaded as a package, mirroring Hermes).

- [ ] **Step 6: Commit**

```bash
git add template/plugins/warroom-gate/wg_gate.py template/tests/test_gate_callback.py
git commit -m "AWR gate: transform_llm_output callback (fail-closed) + register"
```

---

## Task 8: Config wiring — `plugins.enabled` + managed-block gate keys + wizard toggle

Builds on the template's Layer 1 managed block (Task 17 of the template plan).

**Files:**
- Modify: `template/config.yaml` (add `plugins.enabled: true`; add `enforce` + `show_confidence_badge` to the managed block)
- Modify: `template/warroom_setup/setup.py` (extend `patch_war_room_block` to write `enforce` + `show_confidence_badge`)
- Modify: `template/warroom_setup/selectables.py` (add a `warroom.enforce` toggle)
- Test: `template/tests/test_gate_wiring.py`

- [ ] **Step 1: Write the failing test `tests/test_gate_wiring.py`**

```python
import re
from pathlib import Path
from warroom_setup import setup

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_config_enables_plugins():
    cfg = (ROOT / "config.yaml").read_text()
    assert re.search(r"^plugins:\s*$", cfg, re.M)
    assert re.search(r"^\s+enabled:\s*true\s*$", cfg, re.M)


def test_shipped_managed_block_has_gate_keys():
    cfg = (ROOT / "config.yaml").read_text()
    assert "enforce:" in cfg and "show_confidence_badge:" in cfg


def test_patch_writes_gate_keys(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n")
    setup.patch_war_room_block(tmp_path, "incident-9", min_confidence=80, enforce=True)
    text = (tmp_path / "config.yaml").read_text()
    assert "enforce: true" in text and "min_confidence: 80" in text and "show_confidence_badge:" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd template && python3 -m pytest tests/test_gate_wiring.py -v`
Expected: FAIL — shipped config lacks `plugins:`/gate keys; `patch_war_room_block` has no `enforce` param.

- [ ] **Step 3: Update `config.yaml`** — append `plugins:` and extend the managed block

Add at the end of the file:

```yaml
plugins:
  enabled: true
```

And change the managed block (from template Task 17) to include the gate keys:

```yaml
# >>> warroom-managed (set via `warroom setup`) >>>
war_room:
  enabled: false
  board: default
  role: contributor
  min_confidence: 75
  gate_action: abstain
  enforce: false
  show_confidence_badge: true
# <<< warroom-managed <<<
```

- [ ] **Step 4: Extend `patch_war_room_block` in `setup.py`** to write the gate keys

Replace the function body's `block` list and signature:

```python
def patch_war_room_block(profile_root, board, min_confidence=75, gate_action="abstain"):
```

with:

```python
def patch_war_room_block(profile_root, board, min_confidence=75, gate_action="abstain",
                         enforce=False, show_confidence_badge=True):
```

and replace the `block = "\n".join([...])` list with:

```python
    block = "\n".join([
        _WR_BEGIN,
        "war_room:",
        "  enabled: true",
        "  board: %s" % (board or "default"),
        "  role: contributor",
        "  min_confidence: %d" % int(min_confidence),
        "  gate_action: %s" % gate_action,
        "  enforce: %s" % ("true" if enforce else "false"),
        "  show_confidence_badge: %s" % ("true" if show_confidence_badge else "false"),
        _WR_END,
    ])
```

Update the `run_setup` call site:

```python
    if "warroom.enroll" in selected:
        mc = _clamp_pct(values.get("warroom.min_confidence", ""))
        patch_war_room_block(profile_root, values.get("warroom.board", "").strip(),
                             min_confidence=mc, enforce=("warroom.enforce" in selected))
```

- [ ] **Step 5: Add the `warroom.enforce` toggle to `selectables.py`** — append to `TOGGLES`:

```python
    Toggle(id="warroom.enforce", group="WarRoom",
           desc="structurally enforce the confidence gate (suppress ungrounded claims)", default=True),
```

- [ ] **Step 6: Run new + full suite**

Run: `cd template && python3 -m pytest tests/test_gate_wiring.py -v && python3 -m pytest -q`
Expected: gate-wiring passes; full suite green (template Tasks 0-17 + gate Tasks 0-8).

- [ ] **Step 7: Commit**

```bash
git add template/config.yaml template/warroom_setup/setup.py \
        template/warroom_setup/selectables.py template/tests/test_gate_wiring.py
git commit -m "AWR gate: wire plugins.enabled + enforce/badge config + wizard toggle"
```

---

## Task 9: Structural/security tests for the plugin

**Files:**
- Test: `template/tests/test_gate_security.py`

- [ ] **Step 1: Write the test `tests/test_gate_security.py`**

```python
import ast
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "warroom-gate"


def _wg_modules():
    return sorted(PLUGIN.glob("wg_*.py"))


def test_no_network_imports_in_plugin():
    banned = {"socket", "urllib", "http", "requests", "ftplib", "smtplib"}
    for f in _wg_modules() + [PLUGIN / "__init__.py"]:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] not in banned, f"{f.name} imports {n.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned


def test_pure_modules_have_no_io():
    banned = {"os", "subprocess", "socket", "sys"}
    for name in ("wg_envelope.py", "wg_classify.py", "wg_policy.py", "wg_render.py"):
        tree = ast.parse((PLUGIN / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name not in banned, f"{name} imports {n.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") not in banned, f"{name} imports from {node.module}"


def test_no_shell_or_eval():
    for f in _wg_modules() + [PLUGIN / "__init__.py"]:
        text = f.read_text()
        assert "os.system" not in text and "shell=True" not in text
        assert "eval(" not in text and "exec(" not in text


def test_gate_callback_signature_is_kwargs_tolerant():
    # transform_llm_output passes response_text/session_id/model/platform; the
    # callback must accept unknown kwargs (**_) so a future payload key can't crash it.
    import inspect
    import wg_gate
    sig = inspect.signature(wg_gate.gate)
    assert any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()), "gate() must accept **kwargs"
```

- [ ] **Step 2: Run to verify it passes**

Run: `cd template && python3 -m pytest tests/test_gate_security.py -v`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add template/tests/test_gate_security.py
git commit -m "AWR gate: structural/security tests (no network, pure leaves, kwargs-tolerant)"
```

---

## Task 10: End-to-end manual smoke (documented, not automated)

Real gateway run; requires Hermes + a profile with `warroom.enforce: true`.

- [ ] **Step 1: Install + enable the gate on a throwaway profile**

Run:
```sh
hermes profile install /Users/aahil/Documents/Code/agentic-war-room/template --name awr-gate-smoke -y
cd ~/.hermes/profiles/awr-gate-smoke && bash scripts/setup.sh --yes
# confirm the plugin landed and config enables it
test -f plugins/warroom-gate/__init__.py && echo "plugin shipped"
grep -q "enabled: true" config.yaml && echo "plugins enabled"
```
Then set `enforce: true` (setup default-on once `warroom.enroll` chosen) and confirm via `grep "enforce:" config.yaml`.

- [ ] **Step 2: Confirm Hermes discovers the plugin**

Run: `HERMES_HOME=~/.hermes/profiles/awr-gate-smoke hermes plugins list 2>&1 | grep -i warroom-gate`
Expected: the plugin is listed (loaded). If not, check `HERMES_PLUGINS_DEBUG=1 hermes ... ` output.

- [ ] **Step 3: Behavioral check via the gateway/chat**

Drive a turn whose answer would be a low-confidence claim and confirm the channel shows the **abstention**, not the claim; drive a chatter turn and confirm it passes; check `local/war_room/gate.log` recorded the decisions (no secrets).

- [ ] **Step 4: Tear down + record**

Run: `hermes profile delete awr-gate-smoke -y`
Then note the smoke result in the template `README.md` "Verified" section and commit.

---

## Self-Review (completed by plan author)

**Spec coverage (`2026-06-05-war-room-confidence-gate-design.md`):**
- §Where it hooks in (plugin, `transform_llm_output`, ships in profile) → Tasks 0, 7, 8. ✅
- §Envelope (grammar, last-line-only, anti-spoof, ReDoS-safe) → Task 1. ✅
- §Classify → Task 2. ✅
- §Gate policy (full decision table) → Task 3. ✅
- §Abstention output + badge → Task 4. ✅
- §Config (`enforce`/`min_confidence`/`show_confidence_badge`, `plugins.enabled`) → Tasks 5, 8. ✅
- §Reliability (fail-closed; never raises; `enforce:false`→None; streaming caveat documented) → Task 7 + its tests. ✅
- §Security (no network, pure leaves, no secrets in log, plugin trust) → Tasks 6, 9. ✅
- §Observability (gate.log, no secrets) → Task 6. ✅
- §Verifier DEFERRED → no task (intentional; documented in spec). ✅

**Placeholder scan:** none. Every code step has complete code; the manual e2e (Task 10) is explicitly manual.

**Type/name consistency:** `Envelope(conf,grounded,missing)`, `Decision(action,reason,missing)`, `wg_policy.PASS/ABSTAIN`, `wg_envelope.parse_last_line/strip_stray_envelopes`, `wg_gateconfig.read` → `{enforce,min_confidence,show_badge}`, `wg_render.abstention/with_badge`, `wg_audit.log(root,decision,conf,kind,text)`, `wg_gate.gate(**kwargs)/register(ctx)` are consistent across tasks. `patch_war_room_block` signature change (Task 8) is backward-compatible (new params default off) with the template plan's Task 17.

**Known soft spots (flagged, non-blocking):**
- `wg_classify.is_claim` is heuristic — the main accuracy risk (false-abstain on a real claim is safe; false-pass on chatter is harmless). Tune with real traffic; the spec calls this out.
- On an internal error the callback abstains even for what might have been chatter (fail-closed bias) — loud-safe for a war room; documented.
- Task 8 depends on the template plan's Task 17 having shipped the managed block; if executed standalone, create the managed block first.
- Live-streaming surfaces (terminal/ACP) can't un-send streamed tokens; Discord/Slack send buffered finals (the war-room target), so the replacement is authoritative there.
