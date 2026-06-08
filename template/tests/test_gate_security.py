import ast
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "warroom-gate"


def _wg_modules():
    return sorted(PLUGIN.glob("wg_*.py"))


def test_no_network_imports_in_plugin():
    banned = {"socket", "urllib", "http", "requests", "ftplib", "smtplib"}
    for f in _wg_modules() + [PLUGIN / "__init__.py"]:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] not in banned, f"{f.name} imports {n.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned


def test_pure_modules_have_no_io():
    banned = {"os", "subprocess", "socket", "sys"}
    for name in ("wg_envelope.py", "wg_classify.py", "wg_policy.py", "wg_render.py"):
        tree = ast.parse((PLUGIN / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name not in banned, f"{name} imports {n.name}"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") not in banned, f"{name} imports from {node.module}"


def test_no_shell_or_eval():
    for f in _wg_modules() + [PLUGIN / "__init__.py"]:
        text = f.read_text()
        assert "os.system" not in text and "shell=True" not in text
        assert "eval(" not in text and "exec(" not in text


def test_gate_callback_signature_is_kwargs_tolerant():
    # transform_llm_output passes response_text/session_id/model/platform; the
    # callback must accept unknown kwargs (**_) so a future payload key can't crash it.
    import inspect
    import wg_gate
    sig = inspect.signature(wg_gate.gate)
    assert any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()), "gate() must accept **kwargs"
