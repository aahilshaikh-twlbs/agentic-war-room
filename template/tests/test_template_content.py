"""Shape + sanitization guards for shipped template content files.

These lock the deliverables of Phase 4 (T10-T17): correct structure, required
placeholders, and ZERO employer/operator strings. Tests accrete here as each
content task lands.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---- T10: SOUL.md skeleton ----

def test_soul_skeleton_has_h1_and_sections():
    text = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    assert text.lstrip().startswith("<!--") or text.lstrip().startswith("# ")
    h2s = re.findall(r"^## (.+)$", text, re.M)
    for required in ("Voice", "How you talk", "How you work", "What you value",
                     "Communication", "Writing rules", "Boundaries"):
        assert required in h2s, "missing H2: %s" % required
    assert 6 <= len(h2s) <= 8


def test_soul_skeleton_is_all_fill_in_no_real_content():
    text = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    assert "<<FILL-IN" in text
    assert "twelvelabs" not in text.lower()
