from warroom_setup import selectables


def test_build_stages_orders_by_stage_order():
    stages = selectables.build_stages(selectables.TOGGLES)
    assert [s.name for s in stages] == ["Persona", "Channels", "Model", "WarRoom"]


def test_default_ids():
    ids = selectables.default_ids(selectables.TOGGLES)
    assert "channels.discord" in ids and "model.opus" in ids
    assert "channels.slack" not in ids


def test_secret_ids_never_include_plain_fields():
    assert "ANTHROPIC_API_KEY" in selectables.SECRET_IDS
    assert "agent_name" not in selectables.SECRET_IDS


def test_defcon_fields_appended_with_enable_if():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    for fid in ("warroom.severity_alert1", "warroom.severity_alert2",
                "warroom.verifier_label"):
        assert fid in ids
        fld = [f for f in selectables.TEXT_FIELDS if f.id == fid][0]
        assert fld.enable_if == "warroom.enroll"
        assert fld.secret is False
        assert fid not in selectables.ENV_FIELD_IDS
    # DEFCON fields come after parent (append order)
    assert ids.index("warroom.severity_alert1") > ids.index("warroom.parent")
