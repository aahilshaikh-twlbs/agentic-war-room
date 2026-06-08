import io
import json
import shutil
from pathlib import Path
from warroom_setup import setup


def _fake_profile(tmp_path):
    """Build a profile dir that looks like a freshly-installed distribution."""
    src = Path(__file__).resolve().parents[1]      # template/
    prof = tmp_path / "profiles" / "zed"
    prof.mkdir(parents=True)
    for d in ("persona", "templates", "shared"):
        shutil.copytree(src / d, prof / d)
    shutil.copy2(src / "manifest.json", prof / "manifest.json")
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n")
    (prof / "config.yaml").write_text("model:\n  name: opus\n")
    return prof


def test_seed_overlay_copies_persona_once(tmp_path):
    prof = _fake_profile(tmp_path)
    setup.seed_overlay(prof)
    assert (prof / "local" / "persona" / "voice.md").is_file()
    # second call must NOT clobber user edits
    (prof / "local" / "persona" / "voice.md").write_text("EDITED")
    setup.seed_overlay(prof)
    assert (prof / "local" / "persona" / "voice.md").read_text() == "EDITED"


def test_write_env_merges_values_into_example(tmp_path):
    prof = _fake_profile(tmp_path)
    setup.write_env(prof, {"ANTHROPIC_API_KEY": "sk-1", "DISCORD_BOT_TOKEN": "dt-1"})
    env = (prof / ".env").read_text()
    assert "ANTHROPIC_API_KEY=sk-1" in env
    assert "DISCORD_BOT_TOKEN=dt-1" in env


def test_run_setup_headless_writes_identity_env_and_soul(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    # redirect claude head + hermes soul targets into tmp via HOME
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    instream = io.StringIO(
        "zed\n"            # agent_name
        "Zed\n"            # display_name
        "\n"               # handle (defaults to agent_name)
        "sk-anthropic\n"   # ANTHROPIC_API_KEY
        "dt-token\n"       # DISCORD_BOT_TOKEN (discord default-on)
        "123,456\n"        # DISCORD_ALLOWED_USERS
        "\n"               # war-room board (warroom.enroll default-on)
    )
    outstream = io.StringIO()
    # feed the toggle wizard via the numbered fallback: accept defaults each stage + apply
    toggle_in = io.StringIO("\n\n\n\n\n")
    rc = setup.run_setup(prof, yes=False, reconfigure=False,
                         in_stream=instream, out_stream=outstream, toggle_in_stream=toggle_in)
    assert rc == 0
    ident = json.loads((prof / "local" / "agent.json").read_text())
    assert ident["agent_name"] == "zed" and ident["handle"] == "zed"
    assert "ANTHROPIC_API_KEY=sk-anthropic" in (prof / ".env").read_text()
    soul = tmp_path / "home" / ".hermes" / "profiles" / "zed" / "SOUL.md"
    assert soul.is_file()
    assert "{{" not in soul.read_text()
    # answers persisted, secret stripped
    saved = json.loads((prof / "local" / ".warroom-setup.json").read_text())
    assert "sk-anthropic" not in json.dumps(saved)
