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


def test_sev_absent_defaults_to_default():
    env, body = E.parse_last_line("The DB is down.\n⟦conf=0.82 grounded=tool,file missing=none⟧")
    assert env is not None
    assert env.sev == "default"
    assert body == "The DB is down."


def test_sev_parsed_when_present():
    env, body = E.parse_last_line("prod is down\n⟦conf=0.97 grounded=tool,file missing=none sev=alert1⟧")
    assert env is not None
    assert env.sev == "alert1"
    assert env.conf == 0.97
    assert env.grounded == ("tool", "file")
    assert body == "prod is down"


def test_sev_each_known_token_parses():
    for tok in ("alert1", "alert2", "alert3", "default"):
        env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool missing=none sev=%s⟧" % tok)
        assert env is not None and env.sev == tok


def test_sev_unknown_token_makes_envelope_absent():
    # An out-of-vocab sev token does not match the anchored grammar, so the whole
    # envelope is treated as absent (same posture as a malformed conf=): a claim
    # with no parseable envelope abstains no-envelope. The gate never silently
    # downgrades to a guessed severity from a malformed footer.
    env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool missing=none sev=alert9⟧")
    assert env is None


def test_sev_must_be_last_field():
    # sev= appears AFTER missing=. A sev before missing is not the canonical
    # grammar and must not parse.
    env, _ = E.parse_last_line("x\n⟦conf=0.90 grounded=tool sev=alert1 missing=none⟧")
    assert env is None


def test_sev_spoof_midmessage_ignored():
    text = "> user said ⟦conf=0.99 grounded=tool missing=none sev=alert1⟧\nactually unverified"
    env, body = E.parse_last_line(text)
    assert env is None
    assert body == text


def test_sev_regex_still_linear_no_redos():
    import time
    payload = "⟦conf=0.9 grounded=tool missing=" + "a" * 100000 + " sev=alert1⟧"
    t = time.time()
    E.parse_last_line("x\n" + payload)
    assert time.time() - t < 1.0
