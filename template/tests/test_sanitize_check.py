"""Sanitization CI guard (Task T21): clean tree passes; leaks are caught."""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    path = ROOT / "scripts" / "sanitize_check.py"
    spec = importlib.util.spec_from_file_location("sanitize_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()


def test_shipped_template_tree_is_clean():
    violations = checker.scan(str(ROOT))
    assert violations == [], "sanitization violations: %r" % violations[:10]


def test_detects_slack_user_id(tmp_path):
    (tmp_path / "f.md").write_text("admin from U0ABCDE1234X\n", encoding="utf-8")
    v = checker.scan(str(tmp_path))
    assert any(r == "blocked-shape" for _, _, r, _ in v)


def test_detects_snowflake_and_hostname(tmp_path):
    (tmp_path / "a.json").write_text('{"id": "12345678901234567"}\n', encoding="utf-8")
    (tmp_path / "b.yaml").write_text("host: api.internal\n", encoding="utf-8")
    v = checker.scan(str(tmp_path))
    assert len(v) >= 2


def test_detects_configurable_employer_name(tmp_path):
    (tmp_path / "c.md").write_text("Built at AcmeCorp HQ.\n", encoding="utf-8")
    clean = checker.scan(str(tmp_path))
    assert clean == []                                  # no name blocklist -> clean
    flagged = checker.scan(str(tmp_path), names=["acmecorp"])
    assert any(r.startswith("blocked-name") for _, _, r, _ in flagged)


def test_excludes_tests_and_venv(tmp_path):
    for sub in ("tests", ".venv"):
        d = tmp_path / sub
        d.mkdir()
        (d / "fixture.py").write_text('cid = "12345678901234567"\n', encoding="utf-8")
    assert checker.scan(str(tmp_path)) == []


def test_main_exits_zero_on_clean_template():
    assert checker.main([str(ROOT)]) == 0


def test_sanitization_md_documents_blocklist():
    text = (ROOT / "SANITIZATION.md").read_text(encoding="utf-8")
    assert "U0[A-Z0-9]" in text
    assert "sanitize_check.py" in text
    # genericized: documents the configurable --name mechanism, names no employer
    assert "--name" in text
    assert "employer" in text.lower()
