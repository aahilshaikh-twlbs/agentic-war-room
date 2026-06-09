"""Feature B integration tests (gated on --runintegration).

All seven are SIMULATION-based: the `hermes profile install` / `plugins enable`
subprocesses are faked (a fake install materializes a real importable profile),
so the suite exercises the full integrated flow end-to-end without touching a
real Hermes install. Everything is isolated to a tmp profiles_root / HOME.

Run: `.venv/bin/python -m pytest tests/test_installer_e2e.py --runintegration -q`
"""
import io
import json
import shutil
import sys
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
TEMPLATE_DIR = Path(__file__).resolve().parents[1]
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import awr_install as awr  # noqa: E402
import in_process_orchestrator as orch  # noqa: E402
import profile_detect as pd  # noqa: E402
import rollback as rb  # noqa: E402
import sidecar_state as ss  # noqa: E402
import subprocess_runner as sr  # noqa: E402
from _substrate.discord_walkthrough import DiscordCreds  # noqa: E402

pytestmark = pytest.mark.integration

_FAKE_DISCORD = "FAKE_TEST_TOKEN_NOT_REAL.zzzzz.FAKE_TEST_TOKEN_NOT_REAL"


def _materialize(profile_root: Path):
    """Create a real, importable profile (what `hermes profile install` lands)."""
    profile_root.mkdir(parents=True, exist_ok=True)
    ws = profile_root / "warroom_setup"
    ws.mkdir(exist_ok=True)
    (ws / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(TEMPLATE_DIR / "config.yaml", profile_root / "config.yaml")
    (profile_root / ".env.EXAMPLE").write_text(
        "ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\nDISCORD_HOME_CHANNEL=\n", encoding="utf-8"
    )
    return profile_root


def _ok(lines=None):
    return sr.CommandResult(returncode=0, lines=lines or ["ok"], duration_s=0.1)


def _answers(name="alpha-sh", **over):
    base = dict(
        source=str(TEMPLATE_DIR), profile_name=name, channels={"discord"},
        discord_creds=DiscordCreds(bot_token=_FAKE_DISCORD, channel_id="12345678901234567"),
        slack_creds=None, anthropic_key="sk-ant-" + "x" * 40, agent_name=name,
        display_name="Alpha", handle=name, discord_allowed_users=["u1"],
        min_confidence=80, model="opus", board="shared", label=name,
    )
    base.update(over)
    return awr.InstallerAnswers(**base)


def _isolate_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


# --------------------------------------------------------------------------- #
def test_happy_path_neutral_profile(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    profiles_root = tmp_path / "profiles"
    a = _answers("alpha-sh")

    def hermes(cmd, *, timeout, tee=None):
        _materialize(profiles_root / a.profile_name)
        return _ok(["installed alpha-sh"])

    res = orch.execute(
        a, profiles_root=profiles_root, hermes_runner=hermes,
        plugin_runner=lambda c, *, timeout, tee=None: _ok(), out=io.StringIO(),
    )
    assert res.exit_code == 0
    assert res.completed_stages == [1, 2, 3, 4, 5]
    prof = profiles_root / "alpha-sh"
    env = (prof / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-ant-" in env
    assert "DISCORD_BOT_TOKEN=" + _FAKE_DISCORD in env
    cfg = (prof / "config.yaml").read_text(encoding="utf-8")
    assert "war_room:" in cfg and "mailbox:" in cfg and "board: shared" in cfg
    agent = json.loads((prof / "local" / "agent.json").read_text(encoding="utf-8"))
    assert agent["agent_name"] == "alpha-sh"
    assert (prof / "local" / "warroom-enroll.json").exists()


def test_rollback_on_simulated_hermes_failure(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    profiles_root = tmp_path / "profiles"
    a = _answers("alpha-sh")

    def hermes_fail(cmd, *, timeout, tee=None):
        _materialize(profiles_root / a.profile_name)  # half-populated
        return sr.CommandResult(returncode=1, lines=["error: DistributionError"], duration_s=0.1)

    res = orch.execute(
        a, profiles_root=profiles_root, hermes_runner=hermes_fail,
        plugin_runner=lambda c, *, timeout, tee=None: _ok(), out=io.StringIO(),
    )
    assert res.exit_code == 1 and res.failed_stage == 1
    prof = profiles_root / "alpha-sh"
    rbres = rb.rollback(prof, stages_completed=res.completed_stages)
    assert rbres.removed is True
    assert not prof.exists()


def test_resume_after_simulated_sigint(tmp_path):
    sc = ss.Sidecar(tmp_path / ".awr" / "install-state.json")

    class _Args:
        headless = False
        source = str(TEMPLATE_DIR)
        force = False

    # Feed source (accept default) + name, then Ctrl-C at the channels stage.
    feed = "\n".join([str(TEMPLATE_DIR), "alpha-sh", "\x03"]) + "\n"
    io_ = awr.WizardIO(infile=io.StringIO(feed), outfile=io.StringIO())
    result = awr.run_tui(_Args(), io=io_, sidecar=sc, restore=lambda: None,
                         git_runner=lambda u: True)
    assert result is None  # aborted
    state = sc.load()
    assert state is not None
    assert state["profile_name"] == "alpha-sh"
    # secrets never persisted; channels selected (if any) would need re-prompt
    assert "anthropic_key" not in json.dumps(state)


def test_two_step_path_still_works(tmp_path, monkeypatch):
    # The manual two-step path (warroom_setup.setup.run_setup) is unchanged by
    # feature B; prove it still installs a profile.
    import warroom_setup.setup as setup

    src = TEMPLATE_DIR
    prof = tmp_path / "profiles" / "beta-sh"
    prof.mkdir(parents=True)
    for d in ("persona", "templates", "shared"):
        shutil.copytree(src / d, prof / d)
    shutil.copy2(src / "manifest.json", prof / "manifest.json")
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n", encoding="utf-8")
    (prof / "config.yaml").write_text("model:\n  name: opus\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    instream = io.StringIO(
        "beta-sh\n"        # agent_name
        "Beta\n"           # display_name
        "\n"               # handle -> agent_name
        "sk-anthropic\n"   # ANTHROPIC_API_KEY
        "dt-token\n"       # DISCORD_BOT_TOKEN
        "123,456\n"        # DISCORD_ALLOWED_USERS
        "shared\n"         # war-room board
    )
    toggle_in = io.StringIO("\n\n\n\n\n")
    rc = setup.run_setup(prof, yes=False, reconfigure=False,
                         in_stream=instream, out_stream=io.StringIO(),
                         toggle_in_stream=toggle_in)
    assert rc == 0
    ident = json.loads((prof / "local" / "agent.json").read_text(encoding="utf-8"))
    assert ident["agent_name"] == "beta-sh"
    assert "ANTHROPIC_API_KEY=sk-anthropic" in (prof / ".env").read_text(encoding="utf-8")


def test_uninstall_round_trip(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    profiles_root = tmp_path / "profiles"
    prof = _materialize(profiles_root / "alpha-sh")
    captured = {}

    def hermes_delete(cmd, *, timeout, tee=None):
        captured["cmd"] = cmd
        shutil.rmtree(prof)  # real delete
        return _ok(["deleted"])

    rc = awr.uninstall("alpha-sh", profiles_root=profiles_root,
                       hermes_runner=hermes_delete,
                       sidecar=ss.Sidecar(tmp_path / ".awr" / "install-state.json"),
                       out=io.StringIO())
    assert rc == 0
    assert captured["cmd"] == ["hermes", "profile", "delete", "alpha-sh", "-y"]
    assert not prof.exists()


def test_collision_reconfigure_preserves_user_data(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    profiles_root = tmp_path / "profiles"
    prof = _materialize(profiles_root / "alpha-sh")
    # pre-existing user data
    persona = prof / "local" / "persona"
    persona.mkdir(parents=True)
    (persona / "voice.md").write_text("MY VOICE", encoding="utf-8")
    (prof / "local" / "agent.json").write_text(
        json.dumps({"agent_name": "alpha-sh", "handle": "alpha-sh", "display_name": "Alpha",
                    "model": "opus", "specialist_prefix": "alpha-sh",
                    "agent_fingerprint": "alpha-sh-deadbeef0000"}), encoding="utf-8")

    insp = pd.inspect_profile(prof)
    assert insp.strategy == pd.RECONFIGURE
    action = pd.collision_strategy(insp, force=False)
    assert action == pd.RECONFIGURE

    called = {"h": 0}

    def hermes(cmd, *, timeout, tee=None):
        called["h"] += 1
        return _ok()

    res = orch.execute(
        _answers("alpha-sh"), profiles_root=profiles_root, hermes_runner=hermes,
        plugin_runner=lambda c, *, timeout, tee=None: _ok(),
        skip_install=True, out=io.StringIO(),
    )
    assert res.exit_code == 0
    assert called["h"] == 0  # Stage 1 (reinstall) skipped
    assert (persona / "voice.md").read_text(encoding="utf-8") == "MY VOICE"  # preserved
    # the agent fingerprint is preserved across reconfigure
    agent = json.loads((prof / "local" / "agent.json").read_text(encoding="utf-8"))
    assert agent["agent_fingerprint"] == "alpha-sh-deadbeef0000"


def test_headless_full_install_with_env_secrets(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    profiles_root = tmp_path / "profiles"

    class _Args:
        headless = True
        name = "alpha-sh"
        source = str(TEMPLATE_DIR)
        board = "shared"
        label = None
        discord = True
        slack = False
        agent_name = "alpha-sh"
        display_name = "Alpha"
        handle = None
        discord_allowed_users = None
        min_confidence = 75
        model = "opus"
        anthropic_key_env = "ANTH"
        anthropic_key_file = None
        discord_token_env = "DTOK"
        discord_token_file = None
        discord_channel_id = "12345678901234567"
        discord_second_channel_id = None
        slack_app_token_env = slack_app_token_file = None
        slack_bot_token_env = slack_bot_token_file = None
        slack_channel_id = slack_second_channel_id = None

    env = {"ANTH": "sk-ant-" + "z" * 40, "DTOK": _FAKE_DISCORD}
    answers = awr.build_headless_answers(_Args(), env=env)

    def hermes(cmd, *, timeout, tee=None):
        _materialize(profiles_root / answers.profile_name)
        return _ok()

    res = orch.execute(
        answers, profiles_root=profiles_root, hermes_runner=hermes,
        plugin_runner=lambda c, *, timeout, tee=None: _ok(), out=io.StringIO(),
    )
    assert res.exit_code == 0
    env_text = (profiles_root / "alpha-sh" / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-ant-" in env_text
    assert "DISCORD_BOT_TOKEN=" + _FAKE_DISCORD in env_text
