"""Canonical schema: key sets, defaults, clamp, sanitization regex (Task T6)."""
from warroom_setup import schema


def test_war_room_keys_exact():
    assert schema.WAR_ROOM_KEYS == (
        "enabled", "board", "parent", "label", "role", "min_confidence",
        "gate_action", "enforce", "show_confidence_badge",
        "severity_thresholds", "severity_inference", "require_verifier_at",
        "verifier_label", "verifier_timeout_s", "escalate_at",
    )


def test_mailbox_keys_exact():
    assert schema.MAILBOX_KEYS == ("board", "label", "mailbox_home", "socket_path")


def test_defaults_cover_war_room_keys():
    assert set(schema.DEFAULTS) == set(schema.WAR_ROOM_KEYS)
    # safe values
    assert schema.DEFAULTS["enabled"] is True
    assert schema.DEFAULTS["board"] == "default"
    assert schema.DEFAULTS["role"] == "contributor"
    assert schema.DEFAULTS["min_confidence"] == 75
    assert schema.DEFAULTS["gate_action"] == "abstain"
    assert schema.DEFAULTS["enforce"] is False
    assert schema.DEFAULTS["show_confidence_badge"] is True


def test_defcon_defaults_present_and_safe():
    # All DEFCON keys default OFF / empty so an un-upgraded profile behaves
    # exactly as before: no severity table, no verifier path, no escalation.
    assert schema.DEFAULTS["severity_thresholds"] == {}
    assert schema.DEFAULTS["severity_inference"] == "explicit"
    assert schema.DEFAULTS["require_verifier_at"] == ""
    assert schema.DEFAULTS["verifier_label"] == ""
    assert schema.DEFAULTS["verifier_timeout_s"] == 30
    assert schema.DEFAULTS["escalate_at"] == ""


def test_role_vocab_documents_verifier():
    # role stays a free scalar; verifier is the new sanctioned value.
    assert "verifier" in schema.ROLE_VOCAB and "contributor" in schema.ROLE_VOCAB


def test_mailbox_defaults_cover_mailbox_keys():
    assert set(schema.MAILBOX_DEFAULTS) == set(schema.MAILBOX_KEYS)


def test_clamp_pct_strings():
    assert schema.clamp_pct("75") == 75
    assert schema.clamp_pct("150") == 100
    assert schema.clamp_pct("-5") == 0
    assert schema.clamp_pct("") == 75
    assert schema.clamp_pct("abc") == 75


def test_clamp_pct_numbers_and_none():
    assert schema.clamp_pct(50) == 50
    assert schema.clamp_pct(200) == 100
    assert schema.clamp_pct(None) == 75
    assert schema.clamp_pct(True) == 75  # bools are not percentages


def test_clamp_pct_custom_default():
    assert schema.clamp_pct("", default=10) == 10
    assert schema.clamp_pct("80", default=10) == 80


def test_blocked_values_regex_hits():
    r = schema.BLOCKED_VALUES_REGEX
    assert r.search("admin from U0ABCDE1234")
    assert r.search("team T0ABCDE1234")
    assert r.search("agent-1a2b3c4d-1234-5678-9abc-def012345678")
    assert r.search("host api.internal here")
    assert r.search("/Users/someone/Documents/vault/self")


def test_blocked_values_regex_misses_clean_template():
    r = schema.BLOCKED_VALUES_REGEX
    assert not r.search("war_room:\n  board: default\n  role: contributor\n")
    assert not r.search("<<FILL-IN: the one-line default lean>>")
    assert not r.search("permission integer 277025770560")  # 12 digits, not a snowflake
