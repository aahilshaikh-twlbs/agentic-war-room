"""T8 -- rollback with the has-user-data hard invariant (A9/C10)."""
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import rollback as rb  # noqa: E402


def _hermes_profile(root, *, warroom=True, user_data=False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text("name: alpha-sh\n", encoding="utf-8")
    if warroom:
        (root / "warroom_setup").mkdir()
        (root / "warroom_setup" / "__init__.py").write_text("", encoding="utf-8")
    if user_data:
        (root / "local").mkdir()
        (root / "local" / "agent.json").write_text("{}", encoding="utf-8")
    return root


def test_removes_on_clean_failure(tmp_path):
    prof = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=False)
    res = rb.rollback(prof, stages_completed=[1, 2])
    assert res.removed is True
    assert res.refused is False
    assert not prof.exists()


def test_refuses_when_user_data(tmp_path):
    prof = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=True)
    res = rb.rollback(prof, stages_completed=[1, 2, 3, 4, 5])
    assert res.removed is False
    assert res.refused is True
    assert prof.exists()  # untouched


def test_refuses_on_confirm_overwrite(tmp_path):
    # A foreign, non-Hermes directory (no config.yaml) -> never delete.
    prof = tmp_path / "random"
    prof.mkdir()
    (prof / "important.txt").write_text("keep me", encoding="utf-8")
    res = rb.rollback(prof, stages_completed=[1])
    assert res.removed is False
    assert res.refused is True
    assert prof.exists()


def test_noop_when_stage1_incomplete(tmp_path):
    prof = tmp_path / "never-made"
    res = rb.rollback(prof, stages_completed=[])
    assert res.removed is False
    assert res.refused is False
    assert "stage 1 incomplete" in res.reason


def test_logs_decision(tmp_path):
    prof = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=True)
    logged = []
    rb.rollback(prof, stages_completed=[1], logger=logged.append)
    assert logged
    assert any("REFUSED" in line for line in logged)


def test_atomic_on_partial_rmtree_failure(tmp_path):
    prof = _hermes_profile(tmp_path / "alpha-sh", warroom=True, user_data=False)

    def boom(path):
        raise OSError("disk on fire")

    res = rb.rollback(prof, stages_completed=[1], rmtree=boom)
    assert res.removed is False
    assert res.refused is False
    assert "rmtree failed" in res.reason
    assert prof.exists()  # nothing claimed-removed


def test_noop_when_path_missing_but_stage1_done(tmp_path):
    res = rb.rollback(tmp_path / "gone", stages_completed=[1])
    assert res.removed is False
    assert "does not exist" in res.reason
