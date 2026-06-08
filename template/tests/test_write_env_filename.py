"""write_env(..., filename=) parameterization (Task T3).

Default callsites keep writing .env (seeded from .env.EXAMPLE). A custom
filename writes elsewhere (e.g. local/sentinel.env), creating parent dirs and
NOT seeding from the example.
"""
from pathlib import Path

from warroom_setup import setup


def _prof(tmp_path):
    prof = tmp_path / "profiles" / "zed"
    prof.mkdir(parents=True)
    (prof / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\nDISCORD_BOT_TOKEN=\n", encoding="utf-8")
    return prof


def test_default_filename_still_writes_dotenv(tmp_path):
    prof = _prof(tmp_path)
    setup.write_env(prof, {"ANTHROPIC_API_KEY": "sk-1"})
    env = (prof / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-1" in env
    # default path still seeds remaining keys from the example
    assert "DISCORD_BOT_TOKEN=" in env


def test_custom_filename_writes_to_subpath_and_creates_dirs(tmp_path):
    prof = _prof(tmp_path)
    setup.write_env(prof, {"MAILBOX_BOARD": "demo"}, filename="local/sentinel.env")
    target = prof / "local" / "sentinel.env"
    assert target.is_file()
    assert "MAILBOX_BOARD=demo" in target.read_text(encoding="utf-8")


def test_custom_filename_does_not_seed_from_example(tmp_path):
    prof = _prof(tmp_path)
    setup.write_env(prof, {"MAILBOX_BOARD": "demo"}, filename="local/sentinel.env")
    body = (prof / "local" / "sentinel.env").read_text(encoding="utf-8")
    # example-only keys must NOT leak into the custom file
    assert "ANTHROPIC_API_KEY" not in body
    assert "DISCORD_BOT_TOKEN" not in body


def test_custom_filename_overwrites_existing_key_preserves_others(tmp_path):
    prof = _prof(tmp_path)
    (prof / "local").mkdir()
    (prof / "local" / "sentinel.env").write_text("MAILBOX_BOARD=old\nKEEP=yes\n", encoding="utf-8")
    setup.write_env(prof, {"MAILBOX_BOARD": "new"}, filename="local/sentinel.env")
    body = (prof / "local" / "sentinel.env").read_text(encoding="utf-8")
    assert "MAILBOX_BOARD=new" in body
    assert "KEEP=yes" in body
    assert "MAILBOX_BOARD=old" not in body
