"""Golden intake scenarios — committed reviewer checklists (adopted OQ1:
reviewer-run, NOT auto-graded by an LLM judge in CI). This suite lints only
their SHAPE: the five canonical scenarios exist, each carries the four required
sections plus checkbox items, and none leaks org artifacts by shape
(sanitize_check.py skips tests/, so the blocklist regex runs here)."""
import re
from pathlib import Path

import pytest

from warroom_setup import schema

SCEN_DIR = Path(__file__).resolve().parent / "fixtures" / "warroom_scenarios"

SCENARIOS = [
    "duplicate-already-owned",
    "out-of-scope-board",
    "high-severity-escalate",
    "ungrounded-question",
    "lane-deny-defer",
]

REQUIRED_SECTIONS = [
    "## Board setup",
    "## Incoming",
    "## Expected decision path",
    "## Reviewer checklist",
]


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_exists_with_required_sections(name):
    p = SCEN_DIR / ("%s.md" % name)
    assert p.is_file(), "missing golden scenario: %s" % name
    text = p.read_text(encoding="utf-8")
    for sec in REQUIRED_SECTIONS:
        assert sec in text, "%s missing section %r" % (p.name, sec)
    assert re.search(r"- \[ \] ", text), "%s must carry checkbox items" % p.name


def test_scenarios_readme_documents_review_flow():
    text = (SCEN_DIR / "README.md").read_text(encoding="utf-8")
    assert "reviewer" in text.lower()
    assert "not auto-graded" in text.lower()


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_is_sanitized(name):
    text = (SCEN_DIR / ("%s.md" % name)).read_text(encoding="utf-8")
    assert not schema.BLOCKED_VALUES_REGEX.search(text)
