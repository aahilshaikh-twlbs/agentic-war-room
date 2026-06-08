"""Shared input validators (Task T5). One test block per validator."""
from warroom_setup import validators as v


def test_valid_slug():
    assert v.valid_slug("zed")
    assert v.valid_slug("z3d-bot")
    assert v.valid_slug("a")
    assert not v.valid_slug("")
    assert not v.valid_slug("1bad")          # must start with a letter
    assert not v.valid_slug("Zed")           # no uppercase
    assert not v.valid_slug("has space")
    assert not v.valid_slug("under_score")   # slug excludes underscore
    assert not v.valid_slug("a" * 65)        # 64-char cap


def test_valid_channel_id():
    assert v.valid_channel_id("12345678901234567")     # 17 digits
    assert v.valid_channel_id("12345678901234567890")  # 20 digits
    assert not v.valid_channel_id("1234567890123456")  # 16 digits, too short
    assert not v.valid_channel_id("123456789012345678901")  # 21 digits
    assert not v.valid_channel_id("12345abc901234567")
    assert not v.valid_channel_id("")
    assert not v.valid_channel_id(None)


def test_valid_bot_token_discord_shape():
    assert v.valid_bot_token("FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL")
    assert not v.valid_bot_token("not-a-token")
    assert not v.valid_bot_token("only.two")
    assert not v.valid_bot_token("")
    assert not v.valid_bot_token(None)


def test_valid_bot_token_slack_shape():
    assert v.valid_bot_token("xoxb-123456789012-abcdefABCDEF")
    assert v.valid_bot_token("xapp-1-A012345678-0123456789-abcdef")
    assert not v.valid_bot_token("xoxb-")
    assert not v.valid_bot_token("xyz-123456789012")


def test_valid_board_name():
    assert v.valid_board_name("default")
    assert v.valid_board_name("team-alpha")
    assert v.valid_board_name("repo:owner/name")
    assert v.valid_board_name("board.1")
    assert not v.valid_board_name("")
    assert not v.valid_board_name("-leading-dash")
    assert not v.valid_board_name("has space")
    assert not v.valid_board_name("a" * 65)


def test_valid_handle():
    assert v.valid_handle("zed")
    assert v.valid_handle("zed_bot")     # handles allow underscore
    assert v.valid_handle("z-3")
    assert not v.valid_handle("")
    assert not v.valid_handle("1zed")
    assert not v.valid_handle("Zed")
    assert not v.valid_handle("has space")


def test_valid_handle_is_superset_of_valid_slug():
    # Migration safety (T23): every slug-valid handle stays handle-valid.
    for s in ("zed", "z3d-bot", "a", "a" * 64):
        if v.valid_slug(s):
            assert v.valid_handle(s)
