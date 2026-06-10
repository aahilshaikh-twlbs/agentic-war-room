"""Multi-board federation: template-side `parent` wiring (schema key, wizard
field, war_room block rendering, run_setup pass-through). The runtime stays
single-board (`MAILBOX_BOARD` only); federation is resolved engine-side."""
import io
import shutil
from pathlib import Path

from warroom_setup import enroll, schema, selectables, setup


def test_schema_has_parent_key_after_board():
    keys = list(schema.WAR_ROOM_KEYS)
    assert "parent" in keys
    assert keys.index("parent") == keys.index("board") + 1
    assert schema.DEFAULTS["parent"] == ""


def test_patch_war_room_block_renders_parent(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_war_room_block(tmp_path, "squad-api", parent="team-platform")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "board: squad-api" in text
    assert "parent: team-platform" in text


def test_blank_parent_is_omitted_from_block(tmp_path):
    # Zero rendered-byte change for non-federated profiles (DV2).
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_war_room_block(tmp_path, "squad-api")
    assert "parent:" not in (tmp_path / "config.yaml").read_text(
        encoding="utf-8")


def test_mailbox_block_unchanged_by_parent_feature(tmp_path):
    (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    setup.patch_mailbox_block(tmp_path, board="squad-api")
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "parent" not in text
    assert schema.MAILBOX_KEYS == ("board", "label", "mailbox_home",
                                   "socket_path")


def test_selectables_parent_field_appended_last_with_enable_if():
    ids = [f.id for f in selectables.TEXT_FIELDS]
    assert ids[-1] == "warroom.parent"      # F10 rule: appended, never inserted
    fld = [f for f in selectables.TEXT_FIELDS if f.id == "warroom.parent"][0]
    assert fld.enable_if == "warroom.enroll"
    assert fld.secret is False and fld.required is False
    assert "warroom.parent" not in selectables.ENV_FIELD_IDS


def _fake_profile(tmp_path):
    src = Path(__file__).resolve().parents[1]
    prof = tmp_path / "profiles" / "zed"
    prof.mkdir(parents=True)
    for d in ("persona", "templates", "shared"):
        shutil.copytree(src / d, prof / d)
    shutil.copy2(src / "manifest.json", prof / "manifest.json")
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n")
    (prof / "config.yaml").write_text("model:\n  name: opus\n")
    return prof


class _ParentAwareRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, profile_root, board, label, dry_run=False, env=None,
                 parent=None):
        self.calls.append({"board": board, "label": label, "parent": parent})
        return enroll.EnrollState(board=board, label=label, cli_path=None,
                                  mailbox_home="", socket_path="",
                                  last_check_ts=0.0, status="ok")


class _LegacyRecorder:
    """Old bootstrap signature (no parent kwarg) — proves run_setup only
    passes parent= when the operator actually supplied one."""

    def __init__(self):
        self.calls = []

    def __call__(self, profile_root, board, label, dry_run=False, env=None):
        self.calls.append({"board": board, "label": label})
        return enroll.EnrollState(board=board, label=label, cli_path=None,
                                  mailbox_home="", socket_path="",
                                  last_check_ts=0.0, status="ok")


def _run(prof, monkeypatch, rec, extra_lines=""):
    monkeypatch.setenv("HOME", str(prof.parent.parent / "home"))
    monkeypatch.setattr(enroll, "bootstrap", rec)
    instream = io.StringIO(
        "zed\nZed\n\nsk-anthropic\ndt-token\n123,456\n" + extra_lines
    )
    toggle_in = io.StringIO("\n\n\n\n\n")
    return setup.run_setup(prof, yes=False, reconfigure=False,
                           in_stream=instream, out_stream=io.StringIO(),
                           toggle_in_stream=toggle_in)


def test_run_setup_passes_parent_to_bootstrap_and_block(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _ParentAwareRecorder()
    # prompt order after the channel fields: board, min_confidence, label, parent
    rc = _run(prof, monkeypatch, rec,
              extra_lines="squad-api\n80\nalpha-sh\nteam-platform\n")
    assert rc == 0
    assert rec.calls == [{"board": "squad-api", "label": "alpha-sh",
                          "parent": "team-platform"}]
    text = (prof / "config.yaml").read_text(encoding="utf-8")
    assert "parent: team-platform" in text


def test_run_setup_blank_parent_omits_kwarg(tmp_path, monkeypatch):
    prof = _fake_profile(tmp_path)
    rec = _LegacyRecorder()
    rc = _run(prof, monkeypatch, rec,
              extra_lines="squad-api\n80\nalpha-sh\n\n")
    assert rc == 0
    assert rec.calls == [{"board": "squad-api", "label": "alpha-sh"}]
    assert "parent:" not in (prof / "config.yaml").read_text(encoding="utf-8")
