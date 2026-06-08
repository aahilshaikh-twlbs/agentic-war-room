import ast
import os
import stat
from pathlib import Path

import warroom_setup
from warroom_setup import answers, setup as setup_mod

PKG = Path(warroom_setup.__file__).resolve().parent
ROOT = PKG.parent


def _module_files():
    return sorted(p for p in PKG.glob("*.py") if p.name != "__init__.py")


def test_no_network_imports_in_package():
    banned = {"socket", "urllib", "http", "requests", "ftplib", "telnetlib", "smtplib"}
    for f in _module_files():
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] not in banned, f"{f.name} imports {n.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned, f"{f.name} from {node.module}"


def test_state_module_is_pure_no_io():
    tree = ast.parse((PKG / "state.py").read_text())
    banned = {"os", "sys", "termios", "tty", "select", "io", "subprocess"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert n.name not in banned, f"state.py imports {n.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in banned, f"state.py from {node.module}"


def test_no_module_imports_cli_or_setup_except_entrypoints():
    for f in _module_files():
        if f.name in ("cli.py", "setup.py", "__main__.py"):
            continue
        text = f.read_text()
        assert "from .cli" not in text and "from .setup" not in text, f"{f.name} creates a cycle"


def test_no_shell_true_or_os_system():
    for f in _module_files():
        text = f.read_text()
        assert "os.system" not in text, f"{f.name} uses os.system"
        assert "shell=True" not in text, f"{f.name} uses shell=True"


def test_distribution_ships_no_symlinks():
    skip = {".venv", "__pycache__", ".pytest_cache", ".git", ".egg-info"}
    for p in ROOT.rglob("*"):
        if any(part in skip or part.endswith(".egg-info") for part in p.parts):
            continue
        assert not p.is_symlink(), f"Hermes rejects distributions with symlinks: {p}"


def test_answers_save_strips_secrets_and_is_0600(tmp_path):
    p = tmp_path / ".warroom-setup.json"
    answers.save(p, answers.Answers(values={"agent_name": "z", "ANTHROPIC_API_KEY": "sk-x"}))
    assert "sk-x" not in p.read_text()
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_write_env_is_0600(tmp_path):
    (tmp_path / ".env.EXAMPLE").write_text("ANTHROPIC_API_KEY=\n")
    setup_mod.write_env(tmp_path, {"ANTHROPIC_API_KEY": "sk-secret"})
    assert stat.S_IMODE(os.stat(tmp_path / ".env").st_mode) == 0o600


def test_validate_slug():
    assert setup_mod._validate_slug("warroom")
    assert setup_mod._validate_slug("aria-1")
    assert not setup_mod._validate_slug("Bad Name")
    assert not setup_mod._validate_slug("1leading")
    assert not setup_mod._validate_slug("")
