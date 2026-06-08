import wg_gateconfig as G


def test_reads_managed_block(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model: {}\n"
        "# >>> warroom-managed (set via `warroom setup`) >>>\n"
        "war_room:\n"
        "  enabled: true\n"
        "  board: incident-1\n"
        "  min_confidence: 80\n"
        "  gate_action: abstain\n"
        "  enforce: true\n"
        "  show_confidence_badge: false\n"
        "# <<< warroom-managed <<<\n"
        "plugins:\n  enabled: true\n"
    )
    cfg = G.read(tmp_path)
    assert cfg["enforce"] is True
    assert cfg["min_confidence"] == 80
    assert cfg["show_badge"] is False


def test_defaults_when_missing(tmp_path):
    cfg = G.read(tmp_path)            # no config.yaml
    assert cfg == {"enforce": False, "min_confidence": 75, "show_badge": True}


def test_enforce_defaults_false_when_absent(tmp_path):
    (tmp_path / "config.yaml").write_text("war_room:\n  board: x\n")
    assert G.read(tmp_path)["enforce"] is False
