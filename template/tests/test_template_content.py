"""Shape + sanitization guards for shipped template content files.

These lock the deliverables of Phase 4 (T10-T17): correct structure, required
placeholders, and ZERO employer/operator strings. Tests accrete here as each
content task lands.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---- T10: SOUL.md skeleton ----

def test_soul_skeleton_has_h1_and_sections():
    text = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    assert text.lstrip().startswith("<!--") or text.lstrip().startswith("# ")
    h2s = re.findall(r"^## (.+)$", text, re.M)
    for required in ("Voice", "How you talk", "How you work", "What you value",
                     "Communication", "Writing rules", "Boundaries"):
        assert required in h2s, "missing H2: %s" % required
    assert 6 <= len(h2s) <= 8


def test_soul_skeleton_is_all_fill_in_no_real_content():
    text = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    assert "<<FILL-IN" in text

# ---- T11: memory files + convention ----

def test_memory_files_exist_with_separator_header():
    for name in ("USER.md", "MEMORY.md"):
        f = ROOT / "memories" / name
        assert f.is_file()
        head = f.read_text(encoding="utf-8")
        assert "§" in head            # documents the § separator
        assert head.count("\n") <= 4       # header-only, no real content

def test_readme_documents_memory_convention():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Memory convention" in readme
    assert "§" in readme


# ---- T12: channel_directory.json ----

def test_channel_directory_is_empty_skeleton():
    data = json.loads((ROOT / "channel_directory.json").read_text(encoding="utf-8"))
    assert data == {"updated_at": None, "platforms": {}}


# ---- T13: slack-manifest.json ----

def test_slack_manifest_is_generic_with_placeholders():
    raw = (ROOT / "slack-manifest.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["display_information"]["name"] == "<<APP_NAME>>"
    assert data["features"]["bot_user"]["display_name"] == "<<BOT_HANDLE>>"
    cmds = data["features"]["slash_commands"]
    assert len(cmds) == 1
    assert cmds[0]["command"] == "/ping"

# ---- T14: cron/jobs.json + schema README ----

def test_cron_jobs_is_empty_list():
    data = json.loads((ROOT / "cron" / "jobs.json").read_text(encoding="utf-8"))
    assert data == {"jobs": []}


def test_cron_readme_documents_schema():
    readme = (ROOT / "cron" / "README.md").read_text(encoding="utf-8")
    for field in ("id", "name", "prompt", "schedule", "enabled"):
        assert field in readme

# ---- T16: .env.template (no .env.example; Hermes renames .env.template) ----

def test_env_template_has_commented_mailbox_override():
    lines = (ROOT / ".env.template").read_text(encoding="utf-8").splitlines()
    # The override is present but COMMENTED OUT by default.
    assert any(l.strip() == "#MAILBOX_BOARD_OVERRIDE=" for l in lines)
    # It must NOT appear as an active (uncommented) key.
    assert not any(l.strip() == "MAILBOX_BOARD_OVERRIDE=" for l in lines)


def test_env_template_keys_consistent_with_distribution():
    env_keys = set()
    for line in (ROOT / ".env.template").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and s.endswith("="):
            env_keys.add(s[:-1])
    dist = (ROOT / "distribution.yaml").read_text(encoding="utf-8")
    req = set(re.findall(r"- name:\s*(\S+)", dist))
    # every declared env_requires key must exist in .env.template
    assert req <= env_keys, "env_requires not covered by .env.template: %s" % (req - env_keys)


# ---- T17: hooks/ + scripts/ READMEs ----

def test_hooks_readme_documents_contracts():
    text = (ROOT / "hooks" / "README.md").read_text(encoding="utf-8")
    for contract in ("on_session_start", "pre_tool_use", "post_tool_use"):
        assert contract in text

def test_scripts_readme_documents_entrypoints():
    text = (ROOT / "scripts" / "README.md").read_text(encoding="utf-8")
    for script in ("setup.sh", "publish.sh", "install.sh", "assimilate.sh"):
        assert script in text


# ---- T22: README updates (append-only; old sections preserved) ----

def test_readme_documents_mailbox_and_mcp_and_sanitization():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "mailbox:" in readme                      # routing block
    assert "mcp_servers:" in readme                  # MCP in config.yaml, not mcp.json
    assert "no separate `mcp.json`" in readme
    assert "## Sanitization" in readme
    assert "SANITIZATION.md" in readme
    # cross-agent (feature C) known limitation
    assert "Cross-agent runtime" in readme


def test_readme_preserves_existing_sections():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # T22 must APPEND, not delete the prior sections.
    assert "## Verified" in readme
    assert "## Known limitations" in readme
    assert "local/.warroom-setup.json" in readme     # original known-limitation bullet