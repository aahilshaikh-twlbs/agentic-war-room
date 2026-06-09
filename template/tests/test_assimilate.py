"""Feature A — assimilate an existing (foreign) Hermes profile into the war room.

T5 subset: classification helpers (_classify / _detect_channels /
_already_assimilated). No CLI reachability yet.
"""
import hashlib
import io
import shutil
from pathlib import Path

from warroom_setup import assimilate, cli, setup

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FOREIGN = FIXTURES / "foreign_profile"
FOREIGN_DISCORD = FIXTURES / "foreign_profile_with_discord"
ALREADY = FIXTURES / "already_assimilated"


def _hash_tree(root):
    root = Path(root)
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------- #
# _classify
# --------------------------------------------------------------------------- #
def test_classify_foreign_hermes_profile():
    info = assimilate._classify(FOREIGN)
    assert info["exists"] is True
    assert info["is_hermes"] is True
    assert info["is_awr_template"] is False
    assert info["already_assimilated"] is False
    assert info["orphan_sentinel"] is False


def test_classify_already_assimilated():
    info = assimilate._classify(ALREADY)
    assert info["already_assimilated"] is True
    assert info["orphan_sentinel"] is False
    assert info["is_hermes"] is True


def test_classify_detects_discord_creds_in_env():
    info = assimilate._classify(FOREIGN_DISCORD)
    assert info["channels"]["discord"] is True
    assert info["channels"]["slack"] is False


def test_classify_nonexistent_path():
    info = assimilate._classify(Path("/tmp/awr-does-not-exist-xyz"))
    assert info["exists"] is False
    assert info["is_hermes"] is False


def test_classify_orphan_sentinel_without_enroll(tmp_path):
    # Synthesis fix (§3 vs §7): a war-room sentinel block with NO enroll state is
    # an orphan -- classify flags it so the orchestrator can refuse (exit 4)
    # rather than silently rewriting a block we may not own.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "model:\n  name: opus\n"
        + setup._WR_BEGIN + "\n"
        + "war_room:\n  board: shared\n"
        + setup._WR_END + "\n",
        encoding="utf-8",
    )
    info = assimilate._classify(tmp_path)
    assert info["orphan_sentinel"] is True
    assert info["already_assimilated"] is False


# --------------------------------------------------------------------------- #
# _detect_channels
# --------------------------------------------------------------------------- #
def test_detect_channels_none_when_no_env(tmp_path):
    ch = assimilate._detect_channels(tmp_path)
    assert ch == {"discord": False, "slack": False}


def test_detect_channels_ignores_empty_values(tmp_path):
    (tmp_path / ".env").write_text(
        "# comment\nDISCORD_BOT_TOKEN=\nSLACK_BOT_TOKEN=xoxb-real\n", encoding="utf-8"
    )
    ch = assimilate._detect_channels(tmp_path)
    assert ch["discord"] is False  # present but empty -> not configured
    assert ch["slack"] is True


# --------------------------------------------------------------------------- #
# _already_assimilated
# --------------------------------------------------------------------------- #
def test_already_assimilated_true_for_fixture():
    assert assimilate._already_assimilated(ALREADY) is True


def test_already_assimilated_false_for_foreign():
    assert assimilate._already_assimilated(FOREIGN) is False


# --------------------------------------------------------------------------- #
# T6 -- CLI dispatch + dry-run report (no patching yet)
# --------------------------------------------------------------------------- #
def test_assimilate_dry_run_writes_nothing(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    before = _hash_tree(prof)
    out = io.StringIO()
    rc = assimilate.assimilate(prof, board="shared", label="beta-sh",
                               dry_run=True, out=out)
    assert rc == 0
    report = out.getvalue()
    assert "Assimilating" in report and "[dry-run] no files written." in report
    assert "war_room block:  absent (will create)" in report
    assert _hash_tree(prof) == before  # byte-identical


def test_assimilate_nonexistent_path_returns_3(tmp_path):
    out = io.StringIO()
    rc = assimilate.assimilate(tmp_path / "nope", dry_run=True, out=out)
    assert rc == 3


def test_assimilate_non_hermes_dir_returns_3(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    out = io.StringIO()
    rc = assimilate.assimilate(d, dry_run=True, out=out)
    assert rc == 3


def test_resolve_label_falls_back_to_basename(tmp_path):
    prof = tmp_path / "beta-sh"
    prof.mkdir()
    assert assimilate._resolve_label(prof, None) == "beta-sh"


def test_resolve_label_reads_agent_json_handle(tmp_path):
    prof = tmp_path / "prof"
    (prof / "local").mkdir(parents=True)
    (prof / "local" / "agent.json").write_text('{"handle": "gamma-sh"}', encoding="utf-8")
    assert assimilate._resolve_label(prof, None) == "gamma-sh"


def test_cli_assimilate_dispatch_dry_run(tmp_path, capsys):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    rc = cli.main(["assimilate", str(prof), "--dry-run",
                   "--board", "shared", "--label", "beta-sh"])
    assert rc == 0
    assert "Assimilating" in capsys.readouterr().out


def test_cli_assimilate_help_lists_new_args(capsys):
    parser = cli._build_parser()
    # the subparser exists and accepts the documented flags without error
    ns = parser.parse_args(["assimilate", "/tmp/x", "--dry-run", "--no-walkthrough",
                            "--reconfigure", "--enforce", "--yes",
                            "--board", "b", "--label", "l"])
    assert ns.cmd == "assimilate"
    assert ns.dry_run and ns.no_walkthrough and ns.reconfigure and ns.enforce and ns.yes


# --------------------------------------------------------------------------- #
# T7 -- live patching (war_room + persona), idempotency, exit matrix
# --------------------------------------------------------------------------- #
def _live(prof, **kw):
    kw.setdefault("yes", True)
    kw.setdefault("no_walkthrough", True)
    kw.setdefault("board", "shared")
    kw.setdefault("label", "beta-sh")
    kw.setdefault("out", io.StringIO())
    return assimilate.assimilate(prof, **kw)


def test_assimilate_writes_war_room_and_persona(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    rc = _live(prof)
    assert rc == 0
    cfg = (prof / "config.yaml").read_text(encoding="utf-8")
    assert setup._WR_BEGIN in cfg
    assert "board: shared" in cfg and "label: beta-sh" in cfg and "enabled: true" in cfg
    persona = (prof / "local" / "persona" / "decisions.md").read_text(encoding="utf-8")
    assert "mailbox claim-lane" in persona


def test_assimilate_enforce_off_by_default(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    _live(prof)
    assert "enforce: false" in (prof / "config.yaml").read_text(encoding="utf-8")


def test_assimilate_enforce_flag_sets_true(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    _live(prof, enforce=True)
    assert "enforce: true" in (prof / "config.yaml").read_text(encoding="utf-8")


def test_assimilate_preserves_existing_hooks_block(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    _live(prof)
    cfg = (prof / "config.yaml").read_text(encoding="utf-8")
    # foreign hooks / plugins / personalities survive verbatim
    assert "on_session_start:" in cfg
    assert 'bash hooks/foreign_boot.sh' in cfg
    assert "system_prompt_suffix: \"Be warm and proactive.\"" in cfg


def test_assimilate_idempotent_with_reconfigure(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    _live(prof, reconfigure=True)
    after_first = _hash_tree(prof)
    _live(prof, reconfigure=True)
    assert _hash_tree(prof) == after_first  # zero content diff on re-run


def test_assimilate_refuses_repeat_without_reconfigure(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(ALREADY, prof)  # has sentinel + enroll.json
    out = io.StringIO()
    rc = assimilate.assimilate(prof, board="shared", label="beta-sh",
                               yes=True, no_walkthrough=True, out=out)
    assert rc == 2


def test_assimilate_orphan_sentinel_returns_4(tmp_path):
    prof = tmp_path / "prof"
    prof.mkdir()
    (prof / "config.yaml").write_text(
        "model:\n  name: opus\n" + setup._WR_BEGIN + "\nwar_room:\n  board: x\n"
        + setup._WR_END + "\n", encoding="utf-8")
    out = io.StringIO()
    rc = assimilate.assimilate(prof, yes=True, no_walkthrough=True, out=out)
    assert rc == 4
    assert "manual review" in out.getvalue()


def test_assimilate_reconfigure_overrides_orphan(tmp_path):
    prof = tmp_path / "prof"
    prof.mkdir()
    (prof / "config.yaml").write_text(
        "model:\n  name: opus\n" + setup._WR_BEGIN + "\nwar_room:\n  board: x\n"
        + setup._WR_END + "\n", encoding="utf-8")
    rc = _live(prof, reconfigure=True)
    assert rc == 0
    cfg = (prof / "config.yaml").read_text(encoding="utf-8")
    assert cfg.count(setup._WR_BEGIN) == 1
    assert "board: shared" in cfg


def test_assimilate_awr_template_redirects_exit_0(tmp_path):
    prof = tmp_path / "prof"
    (prof / "warroom_setup").mkdir(parents=True)
    (prof / "warroom_setup" / "__init__.py").write_text("", encoding="utf-8")
    (prof / "config.yaml").write_text(
        "model:\n  name: opus\n" + setup._WR_BEGIN + "\nwar_room:\n  board: x\n"
        + setup._WR_END + "\n", encoding="utf-8")
    out = io.StringIO()
    rc = assimilate.assimilate(prof, yes=True, no_walkthrough=True, out=out)
    assert rc == 0
    assert "war-room template profile" in out.getvalue()


def test_assimilate_confirm_abort_writes_nothing(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    before = _hash_tree(prof)
    out = io.StringIO()
    rc = assimilate.assimilate(prof, board="shared", label="beta-sh",
                               no_walkthrough=True, yes=False,
                               in_stream=io.StringIO("n\n"), out=out)
    assert rc == 4
    assert _hash_tree(prof) == before


def test_assimilate_confirm_yes_proceeds(tmp_path):
    prof = tmp_path / "prof"
    shutil.copytree(FOREIGN, prof)
    out = io.StringIO()
    rc = assimilate.assimilate(prof, board="shared", label="beta-sh",
                               no_walkthrough=True, yes=False,
                               in_stream=io.StringIO("y\n"), out=out)
    assert rc == 0
    assert setup._WR_BEGIN in (prof / "config.yaml").read_text(encoding="utf-8")
