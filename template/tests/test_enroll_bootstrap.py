"""T2 — enroll.bootstrap: state file + mailbox: block + Claude Code hook install.

All tests pass an explicit `env` with HOME -> tmp so the real ~/.claude is never
touched.
"""
import json
import shutil
import stat
from pathlib import Path

from warroom_setup import enroll, setup

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fake_mailbox_bin.sh"


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


def test_bootstrap_writes_state_file_atomically(tmp_path):
    prof = _profile(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=_env_with_cli(tmp_path))
    sf = prof / "local" / "warroom-enroll.json"
    assert sf.is_file()
    assert stat.S_IMODE(sf.stat().st_mode) == 0o600
    assert [p for p in (prof / "local").iterdir() if p.name.endswith(".tmp")] == []


def test_bootstrap_patches_mailbox_block_in_config(tmp_path):
    prof = _profile(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=_env_with_cli(tmp_path))
    text = (prof / "config.yaml").read_text()
    assert setup._MB_BEGIN in text and setup._MB_END in text
    for key in ("board", "label", "mailbox_home", "socket_path"):
        assert ("  %s:" % key) in text
    assert "board: shared" in text
    assert "label: alpha-sh" in text


def test_bootstrap_is_idempotent_when_inputs_unchanged(tmp_path):
    prof = _profile(tmp_path)
    env = _env_with_cli(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    cfg1 = (prof / "config.yaml").read_text()
    s1 = json.loads((prof / "local" / "warroom-enroll.json").read_text())
    enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    cfg2 = (prof / "config.yaml").read_text()
    s2 = json.loads((prof / "local" / "warroom-enroll.json").read_text())
    assert cfg1 == cfg2
    s1.pop("last_check_ts"); s2.pop("last_check_ts")
    assert s1 == s2


def test_bootstrap_updates_block_when_label_changes(tmp_path):
    prof = _profile(tmp_path)
    env = _env_with_cli(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha", env=env)
    enroll.bootstrap(prof, "shared", "alpha2", env=env)
    text = (prof / "config.yaml").read_text()
    assert "label: alpha2" in text
    assert "label: alpha\n" not in text
    assert text.count(setup._MB_BEGIN) == 1


def test_bootstrap_records_cli_not_found_without_raising(tmp_path):
    prof = _profile(tmp_path)
    env = _env_with_cli(tmp_path, with_cli=False)
    st = enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    assert st.status == "cli-not-found"
    assert (prof / "local" / "warroom-enroll.json").is_file()
    assert (prof / "local" / "warroom-enroll.log").is_file()


def test_bootstrap_dry_run_writes_nothing(tmp_path):
    prof = _profile(tmp_path)
    st = enroll.bootstrap(prof, "shared", "alpha-sh", dry_run=True, env=_env_with_cli(tmp_path))
    assert st.status == "dry-run"
    assert not (prof / "local").exists()
    assert setup._MB_BEGIN not in (prof / "config.yaml").read_text()


def test_bootstrap_writes_runtime_env_to_dotenv(tmp_path):
    # Revised T3: routing is delivered to mailbox's hook via <profile>/.env, not
    # a settings.json hook. Existing .env keys (e.g. tokens) are preserved.
    prof = _profile(tmp_path)
    (prof / ".env").write_text("ANTHROPIC_API_KEY=sk-secret\n", encoding="utf-8")
    enroll.bootstrap(prof, "shared", "alpha-sh", env=_env_with_cli(tmp_path))
    env_txt = (prof / ".env").read_text()
    assert "MAILBOX_BOARD=shared" in env_txt
    assert "MAILBOX_LABEL=alpha-sh" in env_txt
    assert "ANTHROPIC_API_KEY=sk-secret" in env_txt  # not clobbered


def test_bootstrap_does_not_touch_claude_settings(tmp_path):
    # The revised approach must NOT create or edit any settings.json.
    prof = _profile(tmp_path)
    env = _env_with_cli(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    assert not (Path(env["HOME"]) / ".claude" / "settings.json").exists()


def test_bootstrap_appends_log_line_per_invocation(tmp_path):
    prof = _profile(tmp_path)
    env = _env_with_cli(tmp_path)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    enroll.bootstrap(prof, "shared", "alpha-sh", env=env)
    lines = [l for l in (prof / "local" / "warroom-enroll.log").read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert "status=ok" in lines[0] and "board=shared" in lines[0]


def test_bootstrap_writes_war_room_board_in_sync_with_mailbox_board(tmp_path):
    prof = _profile(tmp_path)
    # wizard writes war_room with the same board value first
    setup.patch_war_room_block(prof, "shared")
    enroll.bootstrap(prof, "shared", "alpha-sh", env=_env_with_cli(tmp_path))
    text = (prof / "config.yaml").read_text()
    # both blocks present, both say board: shared
    assert text.count("board: shared") == 2
