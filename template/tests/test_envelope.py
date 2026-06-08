import wg_envelope as E


def test_parses_canonical_last_line():
    env, body = E.parse_last_line("The DB is down.\n⟦conf=0.82 grounded=tool,file missing=none⟧")
    assert env is not None
    assert env.conf == 0.82
    assert env.grounded == ("tool", "file")
    assert env.missing == "none"
    assert body == "The DB is down."


def test_no_envelope_returns_none_and_original():
    env, body = E.parse_last_line("just chatting, no envelope")
    assert env is None
    assert body == "just chatting, no envelope"


def test_malformed_envelope_is_absent():
    env, _ = E.parse_last_line("x\n⟦conf=high grounded=tool missing=none⟧")
    assert env is None


def test_spoof_midmessage_envelope_ignored():
    # A user-quoted lookalike NOT on the final line must be ignored.
    text = "> user said ⟦conf=0.99 grounded=tool missing=none⟧\nactually unverified"
    env, body = E.parse_last_line(text)
    assert env is None                      # last line has no envelope
    assert body == text


def test_grounded_none_only():
    env, _ = E.parse_last_line("claim\n⟦conf=0.40 grounded=none missing=a repro⟧")
    assert env.grounded == ("none",)
    assert env.missing == "a repro"


def test_regex_is_linear_no_redos():
    # Pathological input must return quickly (bounded quantifiers).
    import time
    payload = "⟦conf=0." + "9" * 100000 + " grounded=tool missing=none⟧"
    t = time.time()
    E.parse_last_line("x\n" + payload)
    assert time.time() - t < 1.0
