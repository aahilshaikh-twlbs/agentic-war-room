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
    # The original scalars are unchanged...
    assert cfg["enforce"] is False
    assert cfg["min_confidence"] == 75
    assert cfg["show_badge"] is True
    # ...and the DEFCON keys default OFF (no severity table => default-only floor).
    assert cfg["severity_thresholds"] == {"default": 75}
    assert cfg["severity_inference"] == "explicit"
    assert cfg["require_verifier_at"] == ""
    assert cfg["verifier_label"] == ""
    assert cfg["verifier_timeout_s"] == 30
    assert cfg["escalate_at"] == ""


def test_default_floor_derived_from_min_confidence_when_no_table(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  min_confidence: 90\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"default": 90}


def test_nested_severity_thresholds_parsed(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model: {}\n"
        "war_room:\n"
        "  enabled: true\n"
        "  min_confidence: 75\n"
        "  enforce: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "    alert2: 85\n"
        "    default: 75\n"
        "  require_verifier_at: alert1\n"
        "  verifier_label: verify-sh\n"
        "  verifier_timeout_s: 45\n"
        "  escalate_at: alert2\n"
        "plugins:\n  enabled: true\n"
    )
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "alert2": 85, "default": 75}
    assert cfg["require_verifier_at"] == "alert1"
    assert cfg["verifier_label"] == "verify-sh"
    assert cfg["verifier_timeout_s"] == 45
    assert cfg["escalate_at"] == "alert2"
    # the flat scalars after the nested mapping are still read
    assert cfg["enforce"] is True and cfg["min_confidence"] == 75


def test_nested_table_implies_default_from_min_confidence(tmp_path):
    # severity_thresholds present but no explicit `default` key -> default
    # floor falls back to min_confidence.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  min_confidence: 70\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "default": 70}


def test_block_end_detection_with_nested_mapping(tmp_path):
    # A non-indented key after the nested mapping ends the block; keys beyond
    # the block (plugins:) must not leak in.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  severity_thresholds:\n"
        "    alert1: 95\n"
        "plugins:\n"
        "  alert1: 1\n")    # a same-named key OUTSIDE the block must be ignored
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert1": 95, "default": 75}


def test_verifier_timeout_clamped(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  verifier_timeout_s: 9999\n")
    assert G.read(tmp_path)["verifier_timeout_s"] == 120   # clamp <=120
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  verifier_timeout_s: 0\n")
    assert G.read(tmp_path)["verifier_timeout_s"] == 1     # clamp >=1


def test_unparseable_severity_value_skipped(tmp_path):
    # A non-int floor under the nested mapping is dropped (not a crash); the
    # default floor still resolves from min_confidence.
    (tmp_path / "config.yaml").write_text(
        "war_room:\n"
        "  enforce: true\n"
        "  min_confidence: 75\n"
        "  severity_thresholds:\n"
        "    alert1: high\n"
        "    alert2: 85\n")
    cfg = G.read(tmp_path)
    assert cfg["severity_thresholds"] == {"alert2": 85, "default": 75}


def test_enforce_defaults_false_when_absent(tmp_path):
    (tmp_path / "config.yaml").write_text("war_room:\n  board: x\n")
    assert G.read(tmp_path)["enforce"] is False


def test_reads_label(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "war_room:\n  enforce: true\n  label: alpha-sh\n")
    assert G.read(tmp_path)["label"] == "alpha-sh"


def test_label_defaults_empty(tmp_path):
    cfg = G.read(tmp_path)
    assert cfg["label"] == ""
