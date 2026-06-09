"""T7 -- resume sidecar at ~/.awr/install-state.json."""
import json
import stat
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "scripts" / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import sidecar_state as ss  # noqa: E402


def _sc(tmp_path, **kw):
    return ss.Sidecar(tmp_path / ".awr" / "install-state.json", **kw)


def _payload(**over):
    base = dict(
        profile_name="alpha-sh", source="/tmpl", channels=["discord"],
        agent_name="alpha-sh", display_name="Alpha", handle="alpha-sh",
        min_confidence=80, model="opus", board="shared", label="alpha-sh",
    )
    base.update(over)
    return base


def test_persists_non_secret_only(tmp_path):
    sc = _sc(tmp_path)
    payload = _payload(anthropic_key="sk-ant-" + "x" * 40,
                       discord_bot_token="FAKE.tok.FAKE", api_secret="nope")
    sc.save(payload, stage="anthropic", completed_stages=[1])
    raw_text = sc.path.read_text(encoding="utf-8")
    assert "sk-ant-" not in raw_text
    assert "FAKE.tok.FAKE" not in raw_text
    answers = json.loads(raw_text)["answers_non_secret"]
    assert "anthropic_key" not in answers
    assert "discord_bot_token" not in answers
    assert "api_secret" not in answers
    assert answers["profile_name"] == "alpha-sh"  # non-secret preserved


def test_dotawr_namespace():
    p = str(ss.default_path())
    assert p.endswith("/.awr/install-state.json")
    assert "/.hermes/" not in p


def test_creates_parent_with_0700(tmp_path):
    sc = _sc(tmp_path)
    sc.save(_payload(), stage="name", completed_stages=[])
    dmode = stat.S_IMODE(sc.path.parent.stat().st_mode)
    fmode = stat.S_IMODE(sc.path.stat().st_mode)
    assert dmode == 0o700
    assert fmode == 0o600


def test_records_stage(tmp_path):
    sc = _sc(tmp_path)
    sc.save(_payload(), stage="name", completed_stages=[1])
    sc.record_stage("identity", [1, 2, 3])
    rec = sc.load()
    assert rec["stage"] == "identity"
    assert rec["completed_stages"] == [1, 2, 3]


def test_resume_skips_completed(tmp_path):
    sc = _sc(tmp_path)
    sc.save(_payload(), stage="model", completed_stages=[1, 2])
    rec = sc.load()
    assert ss.pending_stages(rec) == [3, 4, 5]


def test_resume_after_walkthrough_re_prompts_secrets(tmp_path):
    sc = _sc(tmp_path)
    sc.save(_payload(channels=["discord", "slack"]), stage="anthropic", completed_stages=[1])
    rec = sc.load()
    # secrets were never persisted -> both channels must be re-prompted (K6)
    assert set(ss.channels_needing_reprompt(rec)) == {"discord", "slack"}


def test_expired_after_24h_ignored(tmp_path):
    clock = {"t": 1000.0}
    sc = _sc(tmp_path, clock=lambda: clock["t"])
    sc.save(_payload(), stage="name", completed_stages=[1])
    assert sc.load() is not None
    clock["t"] = 1000.0 + 25 * 3600  # +25h
    assert sc.load() is None
    assert sc.is_expired() is True


def test_cleanup_on_success(tmp_path):
    sc = _sc(tmp_path)
    sc.save(_payload(), stage="confirm", completed_stages=[1, 2, 3, 4, 5])
    assert sc.path.exists()
    sc.cleanup()
    assert not sc.path.exists()
    sc.cleanup()  # idempotent


def test_save_preserves_started_at_across_updates(tmp_path):
    clock = {"t": 500.0}
    sc = _sc(tmp_path, clock=lambda: clock["t"])
    sc.save(_payload(), stage="name", completed_stages=[1])
    clock["t"] = 800.0
    sc.save(_payload(), stage="model", completed_stages=[1, 2])
    rec = sc.load()
    assert rec["started_at"] == 500.0  # original
    assert rec["last_updated"] == 800.0
