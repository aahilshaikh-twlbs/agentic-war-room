"""Feature A — assimilate an existing (foreign) Hermes profile into the war room.

T5 subset: classification helpers (_classify / _detect_channels /
_already_assimilated). No CLI reachability yet.
"""
from pathlib import Path

from warroom_setup import assimilate, setup

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FOREIGN = FIXTURES / "foreign_profile"
FOREIGN_DISCORD = FIXTURES / "foreign_profile_with_discord"
ALREADY = FIXTURES / "already_assimilated"


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
