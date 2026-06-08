from warroom_setup import answers


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / ".warroom-setup.json"
    a = answers.Answers(selected=["model.opus"], deselected=["model.sonnet"],
                        values={"agent_name": "zed", "handle": "zed"})
    answers.save(p, a)
    loaded = answers.load(p)
    assert loaded.selected == ["model.opus"]
    assert loaded.values["agent_name"] == "zed"
    assert p.read_text().endswith("\n")


def test_save_drops_secret_ids(tmp_path):
    p = tmp_path / ".warroom-setup.json"
    a = answers.Answers(selected=[], deselected=[],
                        values={"agent_name": "zed", "ANTHROPIC_API_KEY": "sk-xxx"})
    answers.save(p, a)
    text = p.read_text()
    assert "sk-xxx" not in text          # secret never persisted
    assert "ANTHROPIC_API_KEY" not in text
    assert "zed" in text


def test_load_missing_returns_none(tmp_path):
    assert answers.load(tmp_path / "nope.json") is None


def test_load_rejects_non_dict_and_empty(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("[]")
    assert answers.load(p) is None
    p.write_text("{}")
    assert answers.load(p) is None       # carries none of the keys -> None (ccpkg rule)
