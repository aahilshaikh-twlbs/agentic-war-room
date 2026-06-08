"""T0.5 — template/config.yaml hooks block must be Hermes-correct.

Hermes (shell_hooks._parse_hooks_block) accepts ONLY a list-of-mappings under
each `hooks.<event>` key; a scalar string is warn-skipped (so first_run.sh
never fires). These tests assert the shipped shape and that the install-time
rewriter produces an absolute, existing command path.

Stdlib-only: no YAML dependency is available, so we use a narrow indentation
parser for the specific `hooks.on_session_start` structure plus a faithful
minimal port of Hermes's `_parse_hooks_block`.
"""
import re
from pathlib import Path

from warroom_setup import setup

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]
CONFIG = TEMPLATE_ROOT / "config.yaml"


def _extract_on_session_start(text):
    """Parse `hooks.on_session_start` into a list[dict] (stdlib-only)."""
    out = []
    in_hooks = False
    in_oss = False
    cur = None
    for line in text.splitlines():
        if re.match(r"^hooks:\s*$", line):
            in_hooks = True
            continue
        if in_hooks and re.match(r"^\S", line) and not line.startswith("hooks:"):
            # next top-level key ends the hooks block
            break
        if in_hooks:
            if re.match(r"^  on_session_start:\s*$", line):
                in_oss = True
                continue
            if in_oss:
                mi = re.match(r"^    -\s+(\w+):\s*(.*)$", line)
                if mi:
                    cur = {mi.group(1): mi.group(2).strip().strip('"')}
                    out.append(cur)
                    continue
                mk = re.match(r"^      (\w+):\s*(.*)$", line)
                if mk and cur is not None:
                    cur[mk.group(1)] = mk.group(2).strip().strip('"')
                    continue
                if re.match(r"^  \S", line):  # a different hooks subkey
                    in_oss = False
    return out


def _parse_hooks_block(hooks_cfg):
    """Faithful minimal port of Hermes shell_hooks._parse_hooks_block."""
    if not isinstance(hooks_cfg, dict):
        return []
    specs = []
    for _event, entries in hooks_cfg.items():
        if not isinstance(entries, list):
            continue
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            cmd = raw.get("command")
            if isinstance(cmd, str) and cmd.strip():
                specs.append(cmd.strip())
    return specs


def test_config_hooks_block_is_list_of_mappings():
    text = CONFIG.read_text(encoding="utf-8")
    entries = _extract_on_session_start(text)
    assert isinstance(entries, list) and entries, "on_session_start must be a non-empty list"
    for e in entries:
        assert isinstance(e, dict), "each hook entry must be a mapping"
        assert "command" in e and e["command"].strip(), "each entry needs a command"
        assert "first_run.sh" in e["command"]


def test_iter_configured_hooks_returns_nonempty():
    text = CONFIG.read_text(encoding="utf-8")
    cfg = {"hooks": {"on_session_start": _extract_on_session_start(text)}}
    specs = _parse_hooks_block(cfg["hooks"])
    assert len(specs) >= 1


def test_first_run_script_path_resolves_at_install_time(tmp_path):
    # Build a profile that ships the relative command + a hooks/first_run.sh.
    prof = tmp_path / "profiles" / "alpha-sh"
    (prof / "hooks").mkdir(parents=True)
    (prof / "hooks" / "first_run.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    prof.joinpath("config.yaml").write_text(
        "hooks:\n"
        "  on_session_start:\n"
        '    - command: "bash hooks/first_run.sh"\n',
        encoding="utf-8",
    )
    setup.patch_hooks_command(prof)
    entries = _extract_on_session_start((prof / "config.yaml").read_text(encoding="utf-8"))
    assert len(entries) == 1
    cmd = entries[0]["command"]
    # command is `bash <abs>/hooks/first_run.sh`; the path component must be absolute & exist
    path = cmd.split(" ", 1)[1]
    assert Path(path).is_absolute()
    assert Path(path).exists()
    # idempotent
    setup.patch_hooks_command(prof)
    again = _extract_on_session_start((prof / "config.yaml").read_text(encoding="utf-8"))
    assert again == entries
