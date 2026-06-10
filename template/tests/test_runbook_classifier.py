"""Structural guard for the classifier-tuning operator runbook."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNBOOK = REPO / "docs" / "superpowers" / "runbooks" / "2026-06-09-awr-classifier-tuning-runbook.md"


def test_runbook_exists_and_documents_the_loop():
    text = RUNBOOK.read_text(encoding="utf-8")
    for step in ("COLLECT", "LABEL", "FIXTURE", "TEST", "TUNE", "VERIFY"):
        assert step in text, step
    assert "gate_review.py review --log" in text
    assert "gate_review.py label --log" in text
    assert "classifier_cases.json" in text
    assert "never" in text.lower() and "length" in text.lower()
    assert "false negative" in text.lower() and "false positive" in text.lower()
    assert "rotate" in text.lower() or "truncate" in text.lower()
