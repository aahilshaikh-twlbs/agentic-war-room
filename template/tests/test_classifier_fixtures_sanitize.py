"""Direct sanitize scan over the classifier fixtures file.

sanitize_check excludes tests/ by default, so committed fixture rows would
otherwise escape the public-repo gate. This scans the fixtures FILE's directory
directly via sanitize_check.scan so any future operator-added row carrying a
leaked shape (Slack/Discord id, snowflake, internal host) or a configured
employer/operator name is caught in CI.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "classifier_cases.json"


def _load_checker():
    path = ROOT / "scripts" / "sanitize_check.py"
    spec = importlib.util.spec_from_file_location("sanitize_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()


def test_shipped_classifier_fixtures_are_clean():
    violations = checker.scan(str(FIXTURES.parent), names=["alpha-sh", "beta-sh"])
    leaks = [v for v in violations if FIXTURES.name in v[0]]
    assert leaks == [], "fixture sanitization violations: %r" % leaks


def test_scan_flags_a_leaked_shape_in_a_fixture(tmp_path):
    # Prove the guard bites: a fixture row carrying a blocked shape is caught.
    bad = tmp_path / "classifier_cases.json"
    bad.write_text('[{"text": "ping from U0ABCDE1234X", '
                   '"expected_is_claim": false, "note": "x"}]\n', encoding="utf-8")
    v = checker.scan(str(tmp_path))
    assert any(r == "blocked-shape" for _, _, r, _ in v)
