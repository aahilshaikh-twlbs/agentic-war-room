"""patch_persona_decisions: sentinel-bounded, idempotent, accumulating append
to the user-owned local/persona/decisions.md overlay.

Unlike patch_war_room_block (which replaces its region wholesale), this one
ACCUMULATES rules inside the sentinel region and preserves anything an owner
hand-edits between the markers.
"""
from pathlib import Path

from warroom_setup import setup


def _prof(tmp_path):
    prof = tmp_path / "profiles" / "zed"
    (prof / "local" / "persona").mkdir(parents=True)
    return prof


def test_first_write_creates_sentinel_region(tmp_path):
    prof = _prof(tmp_path)
    changed = setup.patch_persona_decisions(prof, "Always write a failing test first.")
    assert changed is True
    text = (prof / "local" / "persona" / "decisions.md").read_text(encoding="utf-8")
    assert "<!-- _WR_PERSONA_BEGIN -->" in text
    assert "<!-- _WR_PERSONA_END -->" in text
    assert "Always write a failing test first." in text


def test_rewrite_same_rule_is_noop(tmp_path):
    prof = _prof(tmp_path)
    assert setup.patch_persona_decisions(prof, "Rule A") is True
    assert setup.patch_persona_decisions(prof, "Rule A") is False
    text = (prof / "local" / "persona" / "decisions.md").read_text(encoding="utf-8")
    assert text.count("Rule A") == 1


def test_owner_edits_between_sentinels_survive(tmp_path):
    prof = _prof(tmp_path)
    setup.patch_persona_decisions(prof, "Rule A")
    target = prof / "local" / "persona" / "decisions.md"

    # Owner hand-edits a line into the managed region.
    text = target.read_text(encoding="utf-8")
    end = "<!-- _WR_PERSONA_END -->"
    text = text.replace(end, "Owner hand-written note.\n" + end)
    target.write_text(text, encoding="utf-8")

    # Appending a new rule must preserve the owner note AND the prior rule.
    changed = setup.patch_persona_decisions(prof, "Rule B")
    assert changed is True
    final = target.read_text(encoding="utf-8")
    assert "Owner hand-written note." in final
    assert "Rule A" in final
    assert "Rule B" in final


def test_custom_sentinel_id_uses_distinct_markers(tmp_path):
    prof = _prof(tmp_path)
    setup.patch_persona_decisions(prof, "Coder rule", sentinel_id="coder")
    text = (prof / "local" / "persona" / "decisions.md").read_text(encoding="utf-8")
    assert "_CODER_PERSONA_BEGIN" in text
    assert "_WR_PERSONA_BEGIN" not in text


def test_preserves_preexisting_file_body(tmp_path):
    prof = _prof(tmp_path)
    target = prof / "local" / "persona" / "decisions.md"
    target.write_text("# Decision-Making Heuristics\n\nExisting body.\n", encoding="utf-8")
    setup.patch_persona_decisions(prof, "Rule A")
    final = target.read_text(encoding="utf-8")
    assert "Existing body." in final
    assert "Rule A" in final
