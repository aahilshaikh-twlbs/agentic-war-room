"""enroll.bootstrap(parent=...): records the home board's parent link
engine-side via the discovered mailbox CLI (`create-board <board> --parent
<p>`), fail-warn on every failure mode, `.env` stays single-board."""
import json
import shutil
import stat
from pathlib import Path

from warroom_setup import cli, enroll

FIXTURE = (Path(__file__).resolve().parent / "fixtures"
           / "fake_mailbox_record.sh")


def _profile(tmp_path):
    prof = tmp_path / "profiles" / "alpha-sh"
    (prof / "hooks").mkdir(parents=True)
    prof.joinpath("config.yaml").write_text("model: {}\n", encoding="utf-8")
    return prof


def _env_with_cli(tmp_path, with_cli=True):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    env = {"HOME": str(home), "PATH": ""}
    if with_cli:
        mh = tmp_path / "mhome"
        mh.mkdir()
        dst = mh / "mailbox"
        shutil.copy2(FIXTURE, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR)
        env["MAILBOX_HOME"] = str(mh)
    return env


def test_bootstrap_parent_invokes_create_board(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(log))
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "ok"
    assert st.parent == "team-platform"
    assert st.parent_status == "ok"
    assert log.read_text().splitlines() == [
        "create-board squad-api --parent team-platform"]


def test_bootstrap_without_parent_never_calls_engine(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(log))
    st = enroll.bootstrap(prof, "shared", "alpha-sh",
                          env=_env_with_cli(tmp_path))
    assert st.parent is None and st.parent_status is None
    assert not log.exists()


def test_bootstrap_parent_failure_is_fail_warn(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_EXIT", "1")
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "ok"                  # enrollment itself succeeded
    assert st.parent_status == "parent-failed"
    # config + .env still written: fail-warn, never fail-stop
    assert "MAILBOX_BOARD=squad-api" in (prof / ".env").read_text()


def test_bootstrap_parent_with_no_cli_records_cli_not_found(tmp_path):
    prof = _profile(tmp_path)
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh",
                          env=_env_with_cli(tmp_path, with_cli=False),
                          parent="team-platform")
    assert st.status == "cli-not-found"
    assert st.parent_status == "cli-not-found"


def test_bootstrap_parent_keeps_env_single_board(tmp_path, monkeypatch):
    # Spec: `.env` shape is UNCHANGED — single MAILBOX_BOARD, no parent key.
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(tmp_path / "l.log"))
    enroll.bootstrap(prof, "squad-api", "alpha-sh",
                     env=_env_with_cli(tmp_path), parent="team-platform")
    env_txt = (prof / ".env").read_text()
    assert "MAILBOX_BOARD=squad-api" in env_txt
    assert "team-platform" not in env_txt


def test_bootstrap_dry_run_records_parent_without_writes(tmp_path):
    prof = _profile(tmp_path)
    st = enroll.bootstrap(prof, "squad-api", "alpha-sh", dry_run=True,
                          env=_env_with_cli(tmp_path), parent="team-platform")
    assert st.status == "dry-run"
    assert st.parent == "team-platform"
    assert st.parent_status is None
    assert not (prof / "local").exists()


def test_state_file_records_parent_fields(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    monkeypatch.setenv("FAKE_MAILBOX_LOG", str(tmp_path / "l.log"))
    enroll.bootstrap(prof, "squad-api", "alpha-sh",
                     env=_env_with_cli(tmp_path), parent="team-platform")
    data = json.loads(
        (prof / "local" / "warroom-enroll.json").read_text())
    assert data["parent"] == "team-platform"
    assert data["parent_status"] == "ok"


def test_cli_enroll_parent_flag_passthrough(tmp_path, monkeypatch):
    prof = _profile(tmp_path)
    seen = {}

    def _fake(pr, b, l, dry_run=False, env=None, parent=None):
        seen.update(board=b, parent=parent)
        return enroll.EnrollState(b, l, None, "", "", 0.0, "ok")

    monkeypatch.setattr(enroll, "bootstrap", _fake)
    rc = cli.main(["enroll", "--board", "squad-api",
                   "--parent", "team-platform", "--profile-root", str(prof)])
    assert rc == 0
    assert seen == {"board": "squad-api", "parent": "team-platform"}


def test_confidence_gate_skill_mentions_federation_scopes():
    text = (Path(__file__).resolve().parents[1] / "skills"
            / "confidence-gate" / "SKILL.md").read_text(encoding="utf-8")
    assert "mailbox escalate" in text
    assert "mailbox broadcast" in text
    assert "visibility only" in text


def test_warroom_skill_documents_federation_verbs():
    # DV9 + spec File-path map: warroom/SKILL.md documents the federation
    # protocol verbs alongside the existing board-local protocol.
    text = (Path(__file__).resolve().parents[1] / "skills"
            / "warroom" / "SKILL.md").read_text(encoding="utf-8")
    assert "mailbox escalate" in text
    assert "mailbox broadcast" in text
    assert "mailbox tree" in text
    assert "mailbox fleet" in text
