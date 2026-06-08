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
