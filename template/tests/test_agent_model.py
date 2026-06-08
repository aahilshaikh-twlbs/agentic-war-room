import json
from pathlib import Path
from warroom_setup import agent_model


def test_defaults_and_roundtrip(tmp_path):
    ident = agent_model.AgentIdentity(
        agent_name="warroom", handle="warroom", display_name="War Room",
        model="opus", specialist_prefix="warroom", agent_fingerprint="warroom-abc123",
    )
    p = tmp_path / "agent.json"
    agent_model.save(p, ident)
    loaded = agent_model.load(p)
    assert loaded == ident
    # file is pretty JSON with trailing newline
    assert p.read_text().endswith("\n")
    json.loads(p.read_text())  # valid JSON


def test_load_missing_returns_none(tmp_path):
    assert agent_model.load(tmp_path / "nope.json") is None


def test_as_substitutions_keys():
    ident = agent_model.AgentIdentity(
        agent_name="aria", handle="aria-sh", display_name="Aria",
        model="opus", specialist_prefix="aria", agent_fingerprint="aria-1",
    )
    subs = ident.as_substitutions()
    assert subs["{{agent_name}}"] == "aria"
    assert subs["{{handle}}"] == "aria-sh"
    assert subs["{{display_name}}"] == "Aria"
    assert subs["{{model}}"] == "opus"
    assert subs["{{specialist_prefix}}"] == "aria"
    assert subs["{{agent_fingerprint}}"] == "aria-1"
