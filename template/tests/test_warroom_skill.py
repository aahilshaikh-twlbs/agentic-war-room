"""L1 orchestrator — structural lint for the /warroom five-step intake protocol.

Companion to test_skill_warroom.py (the original verb/frontmatter checks, which
stay green unchanged). This file owns the protocol-shape guarantees: the five
ordered intake steps, compose-don't-restate vs confidence-gate, spec
cross-references, the orchestrate escape hatch, verb existence against the real
mailbox CLI parser, and shape-based sanitization.

Verb existence runs twice: an ast scan of coordination/src/mailbox/cli.py in
the default suite (no import — the stdlib `mailbox` MODULE shadows the package
name and coordination/src is not on the default pythonpath), and a live
build_parser() import under @integration (the guarded-import idiom from
test_runtime_engine_inproc.py).
"""
import argparse
import ast
from pathlib import Path

import pytest

from warroom_setup import schema

TESTS = Path(__file__).resolve().parent
TEMPLATE = TESTS.parent
REPO = TEMPLATE.parent
SKILL = TEMPLATE / "skills" / "warroom" / "SKILL.md"
CLI_SRC = REPO / "coordination" / "src" / "mailbox" / "cli.py"

STEP_HEADINGS = [
    "## STEP 0 — ORIENT (read the room before speaking)",
    "## STEP 1 — TRIAGE (decide whether to engage)",
    "## STEP 2 — SEVERITY (assess, do not define)",
    "## STEP 3 — ROUTE (choose board scope + audience)",
    "## STEP 4 — LANE (claim before you work)",
    "## STEP 5 — FIRST POST (grounded claim-or-question + envelope)",
]


def _text():
    return SKILL.read_text(encoding="utf-8")


def _frontmatter(md):
    lines = md.splitlines()
    assert lines[0].strip() == "---", "frontmatter must open with ---"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    data = {}
    key = None
    for line in lines[1:end]:
        if line and not line[0].isspace() and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            data[key] = val.strip()
        elif key and line.strip():  # folded continuation
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def _code_block_lines(md):
    out, infence = [], False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            infence = not infence
            continue
        if infence:
            out.append(line)
    return out


def _skill_mailbox_verbs():
    """First token after `mailbox ` on every fenced-code line."""
    verbs = set()
    for line in _code_block_lines(_text()):
        s = line.strip()
        if s.startswith("mailbox ") and len(s.split()) >= 2:
            verbs.add(s.split()[1])
    return verbs


def _parser_verbs_from_source():
    tree = ast.parse(CLI_SRC.read_text(encoding="utf-8"))
    verbs = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            verbs.add(node.args[0].value)
    return verbs


def test_frontmatter():
    fm = _frontmatter(_text())
    assert fm.get("name") == "warroom"
    desc = fm.get("description", "")
    assert desc.strip() and len(desc) <= 500
    assert "tags" not in fm


def test_steps_present_and_ordered():
    text = _text()
    idxs = []
    for h in STEP_HEADINGS:
        i = text.find(h)
        assert i != -1, "missing step heading: %r" % h
        idxs.append(i)
    assert idxs == sorted(idxs), "intake steps out of order"


def test_composes_not_restates():
    text = _text()
    assert "confidence-gate" in text, \
        "STEP 5 must reference the confidence-gate skill by name"
    assert "⟦conf=" not in text, \
        "envelope grammar must live ONLY in confidence-gate (compose, don't restate)"


def test_cross_refs():
    text = _text()
    assert "2026-06-09-awr-multi-board-federation-design.md" in text
    assert "2026-06-09-awr-defcon-severity-design.md" in text


def test_orchestrate_escape_hatch_documented():
    assert "war_room.orchestrate" in _text()


def test_skill_names_only_real_mailbox_verbs():
    if not CLI_SRC.is_file():
        pytest.skip("coordination/ checkout not present")
    skill_verbs = _skill_mailbox_verbs()
    assert skill_verbs, "skill must show mailbox commands in fenced blocks"
    unknown = skill_verbs - _parser_verbs_from_source()
    assert not unknown, \
        "skill names verbs missing from mailbox cli: %s" % sorted(unknown)


def test_federation_scope_verbs_registered():
    if not CLI_SRC.is_file():
        pytest.skip("coordination/ checkout not present")
    assert {"escalate", "broadcast", "tree", "fleet"} <= _parser_verbs_from_source()


def test_route_and_lane_verbs_in_protocol():
    named = _skill_mailbox_verbs()
    assert {"ps", "claims", "inbox", "send", "escalate", "broadcast",
            "claim-lane", "release-lane", "list-lanes"} <= named


def test_sanitized_by_shape():
    assert not schema.BLOCKED_VALUES_REGEX.search(_text())


def _cli_importable():
    # Guarded import (F16 idiom): in the default suite the stdlib `mailbox`
    # module wins and `.cli` raises; under --runintegration with
    # PYTHONPATH=coordination/src the real package resolves.
    try:
        import mailbox.cli  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _cli_importable(),
                    reason="coordination mailbox package not importable")
def test_skill_verbs_registered_in_live_parser():
    import mailbox.cli as mcli
    parser = mcli.build_parser()
    sub = next(a for a in parser._actions
               if isinstance(a, argparse._SubParsersAction))
    live = set(sub.choices)
    unknown = _skill_mailbox_verbs() - live
    assert not unknown, \
        "skill names verbs missing from live parser: %s" % sorted(unknown)
